"""
DRF serializers for the ``inventory`` app -- Material Management slice
(CPMAS-28).
"""
from rest_framework import serializers

from .models import Material, MaterialCategory


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
            'minimum_stock_level', 'is_active',
        ]

    def validate_minimum_stock_level(self, value):
        # Business rule: a reorder threshold cannot be negative -- the
        # schema types this as DECIMAL(18,3) NOT NULL but doesn't itself
        # enforce non-negativity at the DB layer, so it's enforced here.
        if value < 0:
            raise serializers.ValidationError(
                "minimum_stock_level cannot be negative."
            )
        return value
