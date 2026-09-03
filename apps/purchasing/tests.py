"""
Tests for the ``purchasing`` app -- Purchase Order Management (CPMAS-30)
and Goods Receiving (CPMAS-31).

Organized into:
- Service tests: compute_item_amounts/recalculate_po_totals (derived
  monetary totals), transition_status (the user-facing status workflow),
  and receive_goods (the atomic receiving flow: validation, stock
  movements, PO status recalculation).
- API tests: the same behaviors exercised through the real DRF
  endpoints -- status-change actions, DRAFT-lock enforcement, nested
  goods-receipt creation, and ledger immutability.
"""
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.models import Material, MaterialCategory, Stock, Warehouse
from suppliers.models import Supplier
from users.models import User
from users.testing import WithUsersTableMixin

from .models import GoodsReceipt, GoodsReceiptItem, PurchaseOrder, PurchaseOrderItem
from .services import (
    compute_item_amounts,
    quantity_received_for,
    quantity_remaining_for,
    receive_goods,
    recalculate_po_totals,
    transition_status,
)


class PurchasingTestBase(WithUsersTableMixin, TestCase):
    """Shared fixtures for purchasing tests: a supplier, a creator user, a material, a warehouse."""

    def setUp(self):
        self.supplier = Supplier.objects.create(name="ACME Building Supplies")
        self.creator = User.objects.create(
            username="creator", email="creator@example.com", password_hash="x",
            first_name="C", last_name="R", role="owner",
        )
        category = MaterialCategory.objects.create(name="Cement")
        self.material = Material.objects.create(category=category, name="Portland Cement", sku="CEM-PO-1", unit="bag")
        self.warehouse = Warehouse.objects.create(name="Main Warehouse")

    def make_po(self, **kwargs):
        defaults = dict(supplier=self.supplier, po_number="PO-0001", order_date="2026-08-31", created_by=self.creator)
        defaults.update(kwargs)
        return PurchaseOrder.objects.create(**defaults)

    def add_item(self, po, quantity=Decimal("10"), unit_price=Decimal("5.00"), tax_rate=None):
        item = PurchaseOrderItem(purchase_order=po, material=self.material, quantity=quantity, unit_price=unit_price, tax_rate=tax_rate)
        compute_item_amounts(item)
        item.save()
        recalculate_po_totals(po)
        return item


class ComputeItemAmountsTests(PurchasingTestBase):
    def test_amounts_computed_without_tax(self):
        po = self.make_po()
        item = self.add_item(po, quantity=Decimal("10"), unit_price=Decimal("5.00"))
        self.assertEqual(item.tax_amount, Decimal("0.00"))
        self.assertEqual(item.total_amount, Decimal("50.00"))

    def test_amounts_computed_with_tax(self):
        from taxes.models import TaxRate
        tax = TaxRate.objects.create(name="VAT 15%", rate=Decimal("15.0000"), tax_type="VAT", effective_date="2026-01-01")
        po = self.make_po()
        item = self.add_item(po, quantity=Decimal("10"), unit_price=Decimal("5.00"), tax_rate=tax)
        self.assertEqual(item.tax_amount, Decimal("7.50"))
        self.assertEqual(item.total_amount, Decimal("57.50"))


class RecalculatePoTotalsTests(PurchasingTestBase):
    def test_totals_sum_across_multiple_items(self):
        po = self.make_po()
        self.add_item(po, quantity=Decimal("10"), unit_price=Decimal("5.00"))
        self.add_item(po, quantity=Decimal("2"), unit_price=Decimal("10.00"))
        po.refresh_from_db()
        self.assertEqual(po.subtotal, Decimal("70.00"))
        self.assertEqual(po.total_amount, Decimal("70.00"))

    def test_totals_recompute_after_item_delete(self):
        po = self.make_po()
        item = self.add_item(po, quantity=Decimal("10"), unit_price=Decimal("5.00"))
        self.add_item(po, quantity=Decimal("2"), unit_price=Decimal("10.00"))
        item.delete()
        recalculate_po_totals(po)
        po.refresh_from_db()
        self.assertEqual(po.total_amount, Decimal("20.00"))


