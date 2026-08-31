"""
Django admin registration for the ``suppliers`` app.

Exposes ``Supplier`` in /admin/ so suppliers can be created/managed without
a dedicated UI while the full Supplier Management ticket is still pending.
"""
from django.contrib import admin

from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """Admin list/search/filter configuration for Supplier."""

    list_display = ('name', 'company_name', 'phone', 'email', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'company_name', 'tax_number', 'email')
    ordering = ('name',)
