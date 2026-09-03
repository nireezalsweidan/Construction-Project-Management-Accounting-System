from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from company.models import DEFAULT_CURRENCY_UUID, CompanyProfile


def landing(request):
    return render(request, "public/landing.html")


def cedar_control(request):
    return render(request, "public/cedar_control.html")


@login_required
def dashboard(request):
    context = {
        "active_page": "overview",
        "active_projects": 8,
        "portfolio_value": "$6.42M",
        "actual_cost": "$3.18M",
        "outstanding_ar": "$428K",
        "projects": [],
    }

    return render(request, "dashboard/overview.html", context)


def _dashboard_page(request, template_name, active_page, **context):
    """Render one of the dedicated v3 dashboard screens."""
    return render(
        request,
        f"dashboard/{template_name}.html",
        {"active_page": active_page, **context},
    )


@login_required
def projects_page(request):
    return _dashboard_page(request, "projects", "projects", projects=[])


@login_required
def project_detail(request, pk):
    return _dashboard_page(request, "project_detail", "projects", project={"pk": pk})


@login_required
def approvals_page(request):
    return _dashboard_page(request, "approvals", "approvals", approvals=[])


@login_required
def partners_page(request):
    return _dashboard_page(request, "partners", "partners", partners=[])


@login_required
def procurement_page(request):
    return _dashboard_page(request, "procurement", "procurement")


@login_required
def inventory_page(request):
    return _dashboard_page(request, "inventory", "inventory", inventory_items=[])


@login_required
def workforce_page(request):
    return _dashboard_page(request, "workforce", "workforce", workforce=[])


@login_required
def invoices_page(request):
    return _dashboard_page(request, "invoices", "invoices", invoices=[])


@login_required
def payments_page(request):
    return _dashboard_page(request, "payments", "payments", payments=[])


@login_required
def accounting_page(request):
    """
    Accounting / Financial Transactions page (CPMAS-34). Renders a dashboard
    view that talks to the /api/accounting/ endpoints (AccountViewSet,
    FinancialTransactionViewSet, TransactionLineViewSet) for listing,
    creating, editing, posting, and voiding journal entries.
    """
    return _dashboard_page(request, "accounting", "accounting")


@login_required
def expenses_page(request):
    return _dashboard_page(request, "expenses", "expenses", expenses=[])


@login_required
def reports_page(request):
    return _dashboard_page(request, "reports", "reports")


@login_required
def settings_page(request):
    return _dashboard_page(request, "settings", "settings")


@login_required
def module_page(request, module):
    """Render a shared placeholder until each module owns its page."""
    return render(
        request,
        "dashboard/module_page.html",
        {"page_title": module.replace("-", " ").title(), "active_page": module},
    )


@login_required
def receipts_page(request):
    """
    Receipts page (CPMAS-58/CPMAS-21). Renders a dashboard view that
    talks to /api/payments/receipts/ (ReceiptViewSet) for listing,
    search, date-range filtering, and PDF download.
    """
    return render(request, "dashboard/receipts.html", {"active_page": "receipts"})


@login_required
def suppliers(request):
    """
    Supplier Management page. Renders a dashboard view that talks to the
    /api/suppliers/ endpoints (SupplierViewSet) for supplier profile,
    purchase orders, invoices, payments, and outstanding balance.
    """
    return render(request, "dashboard/suppliers.html", {"active_page": "suppliers"})


@login_required
def contractors(request):
    """
    Contractor Management page. Renders a dashboard view that talks to the
    /api/contractors/ endpoints (ContractorViewSet) for contractor profile,
    project assignments, and linked documents.
    """
    return render(request, "dashboard/contractors.html", {"active_page": "contractors"})


@login_required
def employees(request):
    """
    Employee Management page. Renders a dashboard view that talks to the
    /api/employees/ endpoints (EmployeeViewSet) for employee profiles,
    project assignments, and labor information.
    """
    return render(request, "dashboard/employees.html", {"active_page": "employees"})


def _company_profile_form_value(request, key, required=False):
    value = request.POST.get(key, "").strip()
    if required and not value:
        return ""
    return value or None


@login_required
def company_settings(request):
    """
    Administration -> Company settings page.

    Single system-wide company identity backed by the existing
    ``company_details`` table (CompanyProfile, managed=False). GET renders
    the form prefilled from the most recently updated row; POST saves the
    editable identity fields. ``currency`` is deliberately never written
    here -- the system currency is fixed at USD and there is no currencies
    table in the schema to choose from.
    """
    profile = CompanyProfile.objects.order_by("-updated_at").first()
    error = None

    if request.method == "POST":
        form_name = _company_profile_form_value(request, "name")
        if not form_name:
            error = "Company name is required."
        else:
            data = {
                "name": form_name,
                "registration_number": _company_profile_form_value(request, "registration_number"),
                "address": _company_profile_form_value(request, "address"),
                "phone": _company_profile_form_value(request, "phone"),
                "email": _company_profile_form_value(request, "email"),
                "website": _company_profile_form_value(request, "website"),
                "tax_information": _company_profile_form_value(request, "tax_information"),
            }
            logo_file = request.FILES.get("logo")
            if logo_file:
                data["logo"] = logo_file.name

            if profile is None:
                profile = CompanyProfile.objects.create(currency=DEFAULT_CURRENCY_UUID, **data)
            else:
                for field, value in data.items():
                    setattr(profile, field, value)
                profile.save(update_fields=list(data.keys()) + ["updated_at"])
            return redirect(f"{reverse('company-settings')}?saved=1")

    return render(
        request,
        "dashboard/company_settings.html",
        {"active_page": "settings", "profile": profile, "saved": request.GET.get("saved") == "1", "error": error},
    )
