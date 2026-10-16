"""Recoverability checks against isolated files; never touch deployment data."""
import json
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import unittest

from fastapi.testclient import TestClient

from app.db import connect, migrate, transaction
from app.main import create_app
from scripts.restore_check import restore
from tests import test_core as core


class RecoveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.flow = core.WarehouseIntegrationTests(methodName="test_100_received_3_shipped_97_balance_and_restart")
        self.flow.setUp()
        self.addCleanup(self.flow.doCleanups)
        self.directory = Path(self.flow.temp.name)

    def command(self, *arguments):
        result = subprocess.run([sys.executable, "-m", "app.cli", *map(str, arguments)], capture_output=True, text=True, timeout=20, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, "Local CLI command failed: " + result.stderr)
        self.assertNotIn(self.flow.admin["token"], result.stdout + result.stderr)
        return result

    def test_consistent_backup_restore_reconciles_without_changing_source(self):
        self.flow.replenish(100)
        order = self.flow.order(3)
        self.flow.fulfill(order)
        self.flow.post("/fees", {"order_id": order["id"], "code": "TEST-SHIPPING", "amount_cents": 150})
        original = self.flow.snapshot()
        backup = self.directory / "backup.sqlite3"
        restored = self.directory / "restored.sqlite3"
        self.command("--db", self.flow.db, "backup", "--output", backup)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        report = restore(str(backup), str(restored))
        self.assertEqual(report["integrity"], "ok")
        self.assertEqual(report["foreign_keys"], "ok")
        self.assertEqual(report["ledger_balances"], "ok")
        self.assertEqual(report["counts"]["orders"], 1)
        self.assertEqual(report["counts"]["fees"], 1)
        with TestClient(create_app(str(restored))) as client:
            response = client.get("/api/snapshot", headers=self.flow.headers())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), original)
            self.assertTrue(response.json()["reconciliation"]["ok"])
            self.assertEqual(sum(row["on_hand"] for row in response.json()["inventory"]), 97)
        self.assertEqual(self.flow.snapshot(), original)
        with self.assertRaises(FileExistsError):
            restore(str(backup), self.flow.db)
        self.assertEqual(self.flow.snapshot(), original)
        # Store only inventory/count metrics; backup and credentials remain in tempdir.
        evidence = Path(__file__).resolve().parents[1] / "evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "recovery.json").write_text(json.dumps({**report, "source_unchanged": True, "restored_snapshot_matches": True, "restored_on_hand": 97, "credential_file_mode": "0600", "environment": "temporary synthetic test database"}, indent=2) + "\n")

    def test_repeat_migrations_and_append_only_ledger(self):
        self.flow.replenish(5)
        before = self.flow.snapshot()
        migrate(self.flow.db)
        migrate(self.flow.db)
        self.assertEqual(self.flow.snapshot(), before)
        with connect(self.flow.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], len(list((Path(__file__).resolve().parents[1] / "app" / "migrations").glob("*.sql"))))
        for statement in ("UPDATE ledger SET on_hand_delta=0", "DELETE FROM ledger", "UPDATE audit SET action='tampered'", "DELETE FROM audit"):
            with self.assertRaises(sqlite3.IntegrityError):
                with transaction(self.flow.db) as db:
                    db.execute(statement)
        self.assertEqual(self.flow.snapshot(), before)
        self.flow.assertStock(5, 5)

    def test_bootstrap_credentials_protected_not_printed_or_overwritten(self):
        credential = self.directory / "administrator.json"
        result = self.command("--db", self.flow.db, "bootstrap", "--tenant", "Credential test tenant", "--name", "Credential test administrator", "--output", credential)
        account = json.loads(credential.read_text())
        self.assertEqual(stat.S_IMODE(credential.stat().st_mode), 0o600)
        self.assertNotIn(account["token"], result.stdout + result.stderr)
        with connect(self.flow.db) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM users WHERE token_hash=?", (account["token"],)).fetchone())
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        retry = subprocess.run([sys.executable, "-m", "app.cli", "--db", self.flow.db, "bootstrap", "--tenant", "Must not create", "--name", "Must not create", "--output", str(credential)], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(retry.returncode, 0)
        self.assertNotIn(account["token"], retry.stdout + retry.stderr)
        self.assertEqual(json.loads(credential.read_text()), account)
        with connect(self.flow.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], count)


if __name__ == "__main__":
    unittest.main()
