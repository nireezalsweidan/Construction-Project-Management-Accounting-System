"""
Django admin registration for the ``inventory`` app -- Material Management
slice (CPMAS-28).
"""
from django.contrib import admin

from .models import Material, MaterialCategory


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
