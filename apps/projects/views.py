from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from construction.filtering import filter_date_range

from .models import Phase, Project, ProjectDocument
from .serializers import (
    PhaseSerializer,
    ProjectDocumentSerializer,
    ProjectEmployeeSerializer,
    ProjectListSerializer,
    ProjectSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    """
    /api/projects/                      GET (list), POST (create)
    /api/projects/{id}/                 GET, PATCH, PUT, DELETE
    /api/projects/{id}/archive/         POST
    /api/projects/{id}/unarchive/       POST
    /api/projects/{id}/employees/       GET (list assignments), POST (assign)
    /api/projects/{id}/release-employee/ POST  {"employee_id": "..."}
    /api/projects/{id}/documents/       GET (linked documents)
    """

    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "project_type", "is_archived"]
    search_fields = ["name", "code", "location"]
    ordering_fields = ["created_at", "start_date", "contract_value", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Project.objects.all()
        params = self.request.query_params
        # Archived projects are hidden by default — pass ?include_archived=true
        # or filter explicitly with ?is_archived=true to see them.
        if "is_archived" not in params and params.get("include_archived") != "true":
            qs = qs.filter(is_archived=False)

        client_id = params.get("client")
        if client_id:
            qs = qs.filter(buyer_id=client_id)

        qs = filter_date_range(qs, params, "start_date")

        return qs

    def get_serializer_class(self):
        return ProjectListSerializer if self.action == "list" else ProjectSerializer

    def perform_destroy(self, instance):
        # Hard delete is intentionally not exposed for a financial system —
        # archiving is the supported way to retire a project.
        raise NotImplementedError(
            "Projects cannot be deleted. Use POST /archive/ instead."
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        project = self.get_object()
        project.is_archived = True
        project.save(update_fields=["is_archived", "updated_at"])
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        project = self.get_object()
        project.is_archived = False
        project.save(update_fields=["is_archived", "updated_at"])
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=["get", "post"])
    def employees(self, request, pk=None):
        project = self.get_object()

        if request.method == "GET":
            qs = project.employee_assignments.filter(released_at__isnull=True)
            return Response(ProjectEmployeeSerializer(qs, many=True).data)

        serializer = ProjectEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, assigned_at=request.data.get("assigned_at") or timezone.localdate())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="release-employee")
    def release_employee(self, request, pk=None):
        project = self.get_object()
        employee_id = request.data.get("employee_id")
        if not employee_id:
            return Response(
                {"employee_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = project.employee_assignments.filter(
            employee_id=employee_id, released_at__isnull=True
        ).first()
        if assignment is None:
            return Response(
                {"detail": "No active assignment found for this employee on this project."},
                status=status.HTTP_404_NOT_FOUND,
            )

        assignment.released_at = request.data.get("released_at") or timezone.localdate()
        assignment.save(update_fields=["released_at"])
        return Response(ProjectEmployeeSerializer(assignment).data)

    @action(detail=True, methods=["get"])
    def documents(self, request, pk=None):
        project = self.get_object()
        qs = ProjectDocument.objects.filter(entity_type="project", entity_id=project.id)
        return Response(ProjectDocumentSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="phases")
    def phases(self, request, pk=None):
        """Convenience read: same data as GET /phases/?project={id}."""
        project = self.get_object()
        qs = project.phases.all()
        return Response(PhaseSerializer(qs, many=True).data)


class PhaseViewSet(viewsets.ModelViewSet):
    """
    Project Planning (Phases).

    /api/phases/?project={id}        GET (list, filterable by project), POST (create)
    /api/phases/{id}/                GET, PATCH, PUT, DELETE
    /api/phases/{id}/complete/       POST — shortcut: status=COMPLETED, progress=100
    /api/phases/reorder/             POST — bulk-update sequence_number
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PhaseSerializer
    queryset = Phase.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["project", "status", "responsible_emp_id"]
    search_fields = ["name", "description"]
    ordering_fields = ["sequence_number", "start_date", "end_date"]
    ordering = ["project", "sequence_number"]

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        phase = self.get_object()
        serializer = self.get_serializer(
            phase, data={"status": Phase.STATUS_COMPLETED}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """
        Body: {"phases": [{"id": "...", "sequence_number": 1}, {"id": "...", "sequence_number": 2}]}
        All-or-nothing: every id must belong to an existing phase, or nothing is changed.
        """
        items = request.data.get("phases")
        if not isinstance(items, list) or not items:
            return Response(
                {"phases": "Expected a non-empty list of {id, sequence_number}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = [str(item.get("id")) for item in items]
        phases_by_id = {str(p.id): p for p in Phase.objects.filter(id__in=ids)}
        missing = [i for i in ids if i not in phases_by_id]
        if missing:
            return Response(
                {"detail": f"Unknown phase id(s): {missing}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            updated = []
            for item in items:
                phase = phases_by_id[str(item["id"])]
                phase.sequence_number = item["sequence_number"]
                phase.save(update_fields=["sequence_number", "updated_at"])
                updated.append(phase)

        updated.sort(key=lambda p: p.sequence_number)
        return Response(PhaseSerializer(updated, many=True).data)