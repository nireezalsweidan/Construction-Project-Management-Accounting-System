"""
DRF viewset for the ``documents`` app -- Document Management (CPMAS-25).
"""
from django.core.files.storage import default_storage
from rest_framework import mixins, viewsets
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.CreateModelMixin, mixins.UpdateModelMixin,
                       mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """
    /api/documents/documents/                GET (list, ?entity_type=&entity_id=&document_type=), POST (upload)
    /api/documents/documents/{id}/           GET, PATCH (document_type only -- see DocumentSerializer), DELETE

    No raw file replacement on update -- swapping the underlying file is a
    delete + re-upload (see DocumentSerializer's read_only_fields), so a
    document's stored path never changes out from under something that
    already linked to it.
    """

    queryset = Document.objects.select_related('uploaded_by').all()
    serializer_class = DocumentSerializer
    # Multipart for the upload itself; JSON for the metadata-only PATCH
    # (document_type) an upload doesn't need a form re-submission for.
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    search_fields = ['file_name', 'document_type']

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        entity_type = params.get('entity_type')
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)

        entity_id = params.get('entity_id')
        if entity_id:
            queryset = queryset.filter(entity_id=entity_id)

        document_type = params.get('document_type')
        if document_type:
            queryset = queryset.filter(document_type=document_type)

        return queryset

    def perform_create(self, serializer):
        uploaded_file = serializer.validated_data.pop('file')
        # file_path stores the storage-relative path (e.g. "documents/foo.pdf"),
        # not a served URL -- DocumentSerializer.file_url computes that for
        # callers, keeping this column a plain reflection of where the file
        # actually lives under MEDIA_ROOT.
        stored_path = default_storage.save(f'documents/{uploaded_file.name}', uploaded_file)
        serializer.save(
            uploaded_by=self.request.user,
            file_name=uploaded_file.name,
            file_path=stored_path,
            file_type=uploaded_file.content_type or '',
            file_size=uploaded_file.size,
        )

    def update(self, request, *args, **kwargs):
        # PUT would require re-sending `file` (required on create) just to
        # patch document_type -- there's no full-replace operation here, so
        # only PATCH (partial=True) is supported. See DocumentSerializer's
        # docstring: swapping the file is delete + re-upload, not an update.
        if not kwargs.get('partial', False):
            raise MethodNotAllowed('PUT')
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        # Best-effort: remove the stored file too, but a missing/already-gone
        # file on disk shouldn't block deleting the (still-authoritative) row.
        default_storage.delete(instance.file_path)
        instance.delete()
