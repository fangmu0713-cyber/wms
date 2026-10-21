"""Real transactions, scoped operators and independent transfer custody evidence."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import provision
from app.db import connect, migrate
from app.main import create_app
from scripts.restore_check import restore
from tests.domain_fixtures import DomainCase


class TransferTests(DomainCase):
    def setUp(self):
        super().setUp()
        self.destination = self.post('/warehouses', {'name':'Rio transfer test'})
        self.bin = self.post('/locations', {'warehouse_id':self.destination['id'], 'code':'RIO-01'})
        self.bin2 = self.post('/locations', {'warehouse_id':self.destination['id'], 'code':'RIO-02'})
        self.replenish(100)
        self.source = self.snapshot()['inventory'][0]
        self.sender = self.worker('picker')
        self.receiver = self.worker('receiver', [self.destination['id']])

    def transfer(self, qty=10, account=None, key=None):
        return self.post('/transfers', {'source_inventory_id':self.source['id'],
            'destination_warehouse_id':self.destination['id'], 'reference':str(uuid4()), 'qty':qty}, account, key)

    def dispatch(self, transfer, account=None, key=None):
        return self.post(f"/transfers/{transfer['id']}/dispatch", self.dispatch_body(transfer), account or self.sender, key)

    def dispatch_body(self, transfer):
        return {'barcode':self.sku['barcode'], 'location_id':self.location['id'], 'qty':transfer['qty'],
                'carrier':'Test carrier', 'tracking_number':'TRACK-'+transfer['id']}

    def receive_transfer(self, transfer, qty=4, reference=None, location=None, account=None, key=None):
        return self.post(f"/transfers/{transfer['id']}/receive", {'barcode':self.sku['barcode'],
            'location_id':(location or self.bin)['id'], 'qty':qty, 'receipt_reference':reference or str(uuid4())}, account or self.receiver, key)

    def assert_custody(self, physical=100, transit=0, lost=0, account=None):
        snap = self.snapshot(account)
        self.assertTrue(snap['reconciliation']['ok'], snap['reconciliation'])
        self.assertEqual(sum(r['physical_total'] for r in snap['stock_summary']), physical)
        self.assertEqual(sum(r['transfer_in_transit'] for r in snap['stock_summary']), transit)
        self.assertEqual(sum(r['transfer_lost'] for r in snap['stock_summary']), lost)
        return snap

    def test_partial_receiving_multiple_bins_and_custody_never_double_counts(self):
        t = self.transfer()
        self.assertStock(100,90)
        self.assert_custody()
        self.dispatch(t)
        self.assertStock(90,90)
        self.assert_custody(transit=10)
        first = self.receive_transfer(t,4)
        self.assertEqual(first['status'],'PART_RECEIVED')
        self.assertStock(94,94)
        self.assert_custody(transit=6)
        final = self.receive_transfer(t,6,location=self.bin2)
        self.assertEqual(final['status'],'COMPLETED')
        snap = self.assert_custody()
        self.assertEqual(len(snap['transfer_events']),3)
        self.assertEqual({r['location_id']:r['on_hand'] for r in snap['inventory']}[self.bin2['id']],6)

    def test_source_destination_roles_and_one_sided_read_reconciliation(self):
        t = self.transfer()
        self.assertEqual(self.denied(f"/transfers/{t['id']}/dispatch",self.dispatch_body(t),self.receiver).status_code,403)
        wrong_sender = self.worker('picker',[self.destination['id']])
        self.assertEqual(self.denied(f"/transfers/{t['id']}/dispatch",self.dispatch_body(t),wrong_sender).status_code,404)
        self.dispatch(t)
        body = {'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':4,'receipt_reference':'SIDE'}
        self.assertEqual(self.denied(f"/transfers/{t['id']}/receive",body,self.sender).status_code,403)
        source_receiver = self.worker('receiver')
        self.assertEqual(self.denied(f"/transfers/{t['id']}/receive",body,source_receiver).status_code,404)
        self.receive_transfer(t)
        self.assert_custody(96,6,account=self.sender)
        self.assert_custody(4,account=self.receiver)
        self.assertEqual(len(self.snapshot(self.sender)['transfers']),1)
        self.assertEqual(len(self.snapshot(self.receiver)['transfers']),1)

    def test_create_cancel_require_supervisor_and_both_warehouses(self):
        one = self.worker('staff')
        body = {'source_inventory_id':self.source['id'],'destination_warehouse_id':self.destination['id'],'reference':'DENIED','qty':10}
        self.assertEqual(self.denied('/transfers',body,one).status_code,404)
        self.assertEqual(self.denied('/transfers',body,self.sender).status_code,403)
        both = self.worker('staff',[self.warehouse['id'],self.destination['id']])
        t = self.transfer(account=both)
        self.assertEqual(self.denied(f"/transfers/{t['id']}/cancel",{'reason':'cancel before departure'},one).status_code,404)
        self.post(f"/transfers/{t['id']}/cancel",{'reason':'cancel before departure'},both)
        self.assertStock(100,100)
        self.assert_custody()
        self.denied(f"/transfers/{t['id']}/dispatch",self.dispatch_body(t),self.sender)

    def test_confirmed_transit_loss_requires_admin_reason_and_exact_remaining(self):
        t = self.transfer()
        self.dispatch(t)
        self.receive_transfer(t,7)
        path = f"/transfers/{t['id']}/close_loss"
        both = self.worker('staff',[self.warehouse['id'],self.destination['id']])
        self.assertEqual(self.denied(path,{'qty':3,'reason':'carrier confirms lost'},both).status_code,403)
        self.denied(path,{'qty':3,'reason':'x'})
        self.denied(path,{'qty':2,'reason':'carrier confirms lost'})
        self.denied(path,{'qty':4,'reason':'carrier confirms lost'})
        key = str(uuid4())
        final = self.post(path,{'qty':3,'reason':'carrier confirms lost'},key=key)
        self.assertEqual(final['status'],'CLOSED_WITH_LOSS')
        self.assertEqual(self.post(path,{'qty':3,'reason':'carrier confirms lost'},key=key),final)
        self.assert_custody(97,0,3)
        self.denied(f"/transfers/{t['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':1,'receipt_reference':'LATE'},self.receiver)
        self.denied(f"/transfers/{t['id']}/cancel",{'reason':'cannot pretend returned'})

    def test_idempotency_replay_all_actions_and_duplicate_receipt_reference(self):
        body = {'source_inventory_id':self.source['id'],'destination_warehouse_id':self.destination['id'],'reference':'ONCE','qty':10}
        key = str(uuid4())
        t = self.post('/transfers',body,key=key)
        for _ in range(3):
            self.assertEqual(self.post('/transfers',body,key=key),t)
        self.denied('/transfers',{**body,'qty':9},key=key)
        dispatch_key = str(uuid4())
        dispatched = self.dispatch(t,key=dispatch_key)
        self.assertEqual(self.dispatch(t,key=dispatch_key),dispatched)
        receive_key = str(uuid4())
        first = self.receive_transfer(t,4,'BATCH-1',key=receive_key)
        for _ in range(3):
            self.assertEqual(self.receive_transfer(t,4,'BATCH-1',key=receive_key),first)
        body = {'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':4,'receipt_reference':'BATCH-1'}
        self.denied(f"/transfers/{t['id']}/receive",body,self.receiver)
        second_receiver = self.worker('receiver',[self.destination['id']])
        self.denied(f"/transfers/{t['id']}/receive",body,second_receiver)
        self.assert_custody(transit=6)
        self.assertEqual(self.snapshot()['transfers'][0]['received_qty'],4)

    def test_cached_response_still_checks_current_role_and_warehouse_grants(self):
        both = self.worker('staff',[self.warehouse['id'],self.destination['id']])
        body = {'source_inventory_id':self.source['id'],'destination_warehouse_id':self.destination['id'],'reference':'CACHE-SCOPE','qty':10}
        key = str(uuid4())
        t = self.post('/transfers',body,both,key)
        with connect(self.db) as db:
            db.execute('DELETE FROM user_warehouses WHERE user_id=? AND warehouse_id=?',(both['user_id'],self.destination['id']))
        self.assertEqual(self.denied('/transfers',body,both,key).status_code,404)
        dispatch_key = str(uuid4())
        self.dispatch(t,key=dispatch_key)
        with connect(self.db) as db:
            db.execute("UPDATE users SET role='receiver' WHERE id=?",(self.sender['user_id'],))
        self.assertEqual(self.denied(f"/transfers/{t['id']}/dispatch",self.dispatch_body(t),self.sender,dispatch_key).status_code,403)
        self.assert_custody(transit=10)

    def test_wrong_barcode_locations_quantities_and_physical_stage(self):
        t = self.transfer()
        dispatch = self.dispatch_body(t)
        for change in ({'barcode':'wrong'},{'location_id':self.bin['id']},{'qty':9},{'qty':0},{'qty':1.5}):
            self.denied(f"/transfers/{t['id']}/dispatch",{**dispatch,**change},self.sender)
        self.denied(f"/transfers/{t['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':1,'receipt_reference':'EARLY'},self.receiver)
        self.dispatch(t)
        self.denied(f"/transfers/{t['id']}/cancel",{'reason':'already dispatched'})
        for change in ({'barcode':'wrong'},{'location_id':self.location['id']},{'qty':11},{'qty':True},{'qty':-1}):
            self.denied(f"/transfers/{t['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':4,'receipt_reference':'BAD',**change})
        self.assert_custody(transit=10)

    def test_hold_excludes_reserved_moving_and_count_shortage_stock(self):
        self.reserved(30)
        second_bin = self.post('/locations',{'warehouse_id':self.warehouse['id'],'code':'A-02'})
        self.post('/movements',{'source_inventory_id':self.source['id'],'destination_location_id':second_bin['id'],'kind':'MOVE','reference':'HOLD','qty':20})
        self.denied('/transfers',{'source_inventory_id':self.source['id'],'destination_warehouse_id':self.destination['id'],'reference':'TOO-MUCH','qty':51})
        self.transfer(50)
        self.assertStock(100,0,30)
        self.assert_custody()

    def count(self, warehouse, location, counter):
        return self.post('/stock_counts',{'owner_id':self.owner['id'],'warehouse_id':warehouse['id'],'sku_id':self.sku['id'],'location_ids':[location['id']],'reference':str(uuid4()),'counter_id':counter['user_id']})

    def test_count_measurement_locks_create_dispatch_destination_and_loss(self):
        counter = self.worker(count_only=True)
        session = self.count(self.warehouse,self.location,counter)
        self.denied('/transfers',{'source_inventory_id':self.source['id'],'destination_warehouse_id':self.destination['id'],'reference':'LOCK','qty':1})
        self.post(f"/stock_counts/{session['id']}/cancel",{'reason':'end measurement'})
        t = self.transfer()
        self.denied('/stock_counts',{'owner_id':self.owner['id'],'warehouse_id':self.warehouse['id'],'sku_id':self.sku['id'],'location_ids':[self.location['id']],'reference':'HELD','counter_id':counter['user_id']})
        self.dispatch(t)
        session = self.count(self.warehouse,self.location,counter)
        self.denied(f"/transfers/{t['id']}/close_loss",{'qty':10,'reason':'confirmed loss while measuring'})
        # Source measurement does not prevent receiving into an unlocked destination.
        self.receive_transfer(t,4)
        self.post(f"/stock_counts/{session['id']}/cancel",{'reason':'measurement complete'})
        destination_counter = self.worker(warehouses=[self.destination['id']],count_only=True)
        session = self.count(self.destination,self.bin,destination_counter)
        self.denied(f"/transfers/{t['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':2,'receipt_reference':'LOCKED'},self.receiver)
        self.receive_transfer(t,6,location=self.bin2)
        self.post(f"/stock_counts/{session['id']}/cancel",{'reason':'measurement complete'})
        self.assert_custody()

    def test_count_shortage_hold_cannot_be_transferred(self):
        counter = self.worker(count_only=True)
        self.count(self.warehouse,self.location,counter)
        attempt = self.snapshot(counter)['count_attempts'][0]
        self.post(f"/count_attempts/{attempt['id']}/submit",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':98},counter)
        self.denied('/transfers',{'source_inventory_id':self.source['id'],'destination_warehouse_id':self.destination['id'],'reference':'SHORTAGE','qty':99})
        self.transfer(98)
        self.assertStock(100,0)
        self.assert_custody()

    def test_last_units_transfer_versus_order_is_serialized(self):
        order = self.order(100)
        def action(kind):
            if kind=='transfer':
                return self.request('/transfers',{'source_inventory_id':self.source['id'],'destination_warehouse_id':self.destination['id'],'reference':'RACE','qty':100})
            return self.request(f"/orders/{order['id']}/reserve",{})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(action,['transfer','order']))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertStock(100,0)
        self.assert_custody()

    def test_concurrent_receiving_cannot_over_receive(self):
        t = self.transfer()
        self.dispatch(t)
        def receive(index):
            return self.request(f"/transfers/{t['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':6,'receipt_reference':f'RACE-{index}'},self.receiver)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(receive,range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assert_custody(transit=4)
        self.assertEqual(self.snapshot()['transfers'][0]['received_qty'],6)

    def test_concurrent_receive_versus_loss_cannot_settle_twice(self):
        t = self.transfer()
        self.dispatch(t)
        def settle(kind):
            if kind=='loss':
                return self.request(f"/transfers/{t['id']}/close_loss",{'qty':10,'reason':'confirmed carrier loss'})
            return self.request(f"/transfers/{t['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':10,'receipt_reference':'RACE'},self.receiver)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(settle,['loss','receive']))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertTrue(self.snapshot()['reconciliation']['ok'])

    def test_atomic_rollback_after_stock_write_then_retry_original_key(self):
        t = self.transfer()
        self.dispatch(t)
        with connect(self.db) as db:
            db.execute("CREATE TRIGGER inject_transfer_failure BEFORE INSERT ON transfer_events WHEN NEW.kind='RECEIVE' BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        path = f"/transfers/{t['id']}/receive"
        body = {'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':4,'receipt_reference':'RETRY'}
        key = str(uuid4())
        before = self.snapshot()
        self.denied(path,body,self.receiver,key)
        after = self.snapshot()
        for name in ('inventory','ledger','transfers','transfer_events'):
            self.assertEqual(before[name],after[name])
        with connect(self.db) as db:
            self.assertFalse(db.execute('SELECT 1 FROM idempotency WHERE key=?',(key,)).fetchone())
            db.execute('DROP TRIGGER inject_transfer_failure')
        self.post(path,body,self.receiver,key)
        self.assert_custody(transit=6)

    def test_scope_isolation_tenant_owner_ungranted_and_blind_counter(self):
        t = self.transfer()
        outsider = provision(self.db,'Other tenant','Other administrator')
        ungranted = self.worker('staff',[])
        owner2 = self.post('/owners',{'name':'Owner B'})
        wrong_owner = self.worker('owner_readonly',[self.warehouse['id'],self.destination['id']],owner_id=owner2['id'])
        owner = self.worker('owner_readonly',[self.warehouse['id'],self.destination['id']],owner_id=self.owner['id'])
        counter = self.worker(count_only=True)
        for account in (outsider,ungranted,wrong_owner,counter):
            response = self.client.get(f"/api/transfers/{t['id']}",headers=self.headers(account))
            self.assertIn(response.status_code,(403,404))
            snap = self.snapshot(account)
            self.assertEqual(snap['transfers'],[])
            self.assertEqual(snap['transfer_events'],[])
        self.dispatch(t)
        self.assert_custody(transit=10,account=owner)
        self.assertEqual(self.snapshot(owner)['transfers'],[])
        for action,body in [('dispatch',self.dispatch_body(t)),('receive',{'barcode':self.sku['barcode'],'location_id':self.bin['id'],'qty':1,'receipt_reference':'HIDDEN'}),('close_loss',{'qty':10,'reason':'not authorized'}),('cancel',{'reason':'not authorized'})]:
            self.assertEqual(self.denied(f"/transfers/{t['id']}/{action}",body,counter).status_code,403)

    def test_same_warehouse_invalid_master_and_reference_rejected(self):
        body = {'source_inventory_id':self.source['id'],'destination_warehouse_id':self.warehouse['id'],'reference':'SAME','qty':1}
        self.denied('/transfers',body)
        self.denied('/transfers',{**body,'destination_warehouse_id':str(uuid4())})
        self.denied('/transfers',{**body,'destination_warehouse_id':self.destination['id'],'owner_id':self.owner['id']})
        valid = {**body,'destination_warehouse_id':self.destination['id']}
        self.post('/transfers',valid)
        self.denied('/transfers',valid)
        self.assertStock(100,99)

    def test_events_immutable_restart_and_backup_restore_partial_transfer(self):
        t = self.transfer()
        self.dispatch(t)
        self.receive_transfer(t,4)
        with connect(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('UPDATE transfer_events SET qty=1')
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM transfer_events')
        with TestClient(create_app(self.db)) as restarted:
            self.assertTrue(restarted.get('/api/snapshot',headers=self.headers(self.receiver)).json()['reconciliation']['ok'])
        restored = str(Path(self.temp.name)/'restored.sqlite3')
        result = restore(self.db,restored)
        self.assertEqual(result['transfer_custody'],'ok')
        with TestClient(create_app(restored)) as client:
            response = client.post(f"/api/transfers/{t['id']}/receive",json={'barcode':self.sku['barcode'],'location_id':self.bin2['id'],'qty':6,'receipt_reference':'AFTER-RESTORE'},headers=self.headers(self.receiver))
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(client.get('/api/snapshot',headers=self.headers()).json()['reconciliation']['ok'])
        self.assertEqual(self.snapshot()['transfers'][0]['received_qty'],4)

    def test_reconciliation_and_restore_reject_corrupt_transfer_metadata(self):
        t = self.transfer()
        self.dispatch(t)
        with connect(self.db) as db:
            db.execute('UPDATE transfers SET qty=11 WHERE id=?',(t['id'],))
        self.assertFalse(self.snapshot()['reconciliation']['ok'])
        with self.assertRaisesRegex(AssertionError,'transfer custody mismatch'):
            restore(self.db,str(Path(self.temp.name)/'bad.sqlite3'))

    def test_004_upgrade_preserves_old_ledger_and_forward_only_health(self):
        path = str(Path(self.temp.name)/'old004.sqlite3')
        with connect(path) as db:
            db.execute('CREATE TABLE schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
            for script in sorted(Path('app/migrations').glob('00[1-4]*.sql')):
                db.executescript(script.read_text())
                db.execute('INSERT INTO schema_migrations(version) VALUES (?)',(script.name,))
        with connect(self.db) as current, connect(path) as old:
            for table in ('tenants','owners','warehouses','locations','skus','stores','users','inventory','ledger'):
                columns = [r['name'] for r in old.execute(f'PRAGMA table_info({table})')]
                for row in current.execute(f'SELECT * FROM {table}'):
                    old.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",tuple(row[c] for c in columns))
            before = [dict(r) for r in old.execute('SELECT * FROM ledger')]
        old_admin = self.admin
        with TestClient(create_app(path)) as client:
            self.assertEqual(client.get('/health').status_code,503)
        migrate(path)
        migrate(path)
        with TestClient(create_app(path)) as client:
            self.assertEqual(client.get('/health').status_code,200)
            self.assertEqual(client.get('/api/snapshot',headers=self.headers(old_admin)).status_code,200)
        with connect(path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0],5)
            after = [dict(r) for r in db.execute('SELECT * FROM ledger')]
            for old,new in zip(before,after,strict=True):
                self.assertEqual({k:new[k] for k in old},old)
                self.assertEqual(new['transfer_transit_delta'],0)
                self.assertEqual(new['transfer_lost_delta'],0)
            self.assertEqual(db.execute('SELECT SUM(on_hand) FROM inventory').fetchone()[0],100)
