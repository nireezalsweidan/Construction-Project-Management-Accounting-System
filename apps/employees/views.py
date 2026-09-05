"""
Views for the ``employees`` app -- Employee Management API.

``EmployeeViewSet`` gives authenticated system users a CRUD surface for the
employee master record plus project-assignment actions:

    /api/employees/                          GET (list), POST (create)
    /api/employees/{id}/                     GET, PATCH, PUT, DELETE
    /api/employees/{id}/projects/            GET -- assigned projects,
                                             POST -- assign to a project
    /api/employees/{id}/projects/{assignment_id}/
                                             PATCH -- update/release,
                                             DELETE -- unassign

Employees themselves are pure data records -- they get no authentication, no
login, and no user role anywhere in this app.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Employee, EmployeeProjectAssignment
from .serializers import (
    EmployeeAssignSerializer,
    EmployeeAssignmentUpdateSerializer,
    EmployeeListSerializer,
    EmployeeProjectSerializer,
    EmployeeSerializer,
)


class EmployeeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Employee.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "employee_number", "position", "department", "email"]
    ordering_fields = ["created_at", "name", "department"]
    ordering = ["name"]

    def get_serializer_class(self):
        return EmployeeListSerializer if self.action == "list" else EmployeeSerializer

    @action(detail=True, methods=["get", "post"], url_path="projects")
    def projects(self, request, pk=None):
        """GET -- assigned projects; POST -- assign this employee to one."""
        employee = self.get_object()
        if request.method == "POST":
            serializer = EmployeeAssignSerializer(
                data=request.data, context={"employee": employee}
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            assignment = EmployeeProjectAssignment.objects.create(
                employee=employee,
                project_id=data["project_id"],
                assigned_at=data["assigned_at"],
                role_on_project=data.get("role_on_project"),
            )
            return Response(
                EmployeeProjectSerializer(assignment).data,
                status=http_status.HTTP_201_CREATED,
            )
        qs = employee.project_assignments.select_related("project").order_by(
            "-assigned_at"
        )
        return Response(EmployeeProjectSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"projects/(?P<assignment_id>[^/.]+)",
    )
    def project_assignment(self, request, pk=None, assignment_id=None):
        """PATCH -- update/release an assignment; DELETE -- unassign (remove)."""
        employee = self.get_object()
        try:
            assignment = EmployeeProjectAssignment.objects.get(
                id=assignment_id, employee_id=employee.id
            )
        except EmployeeProjectAssignment.DoesNotExist:
            raise NotFound(
                {"assignment_id": "Project assignment not found for this employee."}
            )
        if request.method == "DELETE":
            assignment.delete()
            return Response(status=http_status.HTTP_204_NO_CONTENT)
        serializer = EmployeeAssignmentUpdateSerializer(
            assignment, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EmployeeProjectSerializer(assignment).data)