class TransitionStatusTests(PurchasingTestBase):
    def test_draft_to_submitted_to_approved(self):
        po = self.make_po()
        transition_status(po, PurchaseOrder.Status.SUBMITTED)
        self.assertEqual(po.status, PurchaseOrder.Status.SUBMITTED)
        transition_status(po, PurchaseOrder.Status.APPROVED)
        self.assertEqual(po.status, PurchaseOrder.Status.APPROVED)

    def test_cannot_skip_from_draft_to_approved(self):
        po = self.make_po()
        with self.assertRaises(ValidationError):
            transition_status(po, PurchaseOrder.Status.APPROVED)

    def test_cannot_leave_a_terminal_status(self):
        po = self.make_po()
        transition_status(po, PurchaseOrder.Status.CANCELLED)
        with self.assertRaises(ValidationError):
            transition_status(po, PurchaseOrder.Status.DRAFT)

    def test_can_cancel_from_approved(self):
        po = self.make_po()
        transition_status(po, PurchaseOrder.Status.SUBMITTED)
        transition_status(po, PurchaseOrder.Status.APPROVED)
        transition_status(po, PurchaseOrder.Status.CANCELLED)
        self.assertEqual(po.status, PurchaseOrder.Status.CANCELLED)


class ReceiveGoodsServiceTests(PurchasingTestBase):
    def setUp(self):
        super().setUp()
        self.po = self.make_po()
        self.item = self.add_item(self.po, quantity=Decimal("100"), unit_price=Decimal("2.00"))

    def _approve(self):
        transition_status(self.po, PurchaseOrder.Status.SUBMITTED)
        transition_status(self.po, PurchaseOrder.Status.APPROVED)

    def test_cannot_receive_against_a_draft_po(self):
        with self.assertRaises(ValidationError):
            receive_goods(
                self.po, {"receipt_number": "GR-1", "received_date": "2026-08-31", "warehouse": self.warehouse},
                [{"purchase_order_item": self.item, "quantity_received": Decimal("10")}], self.creator,
            )

    def test_partial_receipt_updates_stock_and_po_status(self):
        self._approve()
        receive_goods(
            self.po, {"receipt_number": "GR-1", "received_date": "2026-08-31", "warehouse": self.warehouse},
            [{"purchase_order_item": self.item, "quantity_received": Decimal("60")}], self.creator,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        self.assertEqual(quantity_received_for(self.item), Decimal("60"))
        self.assertEqual(quantity_remaining_for(self.item), Decimal("40"))
        stock = Stock.objects.get(warehouse=self.warehouse, material=self.material)
        self.assertEqual(stock.quantity, Decimal("60"))

    def test_over_receipt_is_rejected(self):
        self._approve()
        with self.assertRaises(ValidationError):
            receive_goods(
                self.po, {"receipt_number": "GR-1", "received_date": "2026-08-31", "warehouse": self.warehouse},
                [{"purchase_order_item": self.item, "quantity_received": Decimal("101")}], self.creator,
            )

    def test_full_receipt_marks_po_received(self):
        self._approve()
        receive_goods(
            self.po, {"receipt_number": "GR-1", "received_date": "2026-08-31", "warehouse": self.warehouse},
            [{"purchase_order_item": self.item, "quantity_received": Decimal("100")}], self.creator,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.RECEIVED)

    def test_two_partial_receipts_accumulate_and_complete(self):
        self._approve()
        receive_goods(
            self.po, {"receipt_number": "GR-1", "received_date": "2026-08-31", "warehouse": self.warehouse},
            [{"purchase_order_item": self.item, "quantity_received": Decimal("60")}], self.creator,
        )
        receive_goods(
            self.po, {"receipt_number": "GR-2", "received_date": "2026-08-31", "warehouse": self.warehouse},
            [{"purchase_order_item": self.item, "quantity_received": Decimal("40")}], self.creator,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.RECEIVED)
        stock = Stock.objects.get(warehouse=self.warehouse, material=self.material)
        self.assertEqual(stock.quantity, Decimal("100"))

    def test_cannot_receive_further_once_fully_received(self):
        self._approve()
        receive_goods(
            self.po, {"receipt_number": "GR-1", "received_date": "2026-08-31", "warehouse": self.warehouse},
            [{"purchase_order_item": self.item, "quantity_received": Decimal("100")}], self.creator,
        )
        with self.assertRaises(ValidationError):
            receive_goods(
                self.po, {"receipt_number": "GR-2", "received_date": "2026-08-31", "warehouse": self.warehouse},
                [{"purchase_order_item": self.item, "quantity_received": Decimal("1")}], self.creator,
            )


class PurchaseOrderAPITests(PurchasingTestBase):
    def setUp(self):
        super().setUp()
        django_user = DjangoUser.objects.create_user(username="apitester", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=django_user)

    def test_create_po_and_add_item_computes_totals(self):
        create_response = self.client.post("/api/purchasing/purchase-orders/", {
            "supplier": str(self.supplier.id), "po_number": "PO-API-1", "order_date": "2026-08-31",
            "created_by": str(self.creator.id),
        }, format="json")
        self.assertEqual(create_response.status_code, 201)
        po_id = create_response.json()["id"]

        item_response = self.client.post("/api/purchasing/purchase-order-items/", {
            "purchase_order": po_id, "material": str(self.material.id), "quantity": "4", "unit_price": "25.00",
        }, format="json")
        self.assertEqual(item_response.status_code, 201)

        po_response = self.client.get(f"/api/purchasing/purchase-orders/{po_id}/")
        self.assertEqual(po_response.json()["total_amount"], "100.00")

    def test_status_cannot_be_set_directly_via_patch(self):
        po = self.make_po(po_number="PO-API-2")
        response = self.client.patch(f"/api/purchasing/purchase-orders/{po.id}/", {"status": "APPROVED"}, format="json")
        self.assertEqual(response.json()["status"], "DRAFT")

    def test_submit_approve_cancel_workflow(self):
        po = self.make_po(po_number="PO-API-3")
        submit = self.client.post(f"/api/purchasing/purchase-orders/{po.id}/submit/")
        self.assertEqual(submit.json()["status"], "SUBMITTED")
        approve = self.client.post(f"/api/purchasing/purchase-orders/{po.id}/approve/")
        self.assertEqual(approve.json()["status"], "APPROVED")
        invalid = self.client.post(f"/api/purchasing/purchase-orders/{po.id}/approve/")
        self.assertEqual(invalid.status_code, 400)
        cancel = self.client.post(f"/api/purchasing/purchase-orders/{po.id}/cancel/")
        self.assertEqual(cancel.json()["status"], "CANCELLED")

    def test_items_locked_once_po_leaves_draft(self):
        po = self.make_po(po_number="PO-API-4")
        self.client.post(f"/api/purchasing/purchase-orders/{po.id}/submit/")
        response = self.client.post("/api/purchasing/purchase-order-items/", {
            "purchase_order": str(po.id), "material": str(self.material.id), "quantity": "1", "unit_price": "5.00",
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_filter_by_order_date_range(self):
        in_range = self.make_po(po_number="PO-API-5", order_date="2026-08-15")
        self.make_po(po_number="PO-API-6", order_date="2026-01-01")

        response = self.client.get("/api/purchasing/purchase-orders/?date_from=2026-08-01&date_to=2026-08-31")
        numbers = [p["po_number"] for p in response.json()["results"]]
        self.assertEqual(numbers, [in_range.po_number])


class GoodsReceiptAPITests(PurchasingTestBase):
    def setUp(self):
        super().setUp()
        django_user = DjangoUser.objects.create_user(username="apitester2", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=django_user)
        self.po = self.make_po(po_number="PO-GR-API-1")
        self.item = self.add_item(self.po, quantity=Decimal("50"), unit_price=Decimal("3.00"))
        self.po.status = PurchaseOrder.Status.APPROVED
        self.po.save(update_fields=["status"])

    def test_create_receipt_with_nested_items(self):
        response = self.client.post("/api/purchasing/goods-receipts/", {
            "purchase_order": str(self.po.id), "receipt_number": "GR-API-1", "received_date": "2026-08-31",
            "warehouse": str(self.warehouse.id), "recorded_by": str(self.creator.id),
            "items": [{"purchase_order_item": str(self.item.id), "quantity_received": "20"}],
        }, format="json")
        self.assertEqual(response.status_code, 201)

        stock = Stock.objects.get(warehouse=self.warehouse, material=self.material)
        self.assertEqual(stock.quantity, Decimal("20"))

        po_items = self.client.get(f"/api/purchasing/purchase-order-items/?purchase_order={self.po.id}")
        item_data = po_items.json()["results"][0]
        self.assertEqual(item_data["quantity_received"], 20.0)
        self.assertEqual(item_data["quantity_remaining"], 30.0)

    def test_over_receipt_via_api_is_rejected(self):
        response = self.client.post("/api/purchasing/goods-receipts/", {
            "purchase_order": str(self.po.id), "receipt_number": "GR-API-2", "received_date": "2026-08-31",
            "warehouse": str(self.warehouse.id), "recorded_by": str(self.creator.id),
            "items": [{"purchase_order_item": str(self.item.id), "quantity_received": "999"}],
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_receipt_is_immutable_after_creation(self):
        create_response = self.client.post("/api/purchasing/goods-receipts/", {
            "purchase_order": str(self.po.id), "receipt_number": "GR-API-3", "received_date": "2026-08-31",
            "warehouse": str(self.warehouse.id), "recorded_by": str(self.creator.id),
            "items": [{"purchase_order_item": str(self.item.id), "quantity_received": "5"}],
        }, format="json")
        receipt_id = create_response.json()["id"]

        patch_response = self.client.patch(f"/api/purchasing/goods-receipts/{receipt_id}/", {"notes": "x"}, format="json")
        self.assertEqual(patch_response.status_code, 405)
        delete_response = self.client.delete(f"/api/purchasing/goods-receipts/{receipt_id}/")
        self.assertEqual(delete_response.status_code, 405)
