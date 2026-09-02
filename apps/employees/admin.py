"""
Django admin registration for the ``employees`` app.

Exposes ``Employee`` in /admin/ consistent with the Supplier/Client/Contractor
admin registration.
"""
from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Admin list/search/filter configuration for Employee."""

    list_display = (
        "name",
        "employee_number",
        "position",
        "department",
        "employment_status",
        "labor_rate",
    )
    list_filter = ("employment_status", "department")
    search_fields = ("name", "employee_number", "email", "position")
    ordering = ("name",)
