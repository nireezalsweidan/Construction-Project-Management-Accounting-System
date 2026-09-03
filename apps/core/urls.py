from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path("", views.landing, name="landing"),
    path("cedar-control/", views.cedar_control, name="cedar-control"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("projects/", views.projects_page, name="projects"),
    path("projects/<uuid:pk>/", views.project_detail, name="project-detail"),
    path("approvals/", views.approvals_page, name="approvals"),
    path("partners/", views.partners_page, name="partners"),
    path("procurement/", views.procurement_page, name="procurement"),
    path("inventory/", views.inventory_page, name="inventory"),
    path("workforce/", views.workforce_page, name="workforce"),
    path("invoices/", views.invoices_page, name="invoices"),
    path("payments/", views.payments_page, name="payments"),
    path("accounting/", views.accounting_page, name="accounting"),
    path("expenses/", views.expenses_page, name="expenses"),
    path("reports/", views.reports_page, name="reports"),
    path("settings/", views.settings_page, name="settings"),
    path("dashboard/<slug:module>/", views.module_page, name="module-page"),
    path("suppliers/", views.suppliers, name="suppliers"),
    path("contractors/", views.contractors, name="contractors"),
    path("employees/", views.employees, name="employees"),
    path("receipts/", views.receipts_page, name="receipts"),
    path("settings/company/", views.company_settings, name="company-settings"),
]
