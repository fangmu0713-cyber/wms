"""Shared real-API fixtures; every case owns a temporary SQLite database."""
import unittest
from uuid import uuid4
from app.auth import provision
from tests import test_core as core


class DomainCase(unittest.TestCase):
    setUp = core.WarehouseIntegrationTests.setUp
    headers = core.WarehouseIntegrationTests.headers
    request = core.WarehouseIntegrationTests.request
    post = core.WarehouseIntegrationTests.post
    denied = core.WarehouseIntegrationTests.denied
    snapshot = core.WarehouseIntegrationTests.snapshot
    stock = core.WarehouseIntegrationTests.stock
    assertStock = core.WarehouseIntegrationTests.assertStock
    receive = core.WarehouseIntegrationTests.receive
    replenish = core.WarehouseIntegrationTests.replenish
    order = core.WarehouseIntegrationTests.order
    pick = core.WarehouseIntegrationTests.pick
    fulfill = core.WarehouseIntegrationTests.fulfill

    def reserved(self, qty=3):
        order = self.order(qty)
        self.post(f"/orders/{order['id']}/reserve", {})
        return order

    def worker(self, role='picker', warehouses=None, **kwargs):
        return provision(self.db, '', 'Test worker', role=role, tenant_id=self.admin['tenant_id'],
                         warehouse_ids=[self.warehouse['id']] if warehouses is None else warehouses, **kwargs)

    def put(self, qty, sku=None, location=None, owner=None, warehouse=None):
        receipt = self.post('/receipts', {'owner_id': (owner or self.owner)['id'],
            'warehouse_id': (warehouse or self.warehouse)['id'], 'sku_id': (sku or self.sku)['id'],
            'reference': str(uuid4()), 'qty': qty})
        self.post(f"/receipts/{receipt['id']}/qc", {'accepted_qty': qty, 'rejected_qty': 0})
        self.post(f"/receipts/{receipt['id']}/putaway", {'location_id': (location or self.location)['id']})
        return receipt
