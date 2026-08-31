"""
Django admin registration for the ``inventory`` app -- Material Management
(CPMAS-28) and Inventory & Warehouse Management (CPMAS-29) slices.
"""
from django.contrib import admin

from .models import Material, MaterialCategory, Stock, StockMovement, Warehouse


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    """Admin list/search configuration for MaterialCategory."""

    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    """Admin list/search/filter configuration for Material."""

    list_display = (
        'name', 'sku', 'category', 'unit', 'standard_cost',
        'minimum_stock_level', 'is_active',
    )
    list_filter = ('category', 'is_active', 'tax_rate', 'default_supplier')
    search_fields = ('name', 'sku')
    ordering = ('name',)
    autocomplete_fields = ('category', 'tax_rate', 'default_supplier')


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    """Admin list/search configuration for Warehouse."""

    list_display = ('name', 'location', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    """
    Admin view for Stock. Deliberately read-only (no add/change/delete
    permission) -- quantity must only ever change via StockMovement, per
    BR 12.6, so the admin shouldn't offer a way around that either.
    """

    list_display = ('material', 'warehouse', 'quantity', 'updated_at')
    list_filter = ('warehouse',)
    search_fields = ('material__name', 'material__sku', 'warehouse__name')
    autocomplete_fields = ('warehouse', 'material')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """
    Admin view for StockMovement. Add is allowed (goes through the model's
    normal save(), which does NOT auto-apply to Stock -- see
    inventory.services -- so movements entered here still need the API/
    service call to actually move stock). Change/delete are disabled: this
    is an append-only ledger.
    """

    list_display = (
        'movement_type', 'material', 'warehouse', 'quantity',
        'movement_date', 'user', 'reference',
    )
    list_filter = ('movement_type', 'warehouse')
    search_fields = ('material__name', 'material__sku', 'reference')
    autocomplete_fields = ('material', 'warehouse')
    ordering = ('-movement_date',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
