"""
Django admin registration for the ``payments`` app -- Accounts
Receivable & Accounts Payable slice (CPMAS-35).
"""
from django.contrib import admin

from .models import Payment, PaymentAllocation, Receipt


class PaymentAllocationInline(admin.TabularInline):
    """Inline view of a payment's allocations on the Payment admin page."""

    model = PaymentAllocation
    extra = 0
    autocomplete_fields = ('client_invoice', 'supplier_invoice')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_number', 'direction', 'amount', 'payment_date', 'client', 'supplier')
    list_filter = ('direction', 'payment_method')
    search_fields = ('payment_number', 'reference', 'client__name', 'supplier__name')
    autocomplete_fields = ('client', 'supplier')
    readonly_fields = ('created_at',)
    inlines = [PaymentAllocationInline]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ('payment', 'client_invoice', 'supplier_invoice', 'allocated_amount')
    search_fields = ('payment__payment_number',)
    autocomplete_fields = ('payment', 'client_invoice', 'supplier_invoice')


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment', 'amount', 'receipt_date')
    search_fields = ('receipt_number', 'payment__payment_number')
    autocomplete_fields = ('payment',)
    readonly_fields = ('created_at',)
