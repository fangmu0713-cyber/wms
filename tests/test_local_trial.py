"""The optional trial never overwrites a business DB or prints credentials."""
import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from fastapi.testclient import TestClient
from app.db import connect
from app.main import create_app
from scripts.local_trial import prepare


class LocalTrialTests(unittest.TestCase):
    def test_new_trial_scopes_balances_and_restart_does_not_reseed(self):
        with TemporaryDirectory() as root:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                database,credentials = prepare(Path(root)/'trial')
                self.assertEqual(prepare(Path(root)/'trial'),(database,credentials))
            accounts = json.loads(credentials.read_text())['accounts']
            self.assertEqual(credentials.stat().st_mode & 0o777,0o600)
            self.assertEqual(credentials.parent.stat().st_mode & 0o777,0o700)
            for account in accounts.values():
                self.assertNotIn(account['token'],output.getvalue())
            with TestClient(create_app(database)) as client:
                def snap(label):
                    response = client.get('/api/snapshot',headers={'Authorization':'Bearer '+accounts[label]['token']})
                    self.assertEqual(response.status_code,200)
                    return response.json()
                admin = snap('admin')
                self.assertEqual(sum(i['on_hand'] for i in admin['inventory']),100)
                self.assertEqual(len(admin['orders']),1)
                self.assertTrue(admin['reconciliation']['ok'])
                self.assertEqual(len(snap('source_picker')['warehouses']),1)
                self.assertEqual(len(snap('destination_receiver')['warehouses']),1)
                self.assertEqual(snap('destination_receiver')['inventory'],[])
                self.assertEqual(snap('counter_a')['inventory'],[])
                self.assertEqual(snap('counter_b')['transfers'],[])
            with connect(database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],5)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],1)

    def test_existing_unrecognized_directory_and_symlink_refused(self):
        with TemporaryDirectory() as root:
            directory = Path(root)/'business'
            directory.mkdir()
            sentinel = directory/'trial.sqlite3'
            sentinel.write_text('existing business data')
            with self.assertRaisesRegex(ValueError,'nothing was overwritten'):
                prepare(directory)
            self.assertEqual(sentinel.read_text(),'existing business data')
            link = Path(root)/'link'
            link.symlink_to(directory,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):
                prepare(link)

    def test_revoked_credential_stops_trial_without_mutating_data(self):
        with TemporaryDirectory() as root:
            database,credentials = prepare(Path(root)/'trial')
            accounts = json.loads(credentials.read_text())['accounts']
            with connect(database) as db:
                db.execute('UPDATE users SET active=0 WHERE id=?',(accounts['counter_b']['user_id'],))
            with self.assertRaisesRegex(ValueError,'revoked'):
                prepare(Path(root)/'trial')
            with connect(database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],5)
