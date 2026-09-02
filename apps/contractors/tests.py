"""
Tests for the ``contractors`` app -- Contractor Management API.

All contractor models are ``managed=False``, so tests materialize the
``contractors`` / ``project_contractors`` / ``documents`` tables via
``WithContractorsTableMixin`` and the ``projects`` table via
``WithProjectsTableMixin`` (exactly the pattern already used by the
suppliers/expenses/payments suites).
"""
import uuid

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from clients.testing import WithClientsTableMixin
from projects.models import Project
from projects.testing import WithProjectsTableMixin

from .models import Contractor, ContractorDocument, ContractorProjectAssignment
from .testing import WithContractorsTableMixin


def make_contractor(**overrides):
    """Build + save a Contractor row (requires the contractors table)."""
    defaults = {
        "name": "Skyline Roofing",
        "company_name": "Skyline Roofing Ltd",
        "phone": "555-0100",
        "email": "contact@skyline.example.com",
        "contract_details": "Subcontract for roof works.",
        "specialization": "Roofing",
        "payment_terms": "NET 30",
        "rate": "125.00",
    }
    defaults.update(overrides)
    return Contractor.objects.create(**defaults)


def make_project(**overrides):
    """Build + save a Project row (requires the projects table)."""
    defaults = {
        "name": "Riverside Villas",
        "code": f"PRJ-{uuid.uuid4().hex[:8].upper()}",
        "project_type": "MULTI_UNIT",
        "start_date": "2026-01-15",
        "contract_value": "2500000.00",
    }
    defaults.update(overrides)
    return Project.objects.create(**defaults)


class ContractorModelTests(
    WithProjectsTableMixin, WithClientsTableMixin, WithContractorsTableMixin, TestCase
):
    def test_create_with_required_fields_only(self):
        contractor = Contractor.objects.create(name="AC Electrical")
        self.assertEqual(contractor.status, Contractor.Status.ACTIVE)
        self.assertIsNone(contractor.rate)
        self.assertEqual(str(contractor), "AC Electrical")

    def test_timestamps_are_set_on_create(self):
        contractor = make_contractor()
        self.assertIsNotNone(contractor.created_at)
        self.assertIsNotNone(contractor.updated_at)

    def test_assignment_holds_schema_fields(self):
        project = make_project()
        contractor = make_contractor()
        assignment = ContractorProjectAssignment.objects.create(
            contractor=contractor,
            project=project,
            contract_amount="9500.00",
            assigned_at="2026-02-01",
        )
        self.assertEqual(assignment.status, ContractorProjectAssignment.Status.ASSIGNED)
        self.assertIsNone(assignment.released_at)
        self.assertEqual(assignment.project_id, project.id)
        self.assertEqual(assignment.contractor_id, contractor.id)


class ContractorAPITestBase(
    WithProjectsTableMixin, WithClientsTableMixin, WithContractorsTableMixin, TestCase
):
    """Authenticated API client plus a project + contractor fixture."""

    def setUp(self):
        self.django_user = DjangoUser.objects.create_user(
            username="owner", password="pass12345"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.django_user)
        self.project = make_project()
        self.contractor = make_contractor()

    def post_contractor(self, data):
        return self.client.post("/api/contractors/", data, format="json")

    def assign_project(self, contractor=None, project=None, **overrides):
        contractor = contractor or self.contractor
        project = project or self.project
        payload = {"project_id": str(project.id), "assigned_at": "2026-02-01"}
        payload.update(overrides)
        return self.client.post(
            f"/api/contractors/{contractor.id}/projects/", payload, format="json"
        )

    def assignment_url(self, contractor, assignment_id):
        return f"/api/contractors/{contractor.id}/projects/{assignment_id}/"


