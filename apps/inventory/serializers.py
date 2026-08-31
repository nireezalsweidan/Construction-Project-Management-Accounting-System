"""
DRF serializers for the ``inventory`` app -- Material Management
(CPMAS-28) and Inventory & Warehouse Management (CPMAS-29) slices.
"""
from django.db import transaction
from rest_framework import serializers

from .models import Material, MaterialCategory, Stock, StockMovement, Warehouse
from .services import apply_stock_movement


class MaterialCategorySerializer(serializers.ModelSerializer):
    """Serializer for MaterialCategory CRUD operations."""

    class Meta:
        model = MaterialCategory
        fields = ['id', 'name', 'description']


class MaterialSerializer(serializers.ModelSerializer):
    """
    Serializer for Material CRUD operations.

    Read-only display fields (``category_name``, ``tax_rate_name``,
    ``default_supplier_name``) are included alongside the writable FK id
    fields so API consumers (e.g. a materials table in the UI) don't need a
    second round-trip just to show human-readable labels.
    """

    category_name = serializers.CharField(source='category.name', read_only=True)
    tax_rate_name = serializers.CharField(source='tax_rate.name', read_only=True)
    default_supplier_name = serializers.CharField(
        source='default_supplier.name', read_only=True,
    )

    class Meta:
        model = Material
        fields = [
            'id', 'category', 'category_name', 'name', 'sku', 'unit',
            'description', 'standard_cost', 'tax_rate', 'tax_rate_name',
            'default_supplier', 'default_supplier_name',
            'minimum_stock_level', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_minimum_stock_level(self, value):
        # Business rule: a reorder threshold cannot be negative -- the
        # schema types this as DECIMAL(18,3) NOT NULL but doesn't itself
        # enforce non-negativity at the DB layer, so it's enforced here.
        if value < 0:
            raise serializers.ValidationError(
                "minimum_stock_level cannot be negative."
            )
        return value


class WarehouseSerializer(serializers.ModelSerializer):
    """Serializer for Warehouse CRUD operations."""

    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'location', 'is_active']


class StockSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for Stock.

    ``quantity`` is intentionally excluded from writable input (the whole
    ModelSerializer is read-only here, enforced at the viewset level by
    only wiring list/retrieve routes) -- per BR 12.6, the only way to
    change it is by creating a StockMovement.
    """

    material_name = serializers.CharField(source='material.name', read_only=True)
    material_sku = serializers.CharField(source='material.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    minimum_stock_level = serializers.DecimalField(
        source='material.minimum_stock_level',
        max_digits=18, decimal_places=3, read_only=True,
    )
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = [
            'id', 'warehouse', 'warehouse_name', 'material', 'material_name',
            'material_sku', 'quantity', 'minimum_stock_level', 'is_low_stock',
            'updated_at',
        ]

    def get_is_low_stock(self, obj):
        # BRD 5.13 "Low-stock alerts": surfaced here as a computed flag so
        # any client rendering a stock list can highlight it directly,
        # in addition to the dedicated low_stock filter endpoint.
        return obj.quantity < obj.material.minimum_stock_level


class StockMovementSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and reading StockMovement ledger entries.

    ``create`` wraps movement creation + the resulting Stock update in one
    atomic transaction: if applying the movement to Stock fails for any
    reason, the ledger entry itself is rolled back too, so the two can
    never drift out of sync.
    """

    material_name = serializers.CharField(source='material.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'material', 'material_name', 'warehouse', 'warehouse_name',
            'quantity', 'movement_type', 'movement_date', 'user',
            'reference', 'notes',
        ]

    def validate(self, attrs):
        # OUT-direction movements (OUT, and negative-adjustment usage)
        # should be recorded as a negative quantity; IN-direction ones
        # positive. Rather than silently accepting whatever sign the
        # caller sent, enforce the convention documented on the model so
        # a client can't accidentally record an OUT movement that
        # increases stock.
        movement_type = attrs.get('movement_type')
        quantity = attrs.get('quantity')
        if movement_type == StockMovement.MovementType.OUT and quantity > 0:
            raise serializers.ValidationError(
                {'quantity': "OUT movements must have a negative quantity."}
            )
        if movement_type in (StockMovement.MovementType.IN, StockMovement.MovementType.RETURN) and quantity < 0:
            raise serializers.ValidationError(
                {'quantity': f"{movement_type} movements must have a positive quantity."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        movement = super().create(validated_data)
        apply_stock_movement(movement)
        return movement
