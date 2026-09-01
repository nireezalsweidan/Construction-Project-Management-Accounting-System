"""
Tests for the ``inventory`` app -- Material Management (CPMAS-28) and
Inventory & Warehouse Management (CPMAS-29).

Organized into:
- Model-level tests: constraints (unique SKU/category name, unique
  warehouse+material stock row) and on_delete behavior (PROTECT/
  SET_NULL), run directly against the ORM.
- Service tests: apply_stock_movement, the single function allowed to
  change Stock.quantity (BR 12.6).
- API tests: authentication enforcement, computed fields, filtering,
  the low_stock and transfer actions, and ledger immutability on
  StockMovement -- exercised through the real DRF endpoints, not just
  the underlying Python functions, so a regression in urls.py/views.py
  wiring would be caught too.
"""
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from suppliers.models import Supplier
from taxes.models import TaxRate
from users.models import User
from users.testing import WithUsersTableMixin

from .models import Material, MaterialCategory, Stock, StockMovement, Warehouse
from .services import apply_stock_movement


class MaterialModelTests(TestCase):
    def setUp(self):
        self.category = MaterialCategory.objects.create(name="Cement")

    def test_sku_must_be_unique(self):
        Material.objects.create(category=self.category, name="A", sku="DUP-1", unit="bag")
        with self.assertRaises(Exception):
            Material.objects.create(category=self.category, name="B", sku="DUP-1", unit="bag")

    def test_category_name_must_be_unique(self):
        with self.assertRaises(Exception):
            MaterialCategory.objects.create(name="Cement")

    def test_category_delete_is_protected_while_materials_reference_it(self):
        Material.objects.create(category=self.category, name="A", sku="SKU-1", unit="bag")
        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_tax_rate_deletion_sets_material_tax_rate_to_null(self):
        tax = TaxRate.objects.create(name="VAT", rate=Decimal("15"), tax_type="VAT", effective_date="2026-01-01")
        material = Material.objects.create(category=self.category, name="A", sku="SKU-2", unit="bag", tax_rate=tax)
        tax.delete()
        material.refresh_from_db()
        self.assertIsNone(material.tax_rate)

    def test_default_supplier_deletion_sets_material_supplier_to_null(self):
        supplier = Supplier.objects.create(name="ACME")
        material = Material.objects.create(category=self.category, name="A", sku="SKU-3", unit="bag", default_supplier=supplier)
        supplier.delete()
        material.refresh_from_db()
        self.assertIsNone(material.default_supplier)


class StockModelTests(TestCase):
    def setUp(self):
        category = MaterialCategory.objects.create(name="Steel")
        self.material = Material.objects.create(category=category, name="Rebar", sku="REBAR-1", unit="ton")
        self.warehouse = Warehouse.objects.create(name="Main Warehouse")

    def test_one_stock_row_per_warehouse_and_material(self):
        Stock.objects.create(warehouse=self.warehouse, material=self.material, quantity=Decimal("10"))
        with self.assertRaises(Exception):
            Stock.objects.create(warehouse=self.warehouse, material=self.material, quantity=Decimal("5"))

    def test_same_material_can_have_stock_in_multiple_warehouses(self):
        # Regression guard for the false-alarm "one warehouse per material"
        # bug briefly suspected during CPMAS-29 development (see the Stock
        # model's docstring) -- the live schema always supported this.
        other_warehouse = Warehouse.objects.create(name="Site B")
        Stock.objects.create(warehouse=self.warehouse, material=self.material, quantity=Decimal("10"))
        Stock.objects.create(warehouse=other_warehouse, material=self.material, quantity=Decimal("5"))
        self.assertEqual(Stock.objects.filter(material=self.material).count(), 2)


class ApplyStockMovementServiceTests(WithUsersTableMixin, TestCase):
    """
    Tests for inventory.services.apply_stock_movement -- the sole code
    path allowed to change Stock.quantity (BR 12.6).
    """

    def setUp(self):
        category = MaterialCategory.objects.create(name="Cement")
        self.material = Material.objects.create(category=category, name="Portland Cement", sku="CEM-1", unit="bag")
        self.warehouse = Warehouse.objects.create(name="Main Warehouse")
        self.user = User.objects.create(
            username="mover", email="mover@example.com", password_hash="x",
            first_name="M", last_name="V", role="owner",
        )

    def _movement(self, quantity, movement_type=StockMovement.MovementType.IN):
        movement = StockMovement(
            material=self.material, warehouse=self.warehouse, quantity=quantity,
            movement_type=movement_type, user=self.user,
        )
        movement.save()
        return movement

    def test_first_in_movement_creates_stock_row(self):
        apply_stock_movement(self._movement(Decimal("100")))
        stock = Stock.objects.get(warehouse=self.warehouse, material=self.material)
        self.assertEqual(stock.quantity, Decimal("100"))

    def test_out_movement_decreases_existing_stock(self):
        apply_stock_movement(self._movement(Decimal("100")))
        apply_stock_movement(self._movement(Decimal("-30"), StockMovement.MovementType.OUT))
        stock = Stock.objects.get(warehouse=self.warehouse, material=self.material)
        self.assertEqual(stock.quantity, Decimal("70"))

    def test_multiple_movements_accumulate_correctly(self):
        apply_stock_movement(self._movement(Decimal("50")))
        apply_stock_movement(self._movement(Decimal("25")))
        apply_stock_movement(self._movement(Decimal("-10"), StockMovement.MovementType.OUT))
        stock = Stock.objects.get(warehouse=self.warehouse, material=self.material)
        self.assertEqual(stock.quantity, Decimal("65"))


