from rest_framework import serializers

from .models import Project, ProjectDocument, ProjectEmployee


class ProjectListSerializer(serializers.ModelSerializer):
    """Lightweight representation for the project list/table view."""

    class Meta:
        model = Project
        fields = [
            "id",
            "code",
            "name",
            "status",
            "project_type",
            "contract_value",
            "start_date",
            "expected_completion_date",
            "is_archived",
        ]


class ProjectEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectEmployee
        fields = ["id", "employee_id", "assigned_at", "released_at", "role_on_project"]
        read_only_fields = ["id"]


class ProjectDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectDocument
        fields = [
            "id",
            "file_name",
            "file_path",
            "file_type",
            "file_size",
            "document_type",
            "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = fields


class ProjectSerializer(serializers.ModelSerializer):
    """Full read/write representation used for create, retrieve, update."""

    employees = ProjectEmployeeSerializer(
        source="employee_assignments", many=True, read_only=True
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "code",
            "name",
            "location",
            "project_type",
            "manager_id",
            "buyer_id",
            "estimated_sale_price",
            "actual_sale_price",
            "start_date",
            "expected_completion_date",
            "actual_completion_date",
            "contract_value",
            "status",
            "description",
            "is_archived",
            "created_at",
            "updated_at",
            "employees",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "is_archived"]

    def validate_status(self, value):
        # Creating a new project — any starting status on the enum is fine
        # (in practice this will always be PLANNING, but that's a UI concern).
        if self.instance is None:
            return value

        current = self.instance.status
        if value == current:
            return value

        allowed = Project.ALLOWED_TRANSITIONS.get(current, set())
        if value not in allowed:
            allowed_display = sorted(allowed) or "none — this is a final status"
            raise serializers.ValidationError(
                f"Cannot move a project from '{current}' to '{value}'. "
                f"Allowed next status(es): {allowed_display}."
            )
        return value

    def validate(self, attrs):
        start_date = attrs.get(
            "start_date", getattr(self.instance, "start_date", None)
        )
        expected = attrs.get(
            "expected_completion_date",
            getattr(self.instance, "expected_completion_date", None),
        )
        if start_date and expected and expected < start_date:
            raise serializers.ValidationError(
                {"expected_completion_date": "Cannot be earlier than the start date."}
            )
        return attrs