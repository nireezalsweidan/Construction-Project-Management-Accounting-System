"""
DRF viewsets for the ``payments`` app -- Accounts Receivable & Accounts
Payable (CPMAS-35) and Receipts (CPMAS-21) slices.
"""
from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action

from construction.filtering import filter_date_range

from .models import Payment, PaymentAllocation, Receipt
from .pdf import render_receipt_pdf
from .serializers import PaymentAllocationSerializer, PaymentSerializer, ReceiptSerializer


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Append-only ledger API for payments -- list/retrieve/create only, no
    update/destroy, same reasoning as
    inventory.views.StockMovementViewSet: a recorded payment is history,
    not something edited in place.

    Filterable by ?direction=, ?client=, ?supplier=, ?date_from=/?date_to=.
    """

    queryset = Payment.objects.select_related('client', 'supplier', 'created_by').prefetch_related('allocations').all()
    serializer_class = PaymentSerializer
    search_fields = ['payment_number', 'reference', 'client__name', 'supplier__name']
    ordering_fields = ['payment_date', 'amount', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        direction = params.get('direction')
        if direction:
            queryset = queryset.filter(direction=direction.upper())

        client_id = params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        supplier_id = params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        queryset = filter_date_range(queryset, params, 'payment_date')

        return queryset


class PaymentAllocationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                                mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Append-only ledger API for payment allocations -- list/retrieve/
    create only. Creating one is how a payment gets applied to an
    invoice and how that invoice's status advances (see
    payments.services.allocate_payment); there is no "unallocate" -- a
    mistaken allocation is corrected the same way a mis-posted
    accounting entry is, with an explicit offsetting record, not an
    in-place edit.

    Filterable by ?payment=, ?client_invoice=, ?supplier_invoice=.
    """

    queryset = PaymentAllocation.objects.select_related('payment', 'client_invoice', 'supplier_invoice').all()
    serializer_class = PaymentAllocationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        payment_id = params.get('payment')
        if payment_id:
            queryset = queryset.filter(payment_id=payment_id)

        client_invoice_id = params.get('client_invoice')
        if client_invoice_id:
            queryset = queryset.filter(client_invoice_id=client_invoice_id)

        supplier_invoice_id = params.get('supplier_invoice')
        if supplier_invoice_id:
            queryset = queryset.filter(supplier_invoice_id=supplier_invoice_id)

        return queryset


class ReceiptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Append-only API for receipts -- list/retrieve/create only, same
    immutability reasoning as PaymentViewSet.

    Filterable by ?client=/?supplier=/?payment= (BRD 5.3/5.4: a client's
    or supplier's profile should be able to list their receipts) -- all
    three filter through the receipt's payment, since Receipt itself has
    no client/supplier column of its own.
    """

    queryset = Receipt.objects.select_related('payment', 'payment__client', 'payment__supplier').all()
    serializer_class = ReceiptSerializer
    search_fields = ['receipt_number', 'reference', 'payment__payment_number']
    ordering_fields = ['receipt_date', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        payment_id = params.get('payment')
        if payment_id:
            queryset = queryset.filter(payment_id=payment_id)

        client_id = params.get('client')
        if client_id:
            queryset = queryset.filter(payment__client_id=client_id)

        supplier_id = params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(payment__supplier_id=supplier_id)

        queryset = filter_date_range(queryset, params, 'receipt_date')

        return queryset

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        GET /api/payments/receipts/{id}/download/ -- BRD 5.19
        "printable/downloadable receipts": returns the receipt as a PDF
        file attachment.
        """
        receipt = self.get_object()
        pdf_bytes = render_receipt_pdf(receipt)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{receipt.receipt_number}.pdf"'
        return response
