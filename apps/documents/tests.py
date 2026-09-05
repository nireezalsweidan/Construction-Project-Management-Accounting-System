"""
Tests for the ``documents`` app -- Document Management (CPMAS-25).

Organized into:
- Model tests: basic sanity (str, ordering).
- API tests: upload (multipart), list/filter, metadata-only update,
  destroy (including the underlying file being removed from storage),
  and the read-only/locked fields (file_name/file_path/uploaded_by,
  entity_type/entity_id once created).
"""
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User
from users.testing import WithUsersTableMixin

from .models import Document


class DocumentsTestBase(WithUsersTableMixin, TestCase):
    """Shared fixtures: an uploader user and an authenticated APIClient."""

    def setUp(self):
        self.uploader = User.objects.create(
            username="uploader", email="uploader@example.com", password_hash="x",
            first_name="U", last_name="P", role="OWNER",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.uploader)

    def tearDown(self):
        # Clean up any files written to MEDIA_ROOT during a test.
        for doc in Document.objects.all():
            default_storage.delete(doc.file_path)

    def upload(self, entity_type="project", entity_id=None, document_type="CONTRACT", content=b"hello world", name="contract.pdf"):
        entity_id = entity_id or "11111111-1111-1111-1111-111111111111"
        upload_file = SimpleUploadedFile(name, content, content_type="application/pdf")
        return self.client.post("/api/documents/documents/", {
            "file": upload_file, "entity_type": entity_type, "entity_id": entity_id,
            "document_type": document_type,
        }, format="multipart")


class DocumentModelTests(TestCase):
    def test_str_returns_file_name(self):
        doc = Document(file_name="invoice.pdf")
        self.assertEqual(str(doc), "invoice.pdf")


class DocumentUploadAPITests(DocumentsTestBase):
    def test_upload_creates_document_with_derived_fields(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["file_name"], "contract.pdf")
        self.assertEqual(data["file_type"], "application/pdf")
        self.assertEqual(data["file_size"], len(b"hello world"))
        self.assertEqual(data["entity_type"], "project")
        self.assertEqual(data["uploaded_by"], str(self.uploader.id))
        self.assertIn("uploaded_by_name", data)
        self.assertTrue(data["file_url"].startswith("/media/"))

        # The file was actually written to storage.
        doc = Document.objects.get(pk=data["id"])
        self.assertTrue(default_storage.exists(doc.file_path))

    def test_uploaded_by_is_taken_from_the_authenticated_user_not_client_input(self):
        other = User.objects.create(
            username="other", email="other@example.com", password_hash="x",
            first_name="O", last_name="T", role="OWNER",
        )
        response = self.client.post("/api/documents/documents/", {
            "file": SimpleUploadedFile("x.txt", b"x"), "entity_type": "project",
            "entity_id": "11111111-1111-1111-1111-111111111111", "uploaded_by": str(other.id),
        }, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["uploaded_by"], str(self.uploader.id))

    def test_invalid_entity_type_is_rejected(self):
        response = self.upload(entity_type="not_a_real_entity")
        self.assertEqual(response.status_code, 400)
        self.assertIn("entity_type", response.json())

    def test_unauthenticated_upload_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.upload()
        self.assertEqual(response.status_code, 401)


class DocumentListAPITests(DocumentsTestBase):
    def test_filter_by_entity_type_and_entity_id(self):
        self.upload(entity_type="project", entity_id="11111111-1111-1111-1111-111111111111")
        self.upload(entity_type="supplier", entity_id="22222222-2222-2222-2222-222222222222")

        response = self.client.get("/api/documents/documents/?entity_type=project&entity_id=11111111-1111-1111-1111-111111111111")
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["entity_type"], "project")

    def test_filter_by_document_type(self):
        self.upload(document_type="CONTRACT")
        self.upload(document_type="RECEIPT")

        response = self.client.get("/api/documents/documents/?document_type=RECEIPT")
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["document_type"], "RECEIPT")


class DocumentUpdateAPITests(DocumentsTestBase):
    def test_document_type_is_patchable(self):
        doc_id = self.upload(document_type="CONTRACT").json()["id"]
        response = self.client.patch(f"/api/documents/documents/{doc_id}/", {"document_type": "INVOICE"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["document_type"], "INVOICE")

    def test_entity_type_cannot_be_changed(self):
        doc_id = self.upload(entity_type="project").json()["id"]
        response = self.client.patch(f"/api/documents/documents/{doc_id}/", {"entity_type": "supplier"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_put_is_not_allowed(self):
        doc_id = self.upload().json()["id"]
        response = self.client.put(f"/api/documents/documents/{doc_id}/", {"document_type": "INVOICE"}, format="json")
        self.assertEqual(response.status_code, 405)


class DocumentDestroyAPITests(DocumentsTestBase):
    def test_destroy_removes_the_stored_file_too(self):
        data = self.upload().json()
        doc = Document.objects.get(pk=data["id"])
        self.assertTrue(default_storage.exists(doc.file_path))

        response = self.client.delete(f"/api/documents/documents/{data['id']}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Document.objects.filter(pk=data["id"]).exists())
        self.assertFalse(default_storage.exists(doc.file_path))
