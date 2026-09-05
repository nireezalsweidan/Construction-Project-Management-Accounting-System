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
        read_only_fields = ['id', 'created_by', 'created_at']

    def validate_payment_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_payment_method(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def get_unallocated_amount(self, obj):
        return DECIMAL_FIELD.to_representation(unallocated_amount(obj))

    def validate(self, attrs):
        direction = attrs.get('direction')
        client = attrs.get('client')
        supplier = attrs.get('supplier')

        amount = attrs.get('amount')
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({'amount': "Payment amount must be positive."})

        if direction == Payment.Direction.INCOMING and (not client or supplier):
            raise serializers.ValidationError(
                "An INCOMING payment must specify a client and must not specify a supplier."
            )
        if direction == Payment.Direction.OUTGOING and (not supplier or client):
            raise serializers.ValidationError(
                "An OUTGOING payment must specify a supplier and must not specify a client."
            )

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
        if attrs.get('allocated_amount') is not None and attrs['allocated_amount'] <= 0:
            raise serializers.ValidationError({'allocated_amount': "Allocation amount must be positive."})
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

    client_name/supplier_name/payment_method are read-only, derived
    through the receipt's payment -- BRD 5.19 lists "Client/supplier"
    and "Payment method" as receipt fields, but the schema's receipts
    table has no such columns of its own (a receipt is always one-to-
    one with a payment, so nothing would be gained by duplicating them
    here). Currency is in BRD 5.19 too but is out of scope for this
    version (BRD 3.2 lists multi-currency as a future enhancement).
    """

    payment_number = serializers.CharField(source='payment.payment_number', read_only=True)
    client_name = serializers.CharField(source='payment.client.name', read_only=True, default=None)
    supplier_name = serializers.CharField(source='payment.supplier.name', read_only=True, default=None)
    payment_method = serializers.CharField(source='payment.payment_method', read_only=True)

    class Meta:
        model = Receipt
        fields = [
            'id', 'payment', 'payment_number', 'client_name', 'supplier_name', 'payment_method',
            'receipt_number', 'receipt_date', 'amount', 'reference', 'created_at',
        ]

    def validate_payment(self, payment):
        if payment.direction != Payment.Direction.INCOMING:
            raise serializers.ValidationError("A receipt can only be issued for an INCOMING payment.")
        if hasattr(payment, 'receipt'):
            raise serializers.ValidationError("This payment already has a receipt.")
        return payment

    def validate(self, attrs):
        payment = attrs.get('payment')
        amount = attrs.get('amount')
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({'amount': "Receipt amount must be positive."})
        if payment is not None and amount is not None and amount != payment.amount:
            raise serializers.ValidationError(
                {'amount': "Receipt amount must exactly equal the payment amount."}
            )
        return attrs
