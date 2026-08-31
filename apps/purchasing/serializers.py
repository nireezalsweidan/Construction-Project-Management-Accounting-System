"""
DRF serializers for the ``purchasing`` app -- Purchase Order Management
slice (CPMAS-30).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import PurchaseOrder, PurchaseOrderItem
from .services import compute_item_amounts, recalculate_po_totals, transition_status


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

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'purchase_order', 'material', 'material_name', 'material_sku',
            'description', 'quantity', 'unit_price', 'tax_rate',
            'tax_amount', 'total_amount',
        ]
        read_only_fields = ['tax_amount', 'total_amount']

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
