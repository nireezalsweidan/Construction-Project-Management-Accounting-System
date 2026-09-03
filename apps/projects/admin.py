from django.contrib import admin

from .models import Budget, BudgetItem, ChangeOrder, Phase, Project, ProjectEmployee


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


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "sequence_number",
        "name",
        "status",
        "progress_percentage",
        "start_date",
        "end_date",
    )
    list_filter = ("status",)
    search_fields = ("name", "description")
    ordering = ("project", "sequence_number")


class BudgetItemInline(admin.TabularInline):
    model = BudgetItem
    extra = 1


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "total_budget", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)
    ordering = ("-created_at",)
    inlines = [BudgetItemInline]


@admin.register(BudgetItem)
class BudgetItemAdmin(admin.ModelAdmin):
    list_display = ("budget", "category", "phase", "budgeted_amount")
    list_filter = ("category",)


@admin.register(ChangeOrder)
class ChangeOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "amount", "status", "date")
    list_filter = ("status",)
    search_fields = ("number", "description")
    ordering = ("-date",)