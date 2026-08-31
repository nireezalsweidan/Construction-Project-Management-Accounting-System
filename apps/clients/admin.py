from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "company_name", "phone", "email", "tax_id")
    search_fields = ("name", "company_name", "email", "tax_id")
    ordering = ("name",)