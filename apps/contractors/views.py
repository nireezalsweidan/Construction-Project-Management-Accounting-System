"""
Views for the ``contractors`` app -- Contractor Management API.

``ContractorViewSet`` gives authenticated system users a CRUD surface for
the contractor master record plus project-assignment and read-only document
actions:

    /api/contractors/                          GET (list), POST (create)
    /api/contractors/{id}/                     GET, PATCH, PUT, DELETE
    /api/contractors/{id}/projects/            GET -- assigned projects,
                                               POST -- assign to a project
    /api/contractors/{id}/projects/{assignment_id}/
                                               PATCH -- update/release,
                                               DELETE -- unassign
    /api/contractors/{id}/documents/           GET -- linked documents

Contractors themselves are pure data records -- they get no authentication,
no login, and no user role anywhere in this app.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Contractor, ContractorDocument, ContractorProjectAssignment
from .serializers import (
    ContractorAssignSerializer,
    ContractorAssignmentUpdateSerializer,
    ContractorDocumentSerializer,
    ContractorListSerializer,
    ContractorProjectSerializer,
    ContractorSerializer,
)


class ContractorViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Contractor.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "company_name", "email", "specialization"]
    ordering_fields = ["created_at", "name"]
    ordering = ["name"]

    def get_serializer_class(self):
        return ContractorListSerializer if self.action == "list" else ContractorSerializer

    @action(detail=True, methods=["get", "post"], url_path="projects")
    def projects(self, request, pk=None):
        """GET -- assigned projects; POST -- assign this contractor to one."""
        contractor = self.get_object()
        if request.method == "POST":
            serializer = ContractorAssignSerializer(
                data=request.data, context={"contractor": contractor}
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            assignment = ContractorProjectAssignment.objects.create(
                contractor=contractor,
                project_id=data["project_id"],
                contract_amount=data.get("contract_amount"),
                assigned_at=data["assigned_at"],
                released_at=data.get("released_at"),
                status=data.get("status", ContractorProjectAssignment.Status.ASSIGNED),
            )
            return Response(
                ContractorProjectSerializer(assignment).data,
                status=http_status.HTTP_201_CREATED,
            )
        qs = contractor.project_assignments.select_related("project").order_by(
            "-assigned_at"
        )
        return Response(ContractorProjectSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"projects/(?P<assignment_id>[^/.]+)",
    )
    def project_assignment(self, request, pk=None, assignment_id=None):
        """PATCH -- update/release an assignment; DELETE -- unassign (remove)."""
        contractor = self.get_object()
        try:
            assignment = ContractorProjectAssignment.objects.get(
                id=assignment_id, contractor_id=contractor.id
            )
        except ContractorProjectAssignment.DoesNotExist:
            raise NotFound(
                {"assignment_id": "Project assignment not found for this contractor."}
            )
        if request.method == "DELETE":
            assignment.delete()
            return Response(status=http_status.HTTP_204_NO_CONTENT)
        serializer = ContractorAssignmentUpdateSerializer(
            assignment, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ContractorProjectSerializer(assignment).data)

    @action(detail=True, methods=["get"])
    def documents(self, request, pk=None):
        """GET -- metadata for the documents linked to this contractor."""
        contractor = self.get_object()
        qs = ContractorDocument.objects.filter(
            entity_type="contractor", entity_id=contractor.id
        ).order_by("-uploaded_at")
        return Response(ContractorDocumentSerializer(qs, many=True).data)