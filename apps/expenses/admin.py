"""
Django admin registration for the ``expenses`` app -- Expense
Management slice (CPMAS-33).
"""
from django.contrib import admin

from .models import Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    """Admin list/search configuration for ExpenseCategory."""

    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """Admin list/search/filter configuration for Expense."""

    list_display = ('description', 'project', 'category', 'status', 'expense_date', 'amount')
    list_filter = ('status', 'category', 'payment_method')
    search_fields = ('description', 'project__name', 'project__code')
    # 'created_by' excluded from autocomplete_fields: it FKs to users.User,
    # which has no registered ModelAdmin here (Users/RBAC is a separate
    # ticket) -- Django's admin checks require the target model to be
    # registered with search_fields for autocomplete.
    autocomplete_fields = ('project', 'category', 'supplier')
    readonly_fields = ('created_at', 'updated_at')
