"""
Django admin registration for the ``purchasing`` app -- Purchase Order
Management slice (CPMAS-30).
"""
from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderItemInline(admin.TabularInline):
    """Inline editing of line items on the PurchaseOrder admin page."""

    model = PurchaseOrderItem
    extra = 0
    autocomplete_fields = ('material', 'tax_rate')
    readonly_fields = ('tax_amount', 'total_amount')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    """
    Admin view for PurchaseOrder. subtotal/tax_amount/total_amount are
    read-only here too -- they're derived from line items (see
    purchasing.services), never hand-edited, even in the admin.
    """

    list_display = ('po_number', 'supplier', 'status', 'order_date', 'total_amount')
    list_filter = ('status', 'supplier')
    search_fields = ('po_number', 'supplier__name')
    # 'created_by' is deliberately excluded from autocomplete_fields: it
    # FKs to users.User, which has no registered ModelAdmin here (Users/
    # RBAC is a separate ticket) -- Django's admin checks require the
    # target model to be registered with search_fields for autocomplete.
    autocomplete_fields = ('supplier',)
    readonly_fields = ('subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at')
    inlines = [PurchaseOrderItemInline]


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    """Standalone admin view for PurchaseOrderItem (in addition to the inline above)."""

    list_display = ('purchase_order', 'material', 'quantity', 'unit_price', 'total_amount')
    list_filter = ('purchase_order__status',)
    search_fields = ('purchase_order__po_number', 'material__name', 'material__sku')
    autocomplete_fields = ('purchase_order', 'material', 'tax_rate')
    readonly_fields = ('tax_amount', 'total_amount')
