"""
DRF serializers for the ``purchasing`` app -- Purchase Order Management
(CPMAS-30) and Goods Receiving (CPMAS-31) slices.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import GoodsReceipt, GoodsReceiptItem, PurchaseOrder, PurchaseOrderItem
from .services import (
    compute_item_amounts,
    quantity_received_for,
    quantity_remaining_for,
    receive_goods,
    recalculate_po_totals,
    transition_status,
)


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for PurchaseOrderItem CRUD.

    tax_amount/total_amount are read-only -- always computed by
    purchasing.services.compute_item_amounts, never accepted as input.
    Enforcing "items only editable while the parent PO is DRAFT" (BR: a
    submitted PO is a commitment) is delegated to the viewset, since it
    needs to run before create/update/destroy uniformly, not just here.
    """

    material_name = serializers.CharField(source='material.name', read_only=True)
    material_sku = serializers.CharField(source='material.sku', read_only=True)

    # BRD 5.15 "Compares Ordered vs. Received vs. Remaining quantity" --
    # quantity IS the ordered amount already; these two add the other two
    # legs of that comparison, computed from linked GoodsReceiptItems.
    quantity_received = serializers.SerializerMethodField()
    quantity_remaining = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'purchase_order', 'material', 'material_name', 'material_sku',
            'description', 'quantity', 'unit_price', 'tax_rate',
            'tax_amount', 'total_amount', 'quantity_received', 'quantity_remaining',
        ]
        read_only_fields = ['tax_amount', 'total_amount']

    def get_quantity_received(self, obj):
        return quantity_received_for(obj)

    def get_quantity_remaining(self, obj):
        return quantity_remaining_for(obj)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("quantity must be positive.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("unit_price cannot be negative.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        item = PurchaseOrderItem(**validated_data)
        compute_item_amounts(item)
        item.save()
        recalculate_po_totals(item.purchase_order)
        return item

    @transaction.atomic
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        compute_item_amounts(instance)
        instance.save()
        recalculate_po_totals(instance.purchase_order)
        return instance


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """
    Serializer for PurchaseOrder header CRUD.

    subtotal/tax_amount/total_amount/status are all read-only here:
    totals are derived from line items (see PurchaseOrderItemSerializer),
    and status changes go through the dedicated submit/approve/cancel
    actions on the viewset (see PurchaseOrderViewSet) rather than a raw
    PATCH, so an invalid transition can't be written directly.
    """

    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'supplier', 'supplier_name', 'po_number', 'order_date',
            'expected_delivery_date', 'subtotal', 'tax_amount', 'total_amount',
            'status', 'created_by', 'items', 'created_at', 'updated_at',
        ]
        read_only_fields = ['subtotal', 'tax_amount', 'total_amount', 'status', 'created_at', 'updated_at']


def apply_transition(purchase_order: PurchaseOrder, target_status: str) -> PurchaseOrder:
    """
    Shared helper used by the viewset's submit/approve/cancel actions:
    runs the transition and re-raises Django's ValidationError as DRF's,
    so an invalid transition comes back as a 400 with a clear message
    instead of a 500.
    """
    try:
        return transition_status(purchase_order, target_status)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({'status': exc.messages})


class GoodsReceiptItemSerializer(serializers.ModelSerializer):
    """
    Read/nested-write serializer for GoodsReceiptItem.

    Used two ways: read-only in GoodsReceiptItemViewSet (history/listing),
    and as a nested write-input inside GoodsReceiptSerializer.create() --
    see that class for why receipt items aren't a standalone create
    endpoint.
    """

    material_name = serializers.CharField(source='purchase_order_item.material.name', read_only=True)

    class Meta:
        model = GoodsReceiptItem
        fields = ['id', 'goods_receipt', 'purchase_order_item', 'material_name', 'quantity_received', 'notes']
        read_only_fields = ['goods_receipt']


class GoodsReceiptSerializer(serializers.ModelSerializer):
    """
    Serializer for GoodsReceipt: read (with nested items) and create only
    -- see GoodsReceiptViewSet for why update/destroy aren't offered.

    ``items`` is writable here (unlike PurchaseOrderSerializer.items,
    which is read-only): a receipt's items, the stock movements they
    generate, and the parent PO's resulting status must all be created
    together in one call -- see purchasing.services.receive_goods, which
    this delegates to entirely rather than duplicating that logic in
    .create().

    ``recorded_by`` is a write-only input, not a model field: the schema
    gives GoodsReceipt no users.User column at all (only the
    Employee-typed received_by, intentionally not modeled -- see the
    module docstring on purchasing.models), but the StockMovement rows
    this generates require one. See PurchaseOrder.created_by for the same
    kind of explicit-input pattern elsewhere in this app.
    """

    items = GoodsReceiptItemSerializer(many=True, write_only=True)
    items_detail = GoodsReceiptItemSerializer(source='items', many=True, read_only=True)
    recorded_by = serializers.UUIDField(write_only=True)
    purchase_order_number = serializers.CharField(source='purchase_order.po_number', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'purchase_order', 'purchase_order_number', 'receipt_number',
            'received_date', 'warehouse', 'warehouse_name', 'notes',
            'items', 'items_detail', 'recorded_by', 'created_at',
        ]

    @transaction.atomic
    def create(self, validated_data):
        # users.User is a managed=False reflection with no DRF-visible
        # queryset wired up here (Users/RBAC is a separate ticket) -- so
        # recorded_by is taken as a bare UUID and resolved directly,
        # rather than a PrimaryKeyRelatedField that would need its own
        # queryset configuration for a model this app doesn't own.
        from users.models import User
        try:
            movement_user = User.objects.get(pk=validated_data.pop('recorded_by'))
        except User.DoesNotExist:
            raise serializers.ValidationError({'recorded_by': "No such user."})

        items_data = validated_data.pop('items')
        purchase_order = validated_data.pop('purchase_order')

        try:
            return receive_goods(purchase_order, validated_data, items_data, movement_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'detail': exc.messages})
