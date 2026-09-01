from decimal import Decimal

from rest_framework import serializers

from .models import Phase, Project, ProjectDocument, ProjectEmployee


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


class PhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Phase
        fields = [
            "id",
            "project",
            "name",
            "description",
            "start_date",
            "end_date",
            "responsible_emp_id",
            "status",
            "progress_percentage",
            "sequence_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_status(self, value):
        if self.instance is None:
            return value  # creating — any starting status is a UI concern

        current = self.instance.status
        if value == current:
            return value

        allowed = Phase.ALLOWED_TRANSITIONS.get(current, set())
        if value not in allowed:
            allowed_display = sorted(allowed) or "none — this is a final status"
            raise serializers.ValidationError(
                f"Cannot move a phase from '{current}' to '{value}'. "
                f"Allowed next status(es): {allowed_display}."
            )
        return value

    def validate(self, attrs):
        start_date = attrs.get(
            "start_date", getattr(self.instance, "start_date", None)
        )
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "Cannot be earlier than the start date."}
            )

        # Marking a phase COMPLETED implies 100% progress, unless the
        # request already specified a progress value explicitly.
        if attrs.get("status") == Phase.STATUS_COMPLETED and "progress_percentage" not in attrs:
            attrs["progress_percentage"] = Decimal("100.00")

        return attrs


class ProjectSerializer(serializers.ModelSerializer):
    """Full read/write representation used for create, retrieve, update."""

    employees = ProjectEmployeeSerializer(
        source="employee_assignments", many=True, read_only=True
    )
    phases = PhaseSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "code",
            "name",
            "location",
            "project_type",
            "manager_id",
            "buyer",
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
            "phases",
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