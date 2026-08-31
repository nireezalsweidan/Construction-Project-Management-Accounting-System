from django.contrib import admin

from .models import Project, ProjectEmployee


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "status",
        "project_type",
        "contract_value",
        "start_date",
        "is_archived",
    )
    list_filter = ("status", "project_type", "is_archived")
    search_fields = ("code", "name", "location")
    ordering = ("-created_at",)


@admin.register(ProjectEmployee)
class ProjectEmployeeAdmin(admin.ModelAdmin):
    list_display = ("project", "employee_id", "role_on_project", "assigned_at", "released_at")
    list_filter = ("released_at",)