"""
DRF viewsets for the ``purchasing`` app -- Purchase Order Management
(CPMAS-30) and Goods Receiving (CPMAS-31) slices.
"""
from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from construction.filtering import filter_date_range

from .models import GoodsReceipt, GoodsReceiptItem, PurchaseOrder, PurchaseOrderItem
from .serializers import (
    GoodsReceiptItemSerializer,
    GoodsReceiptSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderSerializer,
    apply_transition,
)
from .services import recalculate_po_totals


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """
    CRUD + status-transition API for purchase order headers.

    Header fields (supplier, po_number, dates) stay editable via the
    normal update route while a PO is DRAFT; status itself is changed
    only through the submit/approve/cancel actions below, never a raw
    field PATCH (enforced by PurchaseOrderSerializer marking status
    read-only).
    """

    queryset = PurchaseOrder.objects.select_related('supplier').prefetch_related('items').all()
    serializer_class = PurchaseOrderSerializer
    search_fields = ['po_number', 'supplier__name']
    ordering_fields = ['order_date', 'total_amount', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        supplier_id = params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        status_param = params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param.upper())

        queryset = filter_date_range(queryset, params, 'order_date')

        return queryset

    def _require_draft(self, purchase_order):
        # Header edits are only meaningful while a PO hasn't been
        # submitted yet -- once submitted it's a commitment to the
        # supplier, matching the same "items locked past DRAFT" rule
        # applied on PurchaseOrderItemViewSet.
        if purchase_order.status != PurchaseOrder.Status.DRAFT:
            raise PermissionDenied(
                f"Cannot edit a purchase order once it is {purchase_order.get_status_display()}."
            )

    def perform_update(self, serializer):
        self._require_draft(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._require_draft(instance)
        instance.delete()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """POST /api/purchasing/purchase-orders/{id}/submit/ -- DRAFT -> SUBMITTED."""
        po = apply_transition(self.get_object(), PurchaseOrder.Status.SUBMITTED)
        return Response(self.get_serializer(po).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """POST /api/purchasing/purchase-orders/{id}/approve/ -- SUBMITTED -> APPROVED."""
        po = apply_transition(self.get_object(), PurchaseOrder.Status.APPROVED)
        return Response(self.get_serializer(po).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """POST /api/purchasing/purchase-orders/{id}/cancel/ -- DRAFT/SUBMITTED/APPROVED -> CANCELLED."""
        po = apply_transition(self.get_object(), PurchaseOrder.Status.CANCELLED)
        return Response(self.get_serializer(po).data)


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    """
    CRUD API for purchase order line items.

    Filterable by ?purchase_order=<uuid>. Create/update/destroy are all
    blocked once the parent PO has left DRAFT status -- a submitted PO's
    line items are a commitment already sent to the supplier, so editing
    them silently afterward would make the PO no longer reflect what was
    actually submitted/approved.
    """

    queryset = PurchaseOrderItem.objects.select_related('material', 'tax_rate', 'purchase_order').all()
    serializer_class = PurchaseOrderItemSerializer
    search_fields = ['material__name', 'material__sku']

    def get_queryset(self):
        queryset = super().get_queryset()
        purchase_order_id = self.request.query_params.get('purchase_order')
        if purchase_order_id:
            queryset = queryset.filter(purchase_order_id=purchase_order_id)
        return queryset

    def _require_draft(self, purchase_order):
        if purchase_order.status != PurchaseOrder.Status.DRAFT:
            raise PermissionDenied(
                f"Cannot modify items on a purchase order once it is {purchase_order.get_status_display()}."
            )

    def perform_create(self, serializer):
        self._require_draft(serializer.validated_data['purchase_order'])
        serializer.save()

    def perform_update(self, serializer):
        self._require_draft(serializer.instance.purchase_order)
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        self._require_draft(instance.purchase_order)
        purchase_order = instance.purchase_order
        instance.delete()
        recalculate_po_totals(purchase_order)


class GoodsReceiptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                           mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Append-only API for goods receipts.

    list/retrieve/create only -- no update/destroy. All the real work
    (validating received quantities, creating items, applying stock
    movements, recalculating the PO's status) happens in
    GoodsReceiptSerializer.create() -> purchasing.services.receive_goods;
    this viewset just wires it up and adds ?purchase_order= filtering.
    """

    queryset = GoodsReceipt.objects.select_related('purchase_order', 'warehouse').prefetch_related('items').all()
    serializer_class = GoodsReceiptSerializer
    search_fields = ['receipt_number', 'purchase_order__po_number']

    def get_queryset(self):
        queryset = super().get_queryset()
        purchase_order_id = self.request.query_params.get('purchase_order')
        if purchase_order_id:
            queryset = queryset.filter(purchase_order_id=purchase_order_id)
        return queryset


class GoodsReceiptItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only history API for goods receipt items.

    Items are only ever created as part of a GoodsReceipt (see
    GoodsReceiptViewSet) -- this exists purely so receiving history can
    be queried/filtered independently, e.g. ?purchase_order_item=<uuid>
    to see everything received against one PO line (BRD 5.15's
    Ordered/Received/Remaining comparison, at the individual-receipt
    level rather than just the aggregate exposed on
    PurchaseOrderItemSerializer).
    """

    queryset = GoodsReceiptItem.objects.select_related('goods_receipt', 'purchase_order_item__material').all()
    serializer_class = GoodsReceiptItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        po_item_id = self.request.query_params.get('purchase_order_item')
        if po_item_id:
            queryset = queryset.filter(purchase_order_item_id=po_item_id)
        return queryset
