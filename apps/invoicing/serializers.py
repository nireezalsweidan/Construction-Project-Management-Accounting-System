"""
DRF serializers for the ``invoicing`` app -- Supplier Invoices slice
(CPMAS-32).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import SupplierInvoice, SupplierInvoiceItem
from .services import compute_item_amounts, recalculate_invoice_totals, transition_status


class SupplierInvoiceItemSerializer(serializers.ModelSerializer):
    """
    Serializer for SupplierInvoiceItem CRUD.

    Unlike PurchaseOrderItemSerializer, tax_amount/total_amount are NOT
    read-only here: invoicing.services.compute_item_amounts only derives
    them when quantity+unit_price are both present -- for a flat-charge
    line (neither set), total_amount IS the direct input, so the
    serializer has to let it through to validated_data for
    compute_item_amounts to see it. compute_item_amounts still has the
    final say either way: it overwrites both fields on the
    quantity*price path, and only preserves the caller's values as a
    fallback on the flat-charge path.

    "Items only editable while the parent invoice is DRAFT" is enforced
    in the viewset, same reasoning as PurchaseOrderItemViewSet (CPMAS-30).
    """

    material_name = serializers.CharField(source='material.name', read_only=True, default=None)

    class Meta:
        model = SupplierInvoiceItem
        fields = [
            'id', 'supplier_invoice', 'material', 'material_name', 'description',
            'quantity', 'unit_price', 'tax_rate', 'tax_amount', 'total_amount',
        ]

    def validate(self, attrs):
        # Both-or-neither: a line with only one of quantity/unit_price
        # set is ambiguous (what would the other side of the
        # multiplication be?) -- reject rather than silently falling
        # into the flat-charge path with half the data ignored.
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        unit_price = attrs.get('unit_price', getattr(self.instance, 'unit_price', None))
        if (quantity is None) != (unit_price is None):
            raise serializers.ValidationError(
                "quantity and unit_price must both be set, or both left blank for a flat-charge line."
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        item = SupplierInvoiceItem(**validated_data)
        compute_item_amounts(item)
        item.save()
        recalculate_invoice_totals(item.supplier_invoice)
        return item

    @transaction.atomic
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        compute_item_amounts(instance)
        instance.save()
        recalculate_invoice_totals(instance.supplier_invoice)
        return instance


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for SupplierInvoice header CRUD.

    subtotal/tax_amount/total_amount/status are all read-only: totals
    are derived from line items, and status changes go through the
    mark_sent/cancel actions on the viewset rather than a raw PATCH.
    """

    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    purchase_order_number = serializers.CharField(source='purchase_order.po_number', read_only=True, default=None)
    items = SupplierInvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            'id', 'supplier', 'supplier_name', 'purchase_order', 'purchase_order_number',
            'invoice_number', 'invoice_date', 'due_date', 'subtotal', 'tax_amount',
            'total_amount', 'status', 'items', 'created_at', 'updated_at',
        ]
        read_only_fields = ['subtotal', 'tax_amount', 'total_amount', 'status', 'created_at', 'updated_at']


def apply_transition(invoice: SupplierInvoice, target_status: str) -> SupplierInvoice:
    """
    Shared helper used by the viewset's mark_sent/cancel actions: runs
    the transition and re-raises Django's ValidationError as DRF's, so
    an invalid transition comes back as a 400 instead of a 500.
    """
    try:
        return transition_status(invoice, target_status)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({'status': exc.messages})