class ContractorAPIAuthTests(ContractorAPITestBase):
    def test_list_requires_authentication(self):
        anonymous = APIClient()
        self.assertEqual(
            anonymous.get("/api/contractors/").status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_create_requires_authentication(self):
        anonymous = APIClient()
        response = anonymous.post(
            "/api/contractors/", {"name": "No Auth Co"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_requires_authentication(self):
        anonymous = APIClient()
        response = anonymous.get(f"/api/contractors/{self.contractor.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ContractorListCreateTests(ContractorAPITestBase):
    def test_create_contractor(self):
        response = self.post_contractor(
            {
                "name": "Apex Concrete",
                "company_name": "Apex Concrete Works",
                "email": "info@apex.example.com",
                "specialization": "Concrete",
                "payment_terms": "NET 30",
                "rate": "150.00",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.data
        self.assertEqual(body["name"], "Apex Concrete")
        self.assertEqual(body["company_name"], "Apex Concrete Works")
        self.assertEqual(body["specialization"], "Concrete")
        self.assertEqual(body["payment_terms"], "NET 30")
        self.assertEqual(body["rate"], "150.00")
        self.assertEqual(body["status"], Contractor.Status.ACTIVE)
        self.assertIn("id", body)
        self.assertIn("created_at", body)

    def test_name_is_required(self):
        response = self.post_contractor({"company_name": "No Name Co"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_invalid_email_rejected(self):
        response = self.post_contractor(
            {"name": "Bad Email Co", "email": "not-an-email"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_negative_rate_rejected(self):
        response = self.post_contractor({"name": "Bad Rate Co", "rate": "-10.00"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rate", response.data)

    def test_invalid_status_rejected(self):
        response = self.post_contractor({"name": "Bad Status Co", "status": "GONE"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_list_contractors(self):
        second = make_contractor(name="B Composites", company_name="B Composites LLC")
        response = self.client.get("/api/contractors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        ids = {row["id"] for row in results}
        self.assertIn(str(self.contractor.id), ids)
        self.assertIn(str(second.id), ids)

    def test_search_contractors_by_name(self):
        make_contractor(
            name="Bravo Welding",
            company_name="Bravo Welding LLC",
            email="contact@bravo.example.com",
            specialization="Steel",
        )
        response = self.client.get("/api/contractors/?search=Skyline")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["Skyline Roofing"])

    def test_retrieve_contractor_detail(self):
        response = self.client.get(f"/api/contractors/{self.contractor.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.data
        self.assertEqual(body["contract_details"], "Subcontract for roof works.")
        self.assertEqual(body["rate"], "125.00")
        self.assertEqual(body["status"], Contractor.Status.ACTIVE)
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_update_contractor(self):
        response = self.client.patch(
            f"/api/contractors/{self.contractor.id}/",
            {"payment_terms": "NET 60", "status": "INACTIVE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_terms"], "NET 60")
        self.assertEqual(response.data["status"], "INACTIVE")

    def test_delete_contractor_without_assignments(self):
        contractor = make_contractor(name="Disposable Co")
        response = self.client.delete(f"/api/contractors/{contractor.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        get = self.client.get(f"/api/contractors/{contractor.id}/")
        self.assertEqual(get.status_code, status.HTTP_404_NOT_FOUND)


class ContractorProjectAssignmentTests(ContractorAPITestBase):
    def test_list_assignments_empty(self):
        response = self.client.get(f"/api/contractors/{self.contractor.id}/projects/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_assign_contractor_to_project(self):
        response = self.assign_project(
            contract_amount="12000.00", status="IN_PROGRESS"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.data
        self.assertEqual(body["project"]["id"], str(self.project.id))
        self.assertEqual(body["project"]["code"], self.project.code)
        self.assertEqual(body["project"]["name"], self.project.name)
        self.assertEqual(body["contract_amount"], "12000.00")
        self.assertEqual(body["assigned_at"], "2026-02-01")
        self.assertIsNone(body["released_at"])
        self.assertEqual(body["status"], "IN_PROGRESS")
        self.assertEqual(ContractorProjectAssignment.objects.count(), 1)

    def test_assignment_default_status_is_assigned(self):
        response = self.assign_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], ContractorProjectAssignment.Status.ASSIGNED)

    def test_assignment_requires_assigned_at(self):
        response = self.assign_project(assigned_at=None)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_assignment_rejected(self):
        self.assertEqual(self.assign_project().status_code, status.HTTP_201_CREATED)
        response = self.assign_project()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ContractorProjectAssignment.objects.count(), 1)

    def test_invalid_assignment_status_rejected(self):
        response = self.assign_project(status="SIDELINED")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_contract_amount_rejected(self):
        response = self.assign_project(contract_amount="-5.00")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_release_before_assignment_rejected(self):
        response = self.assign_project(
            assigned_at="2026-04-01", released_at="2026-03-01"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("released_at", response.data)

    def test_release_update_assignment(self):
        created = self.assign_project()
        assignment_id = created.data["id"]
        response = self.client.patch(
            self.assignment_url(self.contractor, assignment_id),
            {"status": "RELEASED", "released_at": "2026-05-01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "RELEASED")
        self.assertEqual(response.data["released_at"], "2026-05-01")

    def test_update_release_before_assignment_rejected(self):
        created = self.assign_project(assigned_at="2026-04-01")
        assignment_id = created.data["id"]
        response = self.client.patch(
            self.assignment_url(self.contractor, assignment_id),
            {"released_at": "2026-03-01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("released_at", response.data)

    def test_unassign_deletes_assignment(self):
        created = self.assign_project()
        assignment_id = created.data["id"]
        response = self.client.delete(
            self.assignment_url(self.contractor, assignment_id)
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ContractorProjectAssignment.objects.count(), 0)
        listing = self.client.get(f"/api/contractors/{self.contractor.id}/projects/")
        self.assertEqual(listing.data, [])

    def test_assignment_scoped_to_contractor(self):
        other = make_contractor(name="Other Co")
        created = self.assign_project(contractor=other)
        assignment_id = created.data["id"]
        # Trying to touch another contractor's assignment 404s.
        response = self.client.delete(
            self.assignment_url(self.contractor, assignment_id)
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ContractorProjectAssignment.objects.count(), 1)

    def test_unassign_unknown_assignment_404(self):
        response = self.client.delete(
            self.assignment_url(self.contractor, uuid.uuid4())
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ContractorDocumentTests(ContractorAPITestBase):
    def setUp(self):
        super().setUp()
        self.uploader_uid = uuid.uuid4()
        self.other_contractor = make_contractor(name="Other Roofing")
        self.own_doc = ContractorDocument.objects.create(
            uploaded_by=self.uploader_uid,
            file_name="contract.pdf",
            file_path="/uploads/contract.pdf",
            file_type="application/pdf",
            file_size=2048,
            document_type="contract",
            entity_type="contractor",
            entity_id=self.contractor.id,
        )
        ContractorDocument.objects.create(
            uploaded_by=self.uploader_uid,
            file_name="other.pdf",
            file_path="/uploads/other.pdf",
            entity_type="contractor",
            entity_id=self.other_contractor.id,
        )
        ContractorDocument.objects.create(
            uploaded_by=self.uploader_uid,
            file_name="client.pdf",
            file_path="/uploads/client.pdf",
            entity_type="client",
            entity_id=self.contractor.id,
        )

    def test_returns_only_own_contractor_documents(self):
        response = self.client.get(f"/api/contractors/{self.contractor.id}/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        body = response.data[0]
        self.assertEqual(body["file_name"], "contract.pdf")
        self.assertEqual(body["document_type"], "contract")
        self.assertEqual(body["file_size"], 2048)
        self.assertEqual(body["uploaded_by"], str(self.uploader_uid))

    def test_other_contractor_has_different_documents(self):
        response = self.client.get(
            f"/api/contractors/{self.other_contractor.id}/documents/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["file_name"], "other.pdf")

    def test_documents_are_read_only(self):
        response = self.client.post(
            f"/api/contractors/{self.contractor.id}/documents/",
            {"file_name": "x.pdf"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ContractorPageRenderTests(TestCase):
    """The dashboard Contractors page is server-rendered HTML + client-side JS
    that speaks to the /api/contractors API. These tests confirm the page
    renders and the view is auth-protected; the JS itself is exercised in
    the browser against the API endpoints (covered by the API tests above)."""

    def test_page_requires_login(self):
        response = self.client.get("/contractors/")
        self.assertEqual(response.status_code, 302)  # redirect to login

    def test_page_renders_for_authenticated_user(self):
        user = DjangoUser.objects.create_user(username="owner", password="pass12345")
        self.client.force_login(user)
        response = self.client.get("/contractors/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Contractors", content)
        self.assertIn("contractors.js", content)
        self.assertIn("contractors.css", content)
        self.assertIn("site-exact.css", content)
        self.assertIn("v3-fixes.css", content)
        self.assertIn("data-contractor-rows", content)
        self.assertIn("module-stat-grid", content)
        self.assertIn('data-metric="assignments"', content)
        self.assertIn("data-contractor-dialog", content)