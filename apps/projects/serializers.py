from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from clients.models import Client

from .models import Budget, BudgetItem, ChangeOrder, Phase, Project, ProjectDocument, ProjectEmployee


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
    # Exposed as "project_id" (matching the physical column exactly) even
    # though the model field backing it is a real ForeignKey named `project`
    # — `source="project"` points this JSON key at that relation, so writes
    # still go through proper FK validation (the id must belong to an
    # existing Project) while the API surface matches the DB 1:1.
    project_id = serializers.PrimaryKeyRelatedField(
        source="project", queryset=Project.objects.all()
    )

    class Meta:
        model = Phase
        fields = [
            "id",
            "project_id",
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

    # Exposed as "buyer_id" (matching the physical `projects.buyer_id`
    # column) — see PhaseSerializer.project_id above for why this is a
    # PrimaryKeyRelatedField with an explicit source rather than just
    # listing "buyer" in Meta.fields.
    buyer_id = serializers.PrimaryKeyRelatedField(
        source="buyer", queryset=Client.objects.all(), allow_null=True, required=False
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


class BudgetItemSerializer(serializers.ModelSerializer):
    # "budget_id" / "phase_id" — same PrimaryKeyRelatedField + source
    # pattern as above, matching budget_items.budget_id / .phase_id exactly.
    budget_id = serializers.PrimaryKeyRelatedField(
        source="budget", queryset=Budget.objects.all()
    )
    phase_id = serializers.PrimaryKeyRelatedField(
        source="phase", queryset=Phase.objects.all(), allow_null=True, required=False
    )

    # Overrides the model field's auto-generated ChoiceField. The column is
    # plain VARCHAR(50) at the DB level (see BudgetItem's docstring) — the
    # model's `choices` are just the five quick-pick suggestions the UI
    # offers, not a real constraint, so a caller can name a category those
    # five don't cover (e.g. "Permits") and it's accepted as-is.
    category = serializers.CharField(max_length=50)

    class Meta:
        model = BudgetItem
        fields = ["id", "budget_id", "phase_id", "category", "description", "budgeted_amount"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        budget = attrs.get("budget", getattr(self.instance, "budget", None))
        amount = attrs.get(
            "budgeted_amount", getattr(self.instance, "budgeted_amount", None)
        )

        if budget is None or amount is None:
            return attrs

        # Only new items are blocked by a locked budget — editing an
        # existing line on one is a separate concern this UI doesn't
        # expose yet.
        if self.instance is None and budget.status not in (
            Budget.STATUS_DRAFT,
            Budget.STATUS_REVISED,
        ):
            raise serializers.ValidationError(
                {
                    "budget_id": (
                        f"Cannot add items to a budget in '{budget.status}' status — "
                        "only DRAFT or REVISED budgets accept new items."
                    )
                }
            )

        # BR: item amounts can't push the budget past what was approved
        # for it in total.
        existing = BudgetItem.objects.filter(budget=budget)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        allocated = existing.aggregate(total=Sum("budgeted_amount"))["total"] or Decimal("0.00")

        if allocated + amount > budget.total_budget:
            remaining = budget.total_budget - allocated
            raise serializers.ValidationError(
                {
                    "budgeted_amount": (
                        f"This would exceed the budget's total of {budget.total_budget}. "
                        f"Remaining unallocated: {remaining}."
                    )
                }
            )

        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    """Full read/write representation, including itemized categories."""

    items = BudgetItemSerializer(many=True, read_only=True)

    # "project_id" — matches project_budgets.project_id exactly.
    project_id = serializers.PrimaryKeyRelatedField(
        source="project", queryset=Project.objects.all()
    )

    class Meta:
        model = Budget
        fields = [
            "id",
            "project_id",
            "name",
            "total_budget",
            "status",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_status(self, value):
        if self.instance is None:
            return value

        current = self.instance.status
        if value == current:
            return value

        allowed = Budget.ALLOWED_TRANSITIONS.get(current, set())
        if value not in allowed:
            allowed_display = sorted(allowed) or "none — this is a final status"
            raise serializers.ValidationError(
                f"Cannot move a budget from '{current}' to '{value}'. "
                f"Allowed next status(es): {allowed_display}."
            )
        return value


class ChangeOrderSerializer(serializers.ModelSerializer):
    """
    status/approved_by are read-only here on purpose — every status change
    goes through the approve/reject/cancel actions on the viewset (same
    convention as expenses.services.transition_status), never a raw PATCH,
    since approval also has to atomically update Project.contract_value.
    """

    project_id = serializers.PrimaryKeyRelatedField(
        source="project", queryset=Project.objects.all()
    )

    class Meta:
        model = ChangeOrder
        fields = [
            "id",
            "project_id",
            "number",
            "description",
            "reason",
            "amount",
            "requested_by",
            "approved_by",
            "date",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "approved_by", "created_at", "updated_at"]

    def validate(self, attrs):
        # App-level uniqueness only — the DB column has no unique
        # constraint on `number`, so this is enforced here, not in Postgres.
        number = attrs.get("number", getattr(self.instance, "number", None))
        project = attrs.get("project", getattr(self.instance, "project", None))
        if number and project:
            qs = ChangeOrder.objects.filter(project=project, number=number)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"number": "A change order with this number already exists on this project."}
                )
        return attrs