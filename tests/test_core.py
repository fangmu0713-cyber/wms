"""Core warehouse integration tests. Run: python -m unittest tests.test_core -v.

Every test uses a new on-disk SQLite database and real FastAPI routes. No API
or database methods are mocked. The fixtures are synthetic test inventory.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import provision
from app.db import migrate, transaction
from app.main import create_app


class WarehouseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="wms-core-test-")
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "test.sqlite3")
        migrate(self.db)
        self.admin = provision(self.db, "Test tenant A", "Test administrator")
        self.client = TestClient(create_app(self.db))
        self.addCleanup(self.client.close)
        self.owner = self.post("/owners", {"name": "Owner A"})
        self.warehouse = self.post("/warehouses", {"name": "São Paulo test"})
        self.location = self.post("/locations", {"warehouse_id": self.warehouse["id"], "code": "A-01"})
        self.sku = self.post("/skus", {"owner_id": self.owner["id"], "code": "SKU-001", "barcode": "789000000001", "name": "测试商品"})
        self.store = self.post("/stores", {"owner_id": self.owner["id"], "name": "Brazil test store"})

    def headers(self, account=None, key=None):
        return {"Authorization": "Bearer " + (account or self.admin)["token"], "Idempotency-Key": key or str(uuid4())}

    def request(self, path, body, account=None, key=None):
        return self.client.post("/api" + path, json=body, headers=self.headers(account, key))

    def post(self, path, body, account=None, key=None):
        response = self.request(path, body, account, key)
        self.assertLess(response.status_code, 300, f"{path}: {response.status_code} {response.text}")
        return response.json()

    def denied(self, path, body, account=None, key=None):
        response = self.request(path, body, account, key)
        self.assertGreaterEqual(response.status_code, 400, f"Unexpected success: {path} {response.text}")
        self.assertLess(response.status_code, 500, f"Unexpected server error: {path} {response.text}")
        return response

    def snapshot(self, account=None):
        response = self.client.get("/api/snapshot", headers=self.headers(account))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def stock(self, account=None):
        rows = self.snapshot(account)["inventory"]
        return {field: sum(row[field] for row in rows if row["sku_id"] == self.sku["id"]) for field in ("on_hand", "reserved", "picked", "available")}

    def assertStock(self, on_hand, available, reserved=None, picked=None):
        stock = self.stock()
        self.assertEqual(stock["on_hand"], on_hand)
        self.assertEqual(stock["available"], available)
        if reserved is not None:
            self.assertEqual(stock["reserved"], reserved)
        if picked is not None:
            self.assertEqual(stock["picked"], picked)
        reconciliation = self.snapshot()["reconciliation"]
        self.assertTrue(reconciliation["ok"], reconciliation)

    def assertCustody(self, physical, pending=0, qualified_unstored=0, rejected=0):
        rows = [row for row in self.snapshot()["stock_summary"] if row["sku_id"] == self.sku["id"]]
        for field, expected in (("physical_total", physical), ("pending_qc", pending), ("qualified_unstored", qualified_unstored), ("rejected", rejected)):
            self.assertEqual(sum(row[field] for row in rows), expected, field)

    def receive(self, qty=100, key=None, reference=None):
        return self.post("/receipts", {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "sku_id": self.sku["id"], "reference": reference or str(uuid4()), "qty": qty}, key=key)

    def replenish(self, qty=100):
        receipt = self.receive(qty)
        self.post(f"/receipts/{receipt['id']}/qc", {"accepted_qty": qty, "rejected_qty": 0})
        self.post(f"/receipts/{receipt['id']}/putaway", {"location_id": self.location["id"]})
        return receipt

    def order(self, qty=3, reference=None, account=None, owner=None, store=None, sku=None, warehouse=None):
        return self.post("/orders", {"owner_id": (owner or self.owner)["id"], "warehouse_id": (warehouse or self.warehouse)["id"], "store_id": (store or self.store)["id"], "reference": reference or str(uuid4()), "lines": [{"sku_id": (sku or self.sku)["id"], "qty": qty}]}, account=account)

    def pick(self, order, qty=3, key=None):
        return self.post(f"/orders/{order['id']}/pick", {"barcode": self.sku["barcode"], "location_id": self.location["id"], "qty": qty}, key=key)

    def fulfill(self, order, qty=3):
        self.post(f"/orders/{order['id']}/reserve", {})
        self.pick(order, qty)
        self.post(f"/orders/{order['id']}/verify", {"barcode": self.sku["barcode"], "qty": qty})
        self.post(f"/orders/{order['id']}/pack", {"package_reference": "PKG-" + order["id"]})
        self.post(f"/orders/{order['id']}/ship", {"tracking_number": "TEST-" + order["id"], "carrier": "Manual test carrier"})

    def test_100_received_3_shipped_97_balance_and_restart(self):
        receipt = self.receive(100)
        self.assertStock(0, 0)
        self.assertCustody(100, pending=100)
        self.post(f"/receipts/{receipt['id']}/qc", {"accepted_qty": 100, "rejected_qty": 0})
        self.assertStock(0, 0)
        self.assertCustody(100, qualified_unstored=100)
        self.post(f"/receipts/{receipt['id']}/putaway", {"location_id": self.location["id"]})
        self.assertStock(100, 100)
        self.assertCustody(100)
        order = self.order()
        self.post(f"/orders/{order['id']}/reserve", {})
        self.assertStock(100, 97, reserved=3, picked=0)
        self.pick(order)
        self.assertStock(100, 97, picked=3)
        self.post(f"/orders/{order['id']}/verify", {"barcode": self.sku["barcode"], "qty": 3})
        self.post(f"/orders/{order['id']}/pack", {"package_reference": "PKG-1"})
        self.assertStock(100, 97, picked=3)
        ship_key = str(uuid4())
        ship_path = f"/orders/{order['id']}/ship"
        ship_body = {"tracking_number": "TRACK-1", "carrier": "Test carrier"}
        shipped = self.post(ship_path, ship_body, key=ship_key)
        for _ in range(10):
            self.assertEqual(self.post(ship_path, ship_body, key=ship_key), shipped)
        self.assertStock(97, 97, reserved=0, picked=0)
        self.assertCustody(97)
        self.denied(ship_path, ship_body)
        self.denied(f"/orders/{order['id']}/cancel", {})
        self.assertStock(97, 97)
        with TestClient(create_app(self.db)) as restarted:
            snapshot = restarted.get("/api/snapshot", headers=self.headers()).json()
            self.assertTrue(snapshot["reconciliation"]["ok"])
            self.assertEqual(snapshot["orders"][0]["status"], "SHIPPED")
            self.assertEqual(sum(row["on_hand"] for row in snapshot["inventory"]), 97)

    def test_concurrent_last_item_only_one_reservation(self):
        self.replenish(1)
        orders = [self.order(1), self.order(1)]
        def reserve(order):
            return self.request(f"/orders/{order['id']}/reserve", {})
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(reserve, orders))
        self.assertEqual(sum(response.status_code < 300 for response in responses), 1, [r.text for r in responses])
        self.assertTrue(all(r.status_code < 500 for r in responses))
        self.assertStock(1, 0, reserved=1)

    def test_idempotent_receive_scan_fee_and_conflicting_payload(self):
        key = str(uuid4())
        receipt = self.receive(10, key=key, reference="IN-IDEMPOTENT")
        for _ in range(10):
            self.assertEqual(self.receive(10, key=key, reference="IN-IDEMPOTENT")["id"], receipt["id"])
        self.denied("/receipts", {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "sku_id": self.sku["id"], "reference": "IN-IDEMPOTENT", "qty": 11}, key=key)
        self.assertEqual(len(self.snapshot()["receipts"]), 1)
        self.post(f"/receipts/{receipt['id']}/qc", {"accepted_qty": 10, "rejected_qty": 0})
        putaway_path = f"/receipts/{receipt['id']}/putaway"
        putaway_key = str(uuid4())
        for _ in range(10):
            self.post(putaway_path, {"location_id": self.location["id"]}, key=putaway_key)
        self.assertStock(10, 10)
        order = self.order(3)
        self.post(f"/orders/{order['id']}/reserve", {})
        scan_key = str(uuid4())
        for _ in range(10):
            self.pick(order, 3, key=scan_key)
        self.assertStock(10, 7, picked=3)
        self.post(f"/orders/{order['id']}/verify", {"barcode": self.sku["barcode"], "qty": 3})
        self.post(f"/orders/{order['id']}/pack", {"package_reference": "IDEMPOTENT-PACKAGE"})
        self.post(f"/orders/{order['id']}/ship", {"tracking_number": "IDEMPOTENT-TRACK", "carrier": "Test carrier"})
        fee_body = {"order_id": order["id"], "code": "HANDLING", "amount_cents": 150}
        fee_key = str(uuid4())
        for _ in range(10):
            self.post("/fees", fee_body, key=fee_key)
        self.denied("/fees", fee_body)
        fees = self.snapshot()["fees"]
        self.assertEqual(len(fees), 1)
        self.assertEqual(fees[0]["amount_cents"], 150)

    def test_wrong_scans_overquantity_and_premature_actions(self):
        self.replenish(100)
        order = self.order()
        path = f"/orders/{order['id']}"
        self.denied(path + "/pick", {"barcode": self.sku["barcode"], "location_id": self.location["id"], "qty": 3})
        self.post(path + "/reserve", {})
        self.denied(path + "/pick", {"barcode": "WRONG", "location_id": self.location["id"], "qty": 3})
        self.denied(path + "/pick", {"barcode": self.sku["barcode"], "location_id": str(uuid4()), "qty": 3})
        self.denied(path + "/pick", {"barcode": self.sku["barcode"], "location_id": self.location["id"], "qty": 4})
        self.denied(path + "/verify", {"barcode": self.sku["barcode"], "qty": 3})
        self.denied(path + "/pack", {"package_reference": "EARLY"})
        self.denied(path + "/ship", {"tracking_number": "EARLY", "carrier": "Test"})
        self.assertStock(100, 97, picked=0)
        self.pick(order)
        self.denied(path + "/pick", {"barcode": self.sku["barcode"], "location_id": self.location["id"], "qty": 1})
        self.denied(path + "/verify", {"barcode": "WRONG", "qty": 3})
        self.denied(path + "/verify", {"barcode": self.sku["barcode"], "qty": 4})
        self.denied(path + "/cancel", {})
        self.assertStock(100, 97, picked=3)

    def test_cancel_before_pick_releases_only_reservation(self):
        self.replenish(4)
        created = self.order(1)
        self.post(f"/orders/{created['id']}/cancel", {})
        self.assertStock(4, 4)
        order = self.order(3)
        self.post(f"/orders/{order['id']}/reserve", {})
        self.assertStock(4, 1)
        key = str(uuid4())
        for _ in range(10):
            self.post(f"/orders/{order['id']}/cancel", {}, key=key)
        self.assertStock(4, 4, reserved=0, picked=0)
        self.denied(f"/orders/{order['id']}/reserve", {})

    def test_returns_require_receive_qc_and_putaway_exactly_once(self):
        self.replenish(100)
        order = self.order()
        self.fulfill(order)
        returned = self.post("/returns", {"order_id": order["id"], "sku_id": self.sku["id"], "qty": 2, "reference": "RETURN-1"})
        path = f"/returns/{returned['id']}"
        self.assertStock(97, 97)
        self.assertCustody(97)
        self.denied(path + "/qc", {"accepted_qty": 2, "rejected_qty": 0})
        self.denied(path + "/putaway", {"location_id": self.location["id"]})
        self.post(path + "/receive", {})
        self.assertStock(97, 97)
        self.assertCustody(99, pending=2)
        self.denied(path + "/putaway", {"location_id": self.location["id"]})
        self.post(path + "/qc", {"accepted_qty": 2, "rejected_qty": 0})
        self.assertStock(97, 97)
        self.assertCustody(99, qualified_unstored=2)
        key = str(uuid4())
        for _ in range(10):
            self.post(path + "/putaway", {"location_id": self.location["id"]}, key=key)
        self.denied(path + "/putaway", {"location_id": self.location["id"]})
        self.assertStock(99, 99)
        self.assertCustody(99)
        self.denied("/returns", {"order_id": order["id"], "sku_id": self.sku["id"], "qty": 2, "reference": "RETURN-EXCEEDS-SHIPPED"})

    def test_unique_references_and_invalid_quantity(self):
        self.receive(5, reference="IN-UNIQUE")
        self.denied("/receipts", {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "sku_id": self.sku["id"], "reference": "IN-UNIQUE", "qty": 5})
        self.order(1, reference="ORDER-UNIQUE")
        self.denied("/orders", {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "store_id": self.store["id"], "reference": "ORDER-UNIQUE", "lines": [{"sku_id": self.sku["id"], "qty": 1}]})
        for qty in (0, -1, 1.5, True):
            self.denied("/receipts", {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "sku_id": self.sku["id"], "reference": str(uuid4()), "qty": qty})
        self.assertEqual(len(self.snapshot()["receipts"]), 1)

    def test_owner_tenant_and_warehouse_server_isolation(self):
        self.replenish(10)
        order = self.order(3)
        owner_b = self.post("/owners", {"name": "Owner B"})
        sku_b = self.post("/skus", {"owner_id": owner_b["id"], "code": self.sku["code"], "barcode": self.sku["barcode"], "name": "Other owner identical SKU"})
        store_b = self.post("/stores", {"owner_id": owner_b["id"], "name": "Owner B store"})
        owner_user = provision(self.db, "Test tenant A", "Owner B user", role="owner", owner_id=owner_b["id"], tenant_id=self.admin["tenant_id"], warehouse_ids=[self.warehouse["id"]])
        own_snapshot = self.snapshot(owner_user)
        self.assertEqual([row["id"] for row in own_snapshot["owners"]], [owner_b["id"]])
        self.assertEqual([row["id"] for row in own_snapshot["skus"]], [sku_b["id"]])
        for name in ("orders", "inventory", "receipts", "ledger", "fees"):
            self.assertEqual(own_snapshot[name], [], name)
        for table, object_id in (("orders", order["id"]), ("skus", self.sku["id"]), ("owners", self.owner["id"])):
            response = self.client.get(f"/api/{table}/{object_id}", headers=self.headers(owner_user))
            self.assertEqual(response.status_code, 404)
        self.denied(f"/orders/{order['id']}/reserve", {}, account=owner_user)
        foreign_order_body = {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "store_id": self.store["id"], "reference": "FORGED", "lines": [{"sku_id": self.sku["id"], "qty": 1}]}
        self.denied("/orders", foreign_order_body, account=owner_user)
        own_order = self.order(1, account=owner_user, owner=owner_b, store=store_b, sku=sku_b)
        self.denied(f"/orders/{own_order['id']}/reserve", {}, account=owner_user)
        self.assertStock(10, 10)
        foreign_admin = provision(self.db, "Tenant B", "Tenant B administrator")
        self.assertEqual(self.snapshot(foreign_admin)["orders"], [])
        self.denied(f"/orders/{order['id']}/reserve", {}, account=foreign_admin)
        self.denied("/orders", foreign_order_body, account=foreign_admin)
        warehouse_b = self.post("/warehouses", {"name": "Restricted warehouse"})
        staff = provision(self.db, "Test tenant A", "Restricted staff", role="staff", tenant_id=self.admin["tenant_id"], warehouse_ids=[warehouse_b["id"]])
        self.assertEqual(self.snapshot(staff)["inventory"], [])
        self.denied(f"/orders/{order['id']}/reserve", {}, account=staff)
        self.denied("/fees", {"order_id": order["id"], "code": "FORGED", "amount_cents": 1}, account=owner_user)

    def test_authentication_and_idempotency_are_required(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertIn(self.client.get("/api/snapshot").status_code, (401, 403))
        self.assertIn(self.client.get("/api/snapshot", headers={"Authorization": "Bearer invalid-test-token"}).status_code, (401, 403))
        response = self.client.post("/api/owners", json={"name": "No key"}, headers={"Authorization": "Bearer " + self.admin["token"]})
        self.assertIn(response.status_code, (400, 422))

    def test_qc_rejected_units_never_become_sellable(self):
        receipt = self.receive(10)
        path = f"/receipts/{receipt['id']}"
        self.denied(path + "/qc", {"accepted_qty": 9, "rejected_qty": 0})
        self.post(path + "/qc", {"accepted_qty": 7, "rejected_qty": 3})
        self.assertStock(0, 0)
        self.assertCustody(10, qualified_unstored=7, rejected=3)
        self.post(path + "/putaway", {"location_id": self.location["id"]})
        self.assertStock(7, 7)
        self.assertCustody(10, rejected=3)
        self.denied(path + "/qc", {"accepted_qty": 10, "rejected_qty": 0})
        self.denied(path + "/putaway", {"location_id": self.location["id"]})
        self.assertStock(7, 7)
        self.assertCustody(10, rejected=3)

    def test_failed_multiline_reservation_rolls_back_every_line(self):
        self.replenish(10)
        second_sku = self.post("/skus", {"owner_id": self.owner["id"], "code": "NO-STOCK", "barcode": "789000000002", "name": "No stock"})
        order = self.post("/orders", {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "store_id": self.store["id"], "reference": "ATOMIC-RESERVE", "lines": [{"sku_id": self.sku["id"], "qty": 3}, {"sku_id": second_sku["id"], "qty": 1}]})
        before = self.snapshot()
        self.denied(f"/orders/{order['id']}/reserve", {})
        after = self.snapshot()
        self.assertEqual(after["ledger"], before["ledger"])
        self.assertEqual(after["allocations"], [])
        self.assertEqual(after["orders"][0]["status"], "CREATED")
        self.assertStock(10, 10, reserved=0, picked=0)

    def test_concurrent_duplicate_receipt_creates_single_record(self):
        key = str(uuid4())
        body = {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "sku_id": self.sku["id"], "reference": "CONCURRENT-REPLAY", "qty": 5}
        with ThreadPoolExecutor(max_workers=10) as workers:
            responses = list(workers.map(lambda _: self.request("/receipts", body, key=key), range(10)))
        self.assertTrue(all(r.status_code < 300 for r in responses), [(r.status_code, r.text) for r in responses])
        self.assertEqual(len({r.json()["id"] for r in responses}), 1)
        self.assertEqual(len(self.snapshot()["receipts"]), 1)

    def test_role_readonly_expired_and_revoked_credentials(self):
        self.replenish(10)
        order = self.order()
        readonly = provision(self.db, "Test tenant A", "Read only owner", role="owner_readonly", owner_id=self.owner["id"], tenant_id=self.admin["tenant_id"], warehouse_ids=[self.warehouse["id"]])
        self.assertEqual(len(self.snapshot(readonly)["inventory"]), 1)
        self.denied(f"/orders/{order['id']}/reserve", {}, account=readonly)
        picker = provision(self.db, "Test tenant A", "Picker", role="picker", tenant_id=self.admin["tenant_id"], warehouse_ids=[self.warehouse["id"]])
        self.denied("/receipts", {"owner_id": self.owner["id"], "warehouse_id": self.warehouse["id"], "sku_id": self.sku["id"], "reference": "ROLE-DENIED", "qty": 1}, account=picker)
        self.post(f"/orders/{order['id']}/reserve", {})
        self.post(f"/orders/{order['id']}/pick", {"barcode": self.sku["barcode"], "location_id": self.location["id"], "qty": 3}, account=picker)
        self.denied(f"/orders/{order['id']}/verify", {"barcode": self.sku["barcode"], "qty": 3}, account=picker)
        with transaction(self.db) as db:
            db.execute("UPDATE users SET expires_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", readonly["user_id"]))
            db.execute("UPDATE users SET active=0 WHERE id=?", (picker["user_id"],))
        for account in (readonly, picker):
            response = self.client.get("/api/snapshot", headers=self.headers(account))
            self.assertEqual(response.status_code, 401)
        self.assertStock(10, 7, picked=3)


if __name__ == "__main__":
    unittest.main()
