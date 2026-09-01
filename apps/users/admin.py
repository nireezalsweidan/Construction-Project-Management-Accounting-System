"""
Django admin registration for the ``users`` app.

Registers ``User`` for the built-in admin (used by the super admin) with
the fields relevant to account management: credentials/identity, role, and
activation status. Reads/writes the same ``users`` table the API manages.
"""
from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'last_login')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('username', 'password_hash', 'email')}),
        ('Personal', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Authorization', {'fields': ('role', 'is_active')}),
        ('Timestamps', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
