"""Tests of truthful unavailable boundaries; never vendor acceptance tests."""
import json

import unittest

from app.integrations import (
    Capability,
    ConnectorNotConfigured,
    ERPAdapter,
    UnsupportedCapability,
    create_adapter,
    get_registry,
)


class IntegrationBoundaryTests(unittest.TestCase):
    def test_registry_exposes_no_live_or_implemented_vendor_capability(self):
        registry = get_registry()
        self.assertEqual(len(registry), 5)
        self.assertEqual(json.loads(json.dumps(registry)), registry)
        for provider in registry:
            self.assertEqual(provider["status"], "pending_integration")
            self.assertFalse(provider["configured"])
            self.assertFalse(provider["production_enabled"])
            self.assertEqual(provider["implemented_methods"], [])
            self.assertEqual(provider["live_tested_methods"], [])
            self.assertTrue(provider["blocker"])
            for capability in provider["capabilities"]:
                self.assertFalse(capability["implemented"])
                self.assertFalse(capability["enabled"])
                self.assertFalse(capability["live_tested"])

    def test_registry_mutation_does_not_enable_connectors_or_change_sources(self):
        metadata = get_registry()
        metadata[0]["configured"] = True
        metadata[0]["capabilities"][0]["implemented"] = True
        metadata[0]["sources"].clear()
        fresh = get_registry()[0]
        self.assertFalse(fresh["configured"])
        self.assertFalse(fresh["capabilities"][0]["implemented"])
        self.assertTrue(fresh["sources"])

    def test_documented_upseller_reads_fail_closed(self):
        adapter = create_adapter("upseller")
        self.assertIsInstance(adapter, ERPAdapter)
        with self.assertRaises(ConnectorNotConfigured):
            adapter.list_warehouses()
        with self.assertRaises(ConnectorNotConfigured):
            adapter.read_inventory(warehouse_external_ids=("external-warehouse",))

    def test_pending_vendor_never_acknowledges_orders_shipments_or_stock_writes(self):
        for provider in ("upseller", "dianxiaomi", "lingxing", "mabang", "bling"):
            adapter = create_adapter(provider)
            for capability in (Capability.ORDERS_RECEIVE, Capability.ORDERS_READ, Capability.SHIPMENTS, Capability.INVENTORY_WRITE, Capability.LABELS, Capability.RETURNS):
                with self.subTest(provider=provider, capability=capability):
                    with self.assertRaises(UnsupportedCapability) as error:
                        adapter.execute(capability, {"secret": "never-echo-sensitive-payload"})
                    self.assertNotIn("never-echo-sensitive-payload", str(error.exception))

    def test_unknown_vendor_and_capability_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown ERP provider"):
            create_adapter("not-a-real-connector")
        with self.assertRaisesRegex(UnsupportedCapability, "Unsupported ERP capability"):
            create_adapter("upseller").execute("nonexistent", {"token": "private"})
