"""
Django admin registration for the ``payments`` app -- Accounts
Receivable & Accounts Payable slice (CPMAS-35).
"""
from django.contrib import admin

from .models import Payment, PaymentAllocation, Receipt


class ImmutablePaymentAdmin(admin.ModelAdmin):
    """Keep financial records inspectable without bypassing API services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ('GET', 'HEAD', 'OPTIONS')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(Payment)
class PaymentAdmin(ImmutablePaymentAdmin):
    list_display = ('payment_number', 'direction', 'amount', 'payment_date', 'client', 'supplier')
    list_filter = ('direction', 'payment_method')
    search_fields = ('payment_number', 'reference', 'client__name', 'supplier__name')
    autocomplete_fields = ('client', 'supplier')


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(ImmutablePaymentAdmin):
    list_display = ('payment', 'client_invoice', 'supplier_invoice', 'allocated_amount')
    search_fields = ('payment__payment_number',)
    autocomplete_fields = ('payment', 'client_invoice', 'supplier_invoice')


@admin.register(Receipt)
class ReceiptAdmin(ImmutablePaymentAdmin):
    list_display = ('receipt_number', 'payment', 'amount', 'receipt_date')
    search_fields = ('receipt_number', 'payment__payment_number')
    autocomplete_fields = ('payment',)
