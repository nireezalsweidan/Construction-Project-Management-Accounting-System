"""
DRF viewsets for the ``inventory`` app -- Material Management slice
(CPMAS-28).
"""
from rest_framework import viewsets

from .models import Material, MaterialCategory
from .serializers import MaterialCategorySerializer, MaterialSerializer


class MaterialCategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD API for material categories.

    Full ModelViewSet (list/create/retrieve/update/destroy) since category
    management is simple reference-data maintenance with no extra workflow.
    """

    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer
    search_fields = ['name']
    ordering_fields = ['name']


class MaterialViewSet(viewsets.ModelViewSet):
    """
    CRUD API for the material catalog.

    Supports filtering by ?category=<uuid> and ?is_active=true|false (BRD
    5.12/10: material management + cross-entity search/filtering), plus free
    -text search across name/SKU and ordering, via DRF's SearchFilter /
    OrderingFilter configured globally in REST_FRAMEWORK settings.
    """

    queryset = Material.objects.select_related(
        'category', 'tax_rate', 'default_supplier',
    ).all()
    serializer_class = MaterialSerializer
    search_fields = ['name', 'sku']
    ordering_fields = ['name', 'sku', 'standard_cost', 'minimum_stock_level']

    def get_queryset(self):
        # select_related avoids N+1 queries for the read-only display
        # fields (category_name, tax_rate_name, default_supplier_name)
        # added on the serializer.
        queryset = super().get_queryset()

        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            # Query params arrive as strings; interpret common truthy
            # spellings explicitly rather than relying on bool("false")
            # (which is truthy and would silently break this filter).
            queryset = queryset.filter(is_active=is_active.lower() in ('true', '1'))

        return queryset
