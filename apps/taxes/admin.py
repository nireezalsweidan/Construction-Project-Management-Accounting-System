"""
Django admin registration for the ``taxes`` app.

Exposes ``TaxRate`` in /admin/ so tax rates can be configured without a
dedicated UI while the full Tax Management ticket is still pending.
"""
from django.contrib import admin

from .models import TaxRate


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    """Admin list/search/filter configuration for TaxRate."""

    list_display = ('name', 'rate', 'tax_type', 'effective_date', 'is_active')
    list_filter = ('tax_type', 'is_active')
    search_fields = ('name', 'tax_type')
    ordering = ('name',)