class InventoryAPITests(WithUsersTableMixin, TestCase):
    def setUp(self):
        self.category = MaterialCategory.objects.create(name="Cement")
        self.material = Material.objects.create(
            category=self.category, name="Portland Cement", sku="CEM-API-1", unit="bag",
            minimum_stock_level=Decimal("50"),
        )
        self.warehouse_a = Warehouse.objects.create(name="Warehouse A")
        self.warehouse_b = Warehouse.objects.create(name="Warehouse B")
        self.movement_user = User.objects.create(
            username="apimover", email="apimover@example.com", password_hash="x",
            first_name="A", last_name="M", role="owner",
        )

        self.django_user = DjangoUser.objects.create_user(username="apitester", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=self.django_user)

    def test_anonymous_request_is_rejected(self):
        anon = APIClient()
        response = anon.get("/api/inventory/materials/")
        # 401 (not 403): with the auth ticket in place, unauthenticated
        # requests are challenged to authenticate before access is denied.
        self.assertEqual(response.status_code, 401)

    def test_material_list_is_reachable_when_authenticated(self):
        response = self.client.get("/api/inventory/materials/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_material_search_by_name(self):
        response = self.client.get("/api/inventory/materials/?search=Portland")
        self.assertEqual(response.json()["count"], 1)
        response = self.client.get("/api/inventory/materials/?search=Nonexistent")
        self.assertEqual(response.json()["count"], 0)

    def test_material_duplicate_sku_rejected_via_api(self):
        response = self.client.post("/api/inventory/materials/", {
            "category": str(self.category.id), "name": "Dup", "sku": "CEM-API-1", "unit": "bag",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_stocks_endpoint_is_read_only(self):
        response = self.client.post("/api/inventory/stocks/", {
            "warehouse": str(self.warehouse_a.id), "material": str(self.material.id), "quantity": "9999",
        }, format="json")
        self.assertEqual(response.status_code, 405)

    def test_stock_movement_create_updates_stock_via_api(self):
        response = self.client.post("/api/inventory/stock-movements/", {
            "material": str(self.material.id), "warehouse": str(self.warehouse_a.id),
            "quantity": "80", "movement_type": "IN", "user": str(self.movement_user.id),
        }, format="json")
        self.assertEqual(response.status_code, 201)

        stock_response = self.client.get(f"/api/inventory/stocks/?warehouse={self.warehouse_a.id}")
        self.assertEqual(stock_response.json()["results"][0]["quantity"], "80.000")

    def test_out_movement_with_positive_quantity_rejected(self):
        response = self.client.post("/api/inventory/stock-movements/", {
            "material": str(self.material.id), "warehouse": str(self.warehouse_a.id),
            "quantity": "10", "movement_type": "OUT", "user": str(self.movement_user.id),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_stock_movement_is_immutable_after_creation(self):
        create_response = self.client.post("/api/inventory/stock-movements/", {
            "material": str(self.material.id), "warehouse": str(self.warehouse_a.id),
            "quantity": "10", "movement_type": "IN", "user": str(self.movement_user.id),
        }, format="json")
        movement_id = create_response.json()["id"]

        patch_response = self.client.patch(f"/api/inventory/stock-movements/{movement_id}/", {"notes": "edited"}, format="json")
        self.assertEqual(patch_response.status_code, 405)
        delete_response = self.client.delete(f"/api/inventory/stock-movements/{movement_id}/")
        self.assertEqual(delete_response.status_code, 405)

    def test_low_stock_action_finds_material_below_minimum(self):
        self.client.post("/api/inventory/stock-movements/", {
            "material": str(self.material.id), "warehouse": str(self.warehouse_a.id),
            "quantity": "10", "movement_type": "IN", "user": str(self.movement_user.id),
        }, format="json")  # below the 50 minimum set in setUp

        response = self.client.get("/api/inventory/stocks/low_stock/")
        skus = [row["material_sku"] for row in response.json()["results"]]
        self.assertIn("CEM-API-1", skus)

    def test_low_stock_action_excludes_material_at_or_above_minimum(self):
        self.client.post("/api/inventory/stock-movements/", {
            "material": str(self.material.id), "warehouse": str(self.warehouse_a.id),
            "quantity": "80", "movement_type": "IN", "user": str(self.movement_user.id),
        }, format="json")  # above the 50 minimum

        response = self.client.get("/api/inventory/stocks/low_stock/")
        skus = [row["material_sku"] for row in response.json()["results"]]
        self.assertNotIn("CEM-API-1", skus)

    def test_transfer_action_moves_stock_between_warehouses(self):
        self.client.post("/api/inventory/stock-movements/", {
            "material": str(self.material.id), "warehouse": str(self.warehouse_a.id),
            "quantity": "100", "movement_type": "IN", "user": str(self.movement_user.id),
        }, format="json")

        response = self.client.post("/api/inventory/stock-movements/transfer/", {
            "material": str(self.material.id), "from_warehouse": str(self.warehouse_a.id),
            "to_warehouse": str(self.warehouse_b.id), "quantity": "30",
            "user": str(self.movement_user.id),
        }, format="json")
        self.assertEqual(response.status_code, 201)

        stock_a = Stock.objects.get(warehouse=self.warehouse_a, material=self.material)
        stock_b = Stock.objects.get(warehouse=self.warehouse_b, material=self.material)
        self.assertEqual(stock_a.quantity, Decimal("70"))
        self.assertEqual(stock_b.quantity, Decimal("30"))

    def test_transfer_action_rejects_same_source_and_destination(self):
        response = self.client.post("/api/inventory/stock-movements/transfer/", {
            "material": str(self.material.id), "from_warehouse": str(self.warehouse_a.id),
            "to_warehouse": str(self.warehouse_a.id), "quantity": "10",
            "user": str(self.movement_user.id),
        }, format="json")
        self.assertEqual(response.status_code, 400)
