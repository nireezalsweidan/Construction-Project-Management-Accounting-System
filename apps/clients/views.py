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
    def documents(self, request, pk=None):
        client = self.get_object()
        qs = ClientDocument.objects.filter(entity_type="client", entity_id=client.id)
        return Response(ClientDocumentSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        client = self.get_object()
        return Response({"client_id": str(client.id), **get_client_financials(client.id)})