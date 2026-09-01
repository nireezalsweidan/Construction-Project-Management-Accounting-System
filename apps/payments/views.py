"""
DRF viewsets for the ``payments`` app -- Accounts Receivable & Accounts
Payable slice (CPMAS-35).
"""
from rest_framework import mixins, viewsets

from .models import Payment, PaymentAllocation, Receipt
from .serializers import PaymentAllocationSerializer, PaymentSerializer, ReceiptSerializer


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Append-only ledger API for payments -- list/retrieve/create only, no
    update/destroy, same reasoning as
    inventory.views.StockMovementViewSet: a recorded payment is history,
    not something edited in place.

    Filterable by ?direction=, ?client=, ?supplier=.
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
    """

    queryset = Receipt.objects.select_related('payment').all()
    serializer_class = ReceiptSerializer
    search_fields = ['receipt_number', 'reference', 'payment__payment_number']
    ordering_fields = ['receipt_date', 'created_at']
