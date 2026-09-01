from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def landing(request):
    return render(request, "public/landing.html")


def cedar_control(request):
    return render(request, "public/cedar_control.html")


@login_required
def dashboard(request):
    context = {
        "active_projects": 8,
        "portfolio_value": "$6.42M",
        "actual_cost": "$3.18M",
        "outstanding_ar": "$428K",
        "projects": [],
    }

    return render(request, "dashboard/overview.html", context)


@login_required
def module_page(request, module):
    """Render a shared placeholder until each module owns its page."""
    return render(
        request,
        "dashboard/module_page.html",
        {"page_title": module.replace("-", " ").title(), "active_page": module},
    )


@login_required
def suppliers(request):
    """
    Supplier Management page. Renders a dashboard view that talks to the
    /api/suppliers/ endpoints (SupplierViewSet) for supplier profile,
    purchase orders, invoices, payments, receipts, and outstanding balance.
    """
    return render(request, "dashboard/suppliers.html", {"active_page": "suppliers"})
