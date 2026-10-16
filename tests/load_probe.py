"""Small reproducible in-process API probe; this is not production capacity evidence.

Run: python -m tests.load_probe --orders 100 --concurrency 8
Uses real TestClient routes, serialized SQLite writes and a fresh on-disk test DB.
Network, reverse proxy, WAN, ERP, physical devices and long-running contention are
outside this probe. All generated products/orders are synthetic test data.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import platform
import resource
import sqlite3
import time

from tests import test_core as core


def run(orders=100, concurrency=8):
    if not 1 <= orders <= 10000 or not 1 <= concurrency <= 64:
        raise ValueError("orders must be 1..10000 and concurrency 1..64")
    flow = core.WarehouseIntegrationTests(methodName="test_concurrent_last_item_only_one_reservation")
    flow.setUp()
    try:
        inventory = max(1000, orders)
        flow.replenish(inventory)
        dataset = [flow.order(1, reference=f"LOAD-PROBE-{i}") for i in range(orders)]
        def reserve(order):
            started = time.perf_counter()
            try:
                response = flow.request(f"/orders/{order['id']}/reserve", {})
                status = response.status_code
            except Exception:
                status = "client_exception"
            return (time.perf_counter() - started) * 1000, status
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            outcomes = list(pool.map(reserve, dataset))
        elapsed = time.perf_counter() - started
        durations = sorted(outcome[0] for outcome in outcomes)
        errors = [status for _, status in outcomes if status != 200]
        flow.assertStock(inventory, inventory - orders, reserved=orders, picked=0)
        def percentile(fraction):
            return round(durations[max(0, math.ceil(len(durations) * fraction) - 1)], 3)
        report = {
            "scope": "small local in-process TestClient API probe against real SQLite; not production load qualification",
            "dataset": {"tenants": 1, "owners": 1, "warehouses": 1, "skus": 1, "inventory_units": inventory, "orders": orders, "units_per_order": 1},
            "operation": "reserve previously persisted orders concurrently",
            "concurrency": concurrency,
            "resources": {"logical_cpus_visible": os.cpu_count(), "platform": platform.system(), "architecture": platform.machine(), "python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "process_max_rss_kib_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
            "elapsed_seconds": round(elapsed, 4),
            "latency_ms": {"p50": percentile(.5), "p95": percentile(.95), "max": round(max(durations), 3)},
            "successful_reservations": len(outcomes) - len(errors), "error_count": len(errors),
            "error_statuses": errors, "reconciliation_ok": True,
            "database_bottleneck": "SQLite BEGIN IMMEDIATE serializes writers; this sample includes client/thread overhead and does not isolate lock wait time",
            "limitations": "No network latency, multiple processes, sustained production load, ERP or devices measured; no daily-order capacity or SLA claim"
        }
        output = Path(__file__).resolve().parents[1] / "evidence" / "load-probe.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        return report
    finally:
        flow.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    result = run(args.orders, args.concurrency)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["error_count"] else 0)
