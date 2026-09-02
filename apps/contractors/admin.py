"""
Django admin registration for the ``contractors`` app.

Exposes ``Contractor`` in /admin/ consistent with the Supplier/Client admin
registration.
"""
from django.contrib import admin

from .models import Contractor


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    """Admin list/search/filter configuration for Contractor."""

    list_display = ("name", "company_name", "phone", "email", "status")
    list_filter = ("status",)
    search_fields = ("name", "company_name", "email", "specialization")
    ordering = ("name",)