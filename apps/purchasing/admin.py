"""
Django admin registration for the ``purchasing`` app -- Purchase Order
Management (CPMAS-30) and Goods Receiving (CPMAS-31) slices.
"""
from django.contrib import admin

from .models import GoodsReceipt, GoodsReceiptItem, PurchaseOrder, PurchaseOrderItem


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


class GoodsReceiptItemInline(admin.TabularInline):
    """Inline display of line items on the GoodsReceipt admin page."""

    model = GoodsReceiptItem
    extra = 0
    autocomplete_fields = ('purchase_order_item',)


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    """
    Admin view for GoodsReceipt. Read-only end to end (see
    has_change_permission/has_delete_permission below) -- a receipt is an
    immutable ledger entry once created (see the model docstring), and
    creating one outside purchasing.services.receive_goods would skip the
    stock-movement/PO-status side effects entirely, so add isn't offered
    here either.
    """

    list_display = ('receipt_number', 'purchase_order', 'warehouse', 'received_date')
    list_filter = ('warehouse',)
    search_fields = ('receipt_number', 'purchase_order__po_number')
    autocomplete_fields = ('purchase_order', 'warehouse')
    inlines = [GoodsReceiptItemInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(admin.ModelAdmin):
    """Standalone read-only admin view for GoodsReceiptItem (see GoodsReceiptAdmin's docstring)."""

    list_display = ('goods_receipt', 'purchase_order_item', 'quantity_received')
    search_fields = ('goods_receipt__receipt_number',)
    autocomplete_fields = ('goods_receipt', 'purchase_order_item')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
