"""
DRF serializers for the ``payments`` app -- Accounts Receivable &
Accounts Payable slice (CPMAS-35).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Payment, PaymentAllocation, Receipt
from .services import allocate_payment, unallocated_amount

# Renders a SerializerMethodField Decimal the same way a real
# DecimalField would (a "0.00"-style JSON string) -- see
# PaymentSerializer.get_unallocated_amount.
DECIMAL_FIELD = serializers.DecimalField(max_digits=18, decimal_places=2)


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for Payment CRUD.

    Read/create only at the viewset level -- see PaymentViewSet -- since
    a recorded payment is a ledger entry (same immutability reasoning as
    StockMovement).
    """

    client_name = serializers.CharField(source='client.name', read_only=True, default=None)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default=None)
    unallocated_amount = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id', 'payment_number', 'payment_date', 'amount', 'direction',
            'payment_method', 'client', 'client_name', 'supplier', 'supplier_name',
            'reference', 'notes', 'created_by', 'unallocated_amount', 'created_at',
        ]

    def get_unallocated_amount(self, obj):
        return DECIMAL_FIELD.to_representation(unallocated_amount(obj))

    def validate(self, attrs):
        direction = attrs.get('direction')
        client = attrs.get('client')
        supplier = attrs.get('supplier')

        if direction == Payment.Direction.INCOMING and not client:
            raise serializers.ValidationError("An INCOMING payment must specify a client.")
        if direction == Payment.Direction.OUTGOING and not supplier:
            raise serializers.ValidationError("An OUTGOING payment must specify a supplier.")

        return attrs


class PaymentAllocationSerializer(serializers.ModelSerializer):
    """
    Serializer for PaymentAllocation. Create-only at the viewset level
    (append-only, same reasoning as Payment) -- .create() delegates to
    payments.services.allocate_payment, which is the single place an
    allocation gets created AND an invoice's status advances as a
    result, rather than a plain ModelSerializer.create().
    """

    class Meta:
        model = PaymentAllocation
        fields = ['id', 'payment', 'client_invoice', 'supplier_invoice', 'allocated_amount']

    def validate(self, attrs):
        # Mirrors the live database's CHECK constraint (defense in
        # depth, same pattern as TransactionLine's mirrored CHECKs).
        client_invoice = attrs.get('client_invoice')
        supplier_invoice = attrs.get('supplier_invoice')
        if bool(client_invoice) == bool(supplier_invoice):
            raise serializers.ValidationError(
                "Exactly one of client_invoice or supplier_invoice must be set."
            )
        return attrs

    def create(self, validated_data):
        payment = validated_data['payment']
        invoice = validated_data.get('client_invoice') or validated_data.get('supplier_invoice')
        amount = validated_data['allocated_amount']
        try:
            return allocate_payment(payment, invoice, amount)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'detail': exc.messages})


class ReceiptSerializer(serializers.ModelSerializer):
    """
    Serializer for Receipt. Create-only at the viewset level (proof of
    receipt, immutable once issued).
    """

    payment_number = serializers.CharField(source='payment.payment_number', read_only=True)

    class Meta:
        model = Receipt
        fields = ['id', 'payment', 'payment_number', 'receipt_number', 'receipt_date', 'amount', 'reference', 'created_at']

    def validate_payment(self, payment):
        if payment.direction != Payment.Direction.INCOMING:
            raise serializers.ValidationError("A receipt can only be issued for an INCOMING payment.")
        if hasattr(payment, 'receipt'):
            raise serializers.ValidationError("This payment already has a receipt.")
        return payment
