"""Playwright acceptance: real browser -> HTTP API -> isolated on-disk database.

Run: python -m tests.browser_flow -v
Optional WMS_BROWSER_EXECUTABLE selects a local Chromium. No mocks, localStorage,
preseeded business data, credentials in artifacts, or third-party ERP claims.
"""
import json
import os
from pathlib import Path
import shutil
import socket
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest

import httpx
from playwright.sync_api import sync_playwright, expect
import uvicorn

from app.auth import provision
from app.db import migrate
from app.main import create_app


class BrowserBusinessFlow(unittest.TestCase):
    def test_chinese_full_flow_portuguese_and_mobile(self):
        with TemporaryDirectory(prefix="wms-browser-test-") as directory:
            db_path = str(Path(directory) / "test.sqlite3")
            migrate(db_path)
            account = provision(db_path, "Browser acceptance test", "Browser test administrator")
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(create_app(db_path), log_level="warning", access_log=False))
            thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(server.started, "Local test HTTP server did not start")
            evidence = Path(__file__).resolve().parents[1] / "evidence"
            evidence.mkdir(exist_ok=True)
            checks = []
            try:
                with httpx.Client(base_url=base_url, headers={"Authorization": "Bearer " + account["token"]}) as api, sync_playwright() as playwright:
                    executable = os.environ.get("WMS_BROWSER_EXECUTABLE") or shutil.which("chromium") or shutil.which("google-chrome")
                    launch = {"headless": True, "args": ["--no-sandbox"]}
                    if executable:
                        launch["executable_path"] = executable
                    browser = playwright.chromium.launch(**launch)
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 1000})
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(base_url)
                        expect(page.locator("html")).to_have_attribute("lang", "zh-CN")
                        page.locator("#api-token").fill(account["token"])
                        with page.expect_response(lambda r: "/api/snapshot" in r.url and r.request.method == "GET") as login:
                            page.locator("#login-form button[type=submit]").click()
                        self.assertEqual(login.value.status, 200)
                        expect(page.locator('button[data-view="masters"]')).to_be_enabled()

                        def submit(view, action, fields, drop_first_response=False):
                            page.locator(f'button[data-view="{view}"]').click()
                            form = page.locator(f"#{action}-form")
                            for name, value in fields.items():
                                field = form.locator(f'[name="{name}"]')
                                if field.evaluate("node => node.tagName") == "SELECT":
                                    expect(field.locator(f'option[value="{value}"]')).to_have_count(1)
                                    field.select_option(str(value))
                                else:
                                    field.fill(str(value))
                            lost = {}
                            if drop_first_response:
                                def drop_committed_response(route):
                                    # The actual server commits. Only its response is lost.
                                    upstream = route.fetch()
                                    self.assertEqual(upstream.status, 200)
                                    lost["record"] = upstream.json()
                                    lost["key"] = route.request.headers["idempotency-key"]
                                    route.abort("failed")
                                endpoint = base_url + "/api/receipts"
                                page.route(endpoint, drop_committed_response, times=1)
                                form.locator('button[type="submit"]').click()
                                expect(form.locator(".form-result.error")).to_contain_text("响应未确认")
                                expect(form.locator('button[type="submit"]')).to_be_enabled()
                                self.assertEqual(len(api.get("/api/snapshot").json()["receipts"]), 1)
                                page.unroute(endpoint, drop_committed_response)
                            with page.expect_response(lambda r: "/api/" in r.url and r.request.method == "POST") as result:
                                form.locator('button[type="submit"]').click()
                            response = result.value
                            self.assertLess(response.status, 300, f"UI action {action}: {response.status} {response.text()}")
                            payload = response.json()
                            if drop_first_response:
                                self.assertEqual(response.request.headers["idempotency-key"], lost["key"])
                                self.assertEqual(payload, lost["record"])
                                self.assertEqual(len(api.get("/api/snapshot").json()["receipts"]), 1)
                            expect(page.locator(f'[data-testid="{action}-result"]')).not_to_have_text("")
                            # UI refresh following mutations must finish before the next selector use.
                            expect(form.locator('button[type="submit"]')).to_be_enabled()
                            checks.append({"action": action, "status": response.status})
                            return payload

                        def stock(expected_on_hand, expected_available):
                            response = api.get("/api/snapshot")
                            self.assertEqual(response.status_code, 200)
                            snapshot = response.json()
                            self.assertTrue(snapshot["reconciliation"]["ok"], snapshot["reconciliation"])
                            self.assertEqual(sum(row["on_hand"] for row in snapshot["inventory"]), expected_on_hand)
                            self.assertEqual(sum(row["available"] for row in snapshot["inventory"]), expected_available)
                            return snapshot

                        owner = submit("masters", "owner", {"name": "浏览器测试货主"})
                        warehouse = submit("masters", "warehouse", {"name": "São Paulo 浏览器测试仓"})
                        location = submit("masters", "location", {"warehouse_id": warehouse["id"], "code": "A-01"})
                        sku = submit("masters", "sku", {"owner_id": owner["id"], "code": "BROWSER-SKU", "barcode": "789100000001", "name": "浏览器测试商品"})
                        store = submit("masters", "store", {"owner_id": owner["id"], "name": "Loja de teste"})
                        receipt = submit("inbound", "receipt", {"owner_id": owner["id"], "warehouse_id": warehouse["id"], "sku_id": sku["id"], "reference": "BROWSER-IN-100", "qty": 100}, drop_first_response=True)
                        stock(0, 0)
                        submit("inbound", "receipt-qc", {"receipt_id": receipt["id"], "accepted_qty": 100, "rejected_qty": 0})
                        submit("inbound", "receipt-putaway", {"receipt_id": receipt["id"], "location_id": location["id"]})
                        stock(100, 100)
                        order = submit("orders", "order", {"owner_id": owner["id"], "warehouse_id": warehouse["id"], "store_id": store["id"], "reference": "BROWSER-ORDER-3", "sku_id": sku["id"], "qty": 3})
                        submit("orders", "reserve", {"order_id": order["id"]})
                        stock(100, 97)
                        submit("pda", "pick", {"order_id": order["id"], "barcode": sku["barcode"], "location_id": location["id"], "qty": 3})
                        submit("pda", "verify", {"order_id": order["id"], "barcode": sku["barcode"], "qty": 3})
                        submit("pda", "pack", {"order_id": order["id"], "package_reference": "BROWSER-PACKAGE"})
                        stock(100, 97)
                        submit("pda", "ship", {"order_id": order["id"], "tracking_number": "BROWSER-TRACK", "carrier": "Manual test carrier"})
                        fee = submit("finance", "fee", {"order_id": order["id"], "code": "HANDLING", "amount_cents": 150})
                        final_snapshot = stock(97, 97)
                        self.assertEqual(len(final_snapshot["fees"]), 1)
                        page.locator('button[data-view="inventory"]').click()
                        expect(page.locator("#inventory-records")).to_contain_text("97")
                        expect(page.locator("#stock-quality-records")).to_contain_text("97")
                        self.assertEqual(page.evaluate("Object.keys(localStorage).length"), 0)
                        self.assertEqual(page.evaluate("Object.keys(sessionStorage).length"), 0)
                        page.evaluate("() => window.scrollTo(0, 0)")
                        page.screenshot(path=str(evidence / "browser-zh-inventory.png"), full_page=True, mask=[page.locator("#api-token")])

                        page.locator("#language").select_option("pt-BR")
                        expect(page.locator("html")).to_have_attribute("lang", "pt-BR")
                        expect(page.locator("body")).to_contain_text("Estoque")
                        expect(page.locator("#identity")).to_contain_text("Browser test administrator")
                        expect(page.locator("#last-refresh")).to_contain_text("Asia/Shanghai")
                        expect(page.locator('[data-testid="ship-result"]')).to_contain_text("Confirmado pelo servidor")
                        page.locator('button[data-view="finance"]').click()
                        expect(page.locator('#fee-records [data-column="amount_cents"]')).to_contain_text("1,50")
                        expect(page.locator('#fee-records [data-column="currency"]')).to_have_text("BRL")
                        page.evaluate("() => window.scrollTo(0, 0)")
                        page.screenshot(path=str(evidence / "browser-pt-finance.png"), full_page=True, mask=[page.locator("#api-token")])
                        page.locator('button[data-view="inventory"]').click()
                        page.evaluate("() => window.scrollTo(0, 0)")
                        page.screenshot(path=str(evidence / "browser-pt-inventory.png"), full_page=True, mask=[page.locator("#api-token")])
                        page.set_viewport_size({"width": 390, "height": 844})
                        page.locator('button[data-view="pda"]').click()
                        expect(page.locator("#pick-form")).to_be_visible()
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Mobile page overflows horizontally")
                        page.evaluate("() => window.scrollTo(0, 0)")
                        page.screenshot(path=str(evidence / "browser-pt-mobile-pda.png"), full_page=True, mask=[page.locator("#api-token")])
                        page.locator("#language").select_option("zh-CN")
                        expect(page.locator("html")).to_have_attribute("lang", "zh-CN")
                        page.evaluate("() => window.scrollTo(0, 0)")
                        page.screenshot(path=str(evidence / "browser-zh-mobile-pda.png"), full_page=True, mask=[page.locator("#api-token")])
                        self.assertEqual(errors, [], "Browser JavaScript errors")
                        report = {"environment": "isolated temporary SQLite database; synthetic test inventory", "flow": "UI HTTP API: receive 100 -> QC -> putaway -> order 3 -> reserve -> pick -> verify -> pack -> ship -> 97", "checks": checks, "inventory": [{key: row[key] for key in ("on_hand", "reserved", "picked", "available")} for row in final_snapshot["inventory"]], "reconciliation": final_snapshot["reconciliation"], "languages": ["zh-CN", "pt-BR"], "viewports": ["1440x1000", "390x844"], "javascript_errors": errors, "committed_response_loss_retry": "same idempotency key; one receipt", "brl_currency_display": "1,50", "warehouse_record_timezone": "America/Sao_Paulo", "refresh_display_timezone": "Asia/Shanghai", "erp_real_authorization_tested": False, "physical_scanner_tested": False}
                        (evidence / "browser-flow.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                    finally:
                        browser.close()
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                listener.close()


if __name__ == "__main__":
    unittest.main()
