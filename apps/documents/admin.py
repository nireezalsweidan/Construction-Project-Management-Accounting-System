"""
Django admin registration for the ``documents`` app -- Document Management
(CPMAS-25).
"""
from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'entity_type', 'entity_id', 'document_type', 'uploaded_by', 'uploaded_at')
    list_filter = ('entity_type', 'document_type')
    search_fields = ('file_name', 'entity_id')
    readonly_fields = ('file_path', 'file_type', 'file_size', 'uploaded_at')
