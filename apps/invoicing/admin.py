"""
Django admin registration for the ``invoicing`` app -- Supplier Invoices
slice (CPMAS-32).
"""
from django.contrib import admin

from .models import SupplierInvoice, SupplierInvoiceItem


class SupplierInvoiceItemInline(admin.TabularInline):
    """Inline editing of line items on the SupplierInvoice admin page."""

    model = SupplierInvoiceItem
    extra = 0
    autocomplete_fields = ('material', 'tax_rate')
    readonly_fields = ('tax_amount', 'total_amount')


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    """
    Admin view for SupplierInvoice. subtotal/tax_amount/total_amount are
    read-only -- derived from line items (see invoicing.services), never
    hand-edited, even in the admin.
    """

    list_display = ('invoice_number', 'supplier', 'status', 'invoice_date', 'due_date', 'total_amount')
    list_filter = ('status', 'supplier')
    search_fields = ('invoice_number', 'supplier__name')
    autocomplete_fields = ('supplier', 'purchase_order')
    readonly_fields = ('subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at')
    inlines = [SupplierInvoiceItemInline]


@admin.register(SupplierInvoiceItem)
class SupplierInvoiceItemAdmin(admin.ModelAdmin):
    """Standalone admin view for SupplierInvoiceItem (in addition to the inline above)."""

    list_display = ('supplier_invoice', 'description', 'quantity', 'unit_price', 'total_amount')
    list_filter = ('supplier_invoice__status',)
    search_fields = ('supplier_invoice__invoice_number', 'description', 'material__name')
    autocomplete_fields = ('supplier_invoice', 'material', 'tax_rate')
    readonly_fields = ('tax_amount', 'total_amount')
