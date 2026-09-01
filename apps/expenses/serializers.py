"""
DRF serializers for the ``expenses`` app -- Expense Management slice
(CPMAS-33).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Expense, ExpenseCategory
from .services import transition_status


class ExpenseCategorySerializer(serializers.ModelSerializer):
    """Serializer for ExpenseCategory CRUD operations."""

    account_code = serializers.CharField(source='account.code', read_only=True, default=None)

    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name', 'description', 'account', 'account_code']


class ExpenseSerializer(serializers.ModelSerializer):
    """
    Serializer for Expense CRUD operations.

    ``status`` is read-only: changes go through the approve/mark_paid/
    reject actions on the viewset (see ExpenseViewSet), never a raw
    PATCH, so an invalid transition can't be written directly.
    """

    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default=None)

    class Meta:
        model = Expense
        fields = [
            'id', 'project', 'project_name', 'project_code', 'category', 'category_name',
            'supplier', 'supplier_name', 'expense_date', 'description', 'amount',
            'tax_amount', 'payment_method', 'status', 'notes', 'created_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']

    def validate_amount(self, value):
        # Schema types amount as DECIMAL(18,2) NOT NULL but doesn't
        # itself forbid non-positive values -- an expense of $0 or less
        # isn't a real recorded cost.
        if value <= 0:
            raise serializers.ValidationError("amount must be positive.")
        return value

    def validate_tax_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("tax_amount cannot be negative.")
        return value


def apply_transition(expense: Expense, target_status: str) -> Expense:
    """
    Shared helper used by the viewset's approve/mark_paid/reject actions:
    runs the transition and re-raises Django's ValidationError as DRF's,
    so an invalid transition comes back as a 400 instead of a 500.
    """
    try:
        return transition_status(expense, target_status)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({'status': exc.messages})
