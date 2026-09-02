"""
DRF viewsets for the ``inventory`` app -- Material Management (CPMAS-28)
and Inventory & Warehouse Management (CPMAS-29) slices.
"""
import uuid

from django.db import transaction
from django.db.models import F
from django.utils.dateparse import parse_datetime
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Material, MaterialCategory, Stock, StockMovement, Warehouse
from .serializers import (
    MaterialCategorySerializer,
    MaterialSerializer,
    StockMovementSerializer,
    StockSerializer,
    WarehouseSerializer,
)


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

    Supports filtering by ?category=<uuid>, ?supplier=<uuid>, and
    ?is_active=true|false (BRD 5.12/10: material management + cross-
    entity search/filtering), plus free-text search across name/SKU and
    ordering, via DRF's SearchFilter/OrderingFilter configured globally
    in REST_FRAMEWORK settings.
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

        supplier_id = self.request.query_params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(default_supplier_id=supplier_id)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            # Query params arrive as strings; interpret common truthy
            # spellings explicitly rather than relying on bool("false")
            # (which is truthy and would silently break this filter).
            queryset = queryset.filter(is_active=is_active.lower() in ('true', '1'))

        return queryset


class WarehouseViewSet(viewsets.ModelViewSet):
    """CRUD API for warehouses."""

    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    search_fields = ['name']
    ordering_fields = ['name']


class StockViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only API for current stock balances.

    list/retrieve only -- no create/update/destroy routes are wired up at
    all, so BR 12.6 ("quantity updated exclusively through stock
    movements") can't be bypassed even by a client that knows the URL
    pattern; it's not just hidden by a read-only serializer.
    """

    queryset = Stock.objects.select_related('material', 'warehouse').all()
    serializer_class = StockSerializer
    search_fields = ['material__name', 'material__sku', 'warehouse__name']
    ordering_fields = ['quantity', 'updated_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        warehouse_id = self.request.query_params.get('warehouse')
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)

        material_id = self.request.query_params.get('material')
        if material_id:
            queryset = queryset.filter(material_id=material_id)

        return queryset

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        GET /api/inventory/stocks/low_stock/

        BRD 5.13 "Low-stock alerts": stock rows where the on-hand quantity
        has fallen below the material's configured minimum_stock_level.
        A plain queryset filter rather than a stored/cached flag, so it's
        always accurate as of the request (materials.minimum_stock_level
        and stocks.quantity can each change independently).
        """
        queryset = self.filter_queryset(
            self.get_queryset().filter(quantity__lt=F('material__minimum_stock_level'))
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)


class StockMovementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                            mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Append-only ledger API for stock movements.

    list/retrieve/create only -- update/destroy are deliberately not
    wired up. A recorded movement is history; correcting a mistake means
    recording an offsetting movement (e.g. an ADJUSTMENT), the same way a
    mis-posted accounting entry gets reversed rather than edited in place.
    Supports filtering by material/warehouse/movement_type and a
    date range (BRD 5.13 "stock history", BRD 10 search/filter).
    """

    queryset = StockMovement.objects.select_related('material', 'warehouse', 'user').all()
    serializer_class = StockMovementSerializer
    search_fields = ['material__name', 'material__sku', 'reference']
    ordering_fields = ['movement_date', 'quantity']

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        material_id = params.get('material')
        if material_id:
            queryset = queryset.filter(material_id=material_id)

        warehouse_id = params.get('warehouse')
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)

        movement_type = params.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type.upper())

        date_from = parse_datetime(params.get('date_from', '') or '')
        if date_from:
            queryset = queryset.filter(movement_date__gte=date_from)

        date_to = parse_datetime(params.get('date_to', '') or '')
        if date_to:
            queryset = queryset.filter(movement_date__lte=date_to)

        return queryset

    @action(detail=False, methods=['post'])
    def transfer(self, request):
        """
        POST /api/inventory/stock-movements/transfer/

        BRD 5.13 "Transfers": moves quantity from one warehouse to another
        for the same material. The stock_movements table has a single
        warehouse_id column, so a transfer can't be one row -- this
        creates the paired OUT-at-source (negative quantity) and
        IN-at-destination (positive quantity) movements, both tagged
        movement_type=TRANSFER and correlated via a shared reference so
        the pair is identifiable in history, applied atomically so stock
        can't end up debited at the source without being credited at the
        destination.

        Body: {material, from_warehouse, to_warehouse, quantity (positive),
        user, reference (optional), notes (optional)}.
        """
        data = request.data
        required = ['material', 'from_warehouse', 'to_warehouse', 'quantity']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response(
                {'detail': f"Missing required field(s): {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if data['from_warehouse'] == data['to_warehouse']:
            return Response(
                {'detail': "from_warehouse and to_warehouse must differ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quantity = data['quantity']
        if float(quantity) <= 0:
            return Response(
                {'detail': "quantity must be positive; direction is implied by from/to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # uuid4-based rather than a count()+1 sequence: two concurrent
        # transfers racing on a count-based number could pick the same
        # value, which a sequence built from row counts can't prevent.
        reference = data.get('reference') or f"transfer-{uuid.uuid4().hex[:12]}"
        common = {
            'material': data['material'],
            'movement_type': StockMovement.MovementType.TRANSFER,
            'reference': reference,
            'notes': data.get('notes'),
            'user': data.get('user'),
        }

        out_serializer = StockMovementSerializer(data={
            **common, 'warehouse': data['from_warehouse'], 'quantity': f"-{quantity}",
        })
        out_serializer.is_valid(raise_exception=True)

        in_serializer = StockMovementSerializer(data={
            **common, 'warehouse': data['to_warehouse'], 'quantity': quantity,
        })
        in_serializer.is_valid(raise_exception=True)

        # Both legs succeed or neither does -- see StockMovementSerializer
        # .create()'s own @transaction.atomic; nesting is safe (Django
        # collapses nested atomic() blocks into savepoints).
        with transaction.atomic():
            out_movement = out_serializer.save()
            in_movement = in_serializer.save()

        return Response(
            {
                'out': StockMovementSerializer(out_movement).data,
                'in': StockMovementSerializer(in_movement).data,
            },
            status=status.HTTP_201_CREATED,
        )
