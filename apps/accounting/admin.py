"""
Django admin registration for the ``accounting`` app -- Accounting /
Financial Transactions slice (CPMAS-34).
"""
from django.contrib import admin

from .models import Account, FinancialTransaction, TransactionLine


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Admin list/search/filter configuration for Account."""

    list_display = ('code', 'name', 'account_type', 'parent_account', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')
    autocomplete_fields = ('parent_account',)
    ordering = ('code',)


class TransactionLineInline(admin.TabularInline):
    """Inline editing of lines on the FinancialTransaction admin page."""

    model = TransactionLine
    extra = 0
    autocomplete_fields = ('account', 'project')


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    """
    Admin view for FinancialTransaction. status/posted_at are read-only
    -- changed only through accounting.services.post_transaction/
    void_transaction, never hand-edited, even in the admin.
    """

    list_display = ('transaction_number', 'transaction_date', 'status', 'description')
    list_filter = ('status',)
    search_fields = ('transaction_number', 'description', 'reference')
    # 'created_by' excluded from autocomplete_fields: it FKs to
    # users.User, which has no registered ModelAdmin here (Users/RBAC is
    # a separate ticket).
    autocomplete_fields = ('project', 'client', 'supplier')
    readonly_fields = ('status', 'posted_at', 'created_at', 'updated_at')
    inlines = [TransactionLineInline]


@admin.register(TransactionLine)
class TransactionLineAdmin(admin.ModelAdmin):
    """Standalone admin view for TransactionLine (in addition to the inline above)."""

    list_display = ('transaction', 'account', 'debit', 'credit', 'project')
    list_filter = ('transaction__status',)
    search_fields = ('transaction__transaction_number', 'account__code', 'account__name')
    autocomplete_fields = ('transaction', 'account', 'project')
