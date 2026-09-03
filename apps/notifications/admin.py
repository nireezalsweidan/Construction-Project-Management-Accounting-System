"""
Django admin registration for the ``notifications`` app (CPMAS-22).
"""
from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('title', 'message', 'user__username')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at',)
