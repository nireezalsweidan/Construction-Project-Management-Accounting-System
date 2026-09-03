from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from projects.models import Project

from .models import (
    Client,
    ClientDocument,
    ClientInvoiceSummary,
    ClientPayment,
    get_client_financials,
)
from .serializers import (
    ClientDocumentSerializer,
    ClientInvoiceSummarySerializer,
    ClientListSerializer,
    ClientPaymentSerializer,
    ClientProjectSerializer,
    ClientSerializer,
)


class ClientViewSet(viewsets.ModelViewSet):
    """
    /api/v1/clients/                    GET (list), POST (create)
    /api/v1/clients/{id}/               GET, PATCH, PUT, DELETE
    /api/v1/clients/{id}/projects/      GET — projects where this client is the buyer
    /api/v1/clients/{id}/invoices/      GET — client invoices
    /api/v1/clients/{id}/payments/      GET — payments received from this client
    /api/v1/clients/{id}/documents/     GET — linked documents
    /api/v1/clients/{id}/balance/       GET — invoiced / paid / outstanding breakdown
    """

    permission_classes = [IsAuthenticated]
    queryset = Client.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "company_name", "email", "tax_id"]
    ordering_fields = ["created_at", "name"]
    ordering = ["name"]

    def get_serializer_class(self):
        return ClientListSerializer if self.action == "list" else ClientSerializer

    @action(detail=True, methods=["get"])
    def projects(self, request, pk=None):
        client = self.get_object()
        qs = Project.objects.filter(buyer_id=client.id)
        return Response(ClientProjectSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def invoices(self, request, pk=None):
        client = self.get_object()
        qs = ClientInvoiceSummary.objects.filter(client_id=client.id).order_by("-invoice_date")
        return Response(ClientInvoiceSummarySerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def payments(self, request, pk=None):
        client = self.get_object()
        qs = ClientPayment.objects.filter(client_id=client.id).order_by("-payment_date")
        return Response(ClientPaymentSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        client = self.get_object()
        return Response({"client_id": str(client.id), **get_client_financials(client.id)})
    @action(detail=False, methods=["get"])
    def aging(self, request):
        """
        GET /api/clients/clients/aging/?as_of=YYYY-MM-DD

        Receivables aging: bucket outstanding client invoice balances by days
        overdue from an optional as-of date (defaults to today), plus a top-
        line total. Each non-zero-balance invoice is counted in exactly one
        bucket so nothing is double-counted.
        """
        from datetime import date, datetime
        from decimal import Decimal

        from invoicing.models import ClientInvoice
        from payments.services import outstanding_balance

        as_of = date.today()
        as_of_param = request.query_params.get("as_of")
        if as_of_param:
            try:
                as_of = datetime.strptime(as_of_param, "%Y-%m-%d").date()
            except ValueError:
                as_of = date.today()

        invoices = ClientInvoice.objects.select_related("client", "project").all()

        buckets = [
            {"bucket": "current", "label": "0-30 days", "total": "0.00", "invoices": []},
            {"bucket": "overdue_31_60", "label": "31-60 days", "total": "0.00", "invoices": []},
            {"bucket": "overdue_61_90", "label": "61-90 days", "total": "0.00", "invoices": []},
            {"bucket": "overdue_90_plus", "label": "90+ days", "total": "0.00", "invoices": []},
        ]
        bucket_map = {b["bucket"]: b for b in buckets}
        grand_total = Decimal("0.00")

        for invoice in invoices:
            outstanding = Decimal(str(outstanding_balance(invoice)))
            if outstanding <= 0:
                continue
            due_date = invoice.due_date or invoice.invoice_date
            days = (as_of - due_date).days if due_date else 0
            if days <= 30:
                bucket_name = "current"
            elif days <= 60:
                bucket_name = "overdue_31_60"
            elif days <= 90:
                bucket_name = "overdue_61_90"
            else:
                bucket_name = "overdue_90_plus"

            bucket = bucket_map[bucket_name]
            bucket["total"] = Decimal(bucket["total"]) + outstanding
            grand_total += outstanding
            bucket["invoices"].append(
                {
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "client_id": str(invoice.client_id),
                    "client_name": invoice.client.name if invoice.client_id else None,
                    "project": invoice.project.name if invoice.project_id else None,
                    "invoice_date": invoice.invoice_date.isoformat(),
                    "due_date": due_date.isoformat(),
                    "days_overdue": max(days, 0),
                    "outstanding_balance": str(outstanding),
                }
            )

        return Response({"as_of": as_of.isoformat(), "total_outstanding": str(grand_total), "buckets": buckets})