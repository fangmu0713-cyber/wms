"""Blind counting, independent recounts and delta posting across live stock flows."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import provision
from app.db import connect, migrate, transaction
from app.main import create_app
from scripts.restore_check import restore
from tests.domain_fixtures import DomainCase


class StockCountTests(DomainCase):
    def setUp(self):
        super().setUp()
        self.first = self.worker(count_only=True)
        self.second = self.worker(count_only=True)
        self.other_location = self.post('/locations',{'warehouse_id':self.warehouse['id'],'code':'B-02'})

    def body(self, **overrides):
        return {'owner_id':self.owner['id'],'warehouse_id':self.warehouse['id'],'sku_id':self.sku['id'],
            'location_ids':[self.location['id']],'reference':str(uuid4()),'counter_id':self.first['user_id'],**overrides}

    def attempt(self, account=None):
        rows = self.snapshot(account)['count_attempts']
        return next(r for r in rows if r['status']=='ACTIVE')

    def submit_count(self,qty,account=None,attempt=None,key=None):
        account = account or self.first
        attempt = attempt or self.attempt(account)
        return self.post(f"/count_attempts/{attempt['id']}/submit",{'barcode':self.sku['barcode'],'location_id':attempt['location_id'],'qty':qty},account=account,key=key)

    def line(self,session):
        return next(r for r in self.snapshot()['count_lines'] if r['session_id']==session['id'])

    def recount(self,session,account=None):
        return self.post(f"/count_lines/{self.line(session)['id']}/recount",{'counter_id':(account or self.second)['user_id']})

    def approve(self,session,**kwargs):
        return self.post(f"/stock_counts/{session['id']}/approve",{'reason':'Physical variance independently verified'},**kwargs)

    def test_shortage_recount_and_shipping_after_cutoff_keep_new_events(self):
        self.replenish()
        session = self.post('/stock_counts',self.body())
        self.submit_count(98)
        self.assertStock(100,98,0,0)
        self.assertEqual(self.snapshot()['inventory'][0]['count_reserved'],2)
        self.fulfill(self.order(3))
        self.assertStock(97,95,0,0)
        second = self.recount(session)
        self.assertEqual(second['baseline_on_hand'],97)
        self.submit_count(95,self.second)
        self.fulfill(self.order(5),5)
        self.assertStock(92,90,0,0)
        source = self.snapshot()['inventory'][0]
        move = self.post('/movements',{'source_inventory_id':source['id'],'destination_location_id':self.other_location['id'],'reference':'AFTER-COUNT','kind':'MOVE','qty':10})
        self.post(f"/movements/{move['id']}/claim",{})
        self.post(f"/movements/{move['id']}/dispatch",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':10})
        self.post(f"/movements/{move['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.other_location['id'],'qty':10})
        self.approve(session)
        self.assertStock(90,90,0,0)
        self.assertEqual(next(i for i in self.snapshot()['inventory'] if i['location_id']==self.other_location['id'])['on_hand'],10)
        self.assertEqual(self.snapshot()['inventory'][0]['count_reserved'],0)
        with connect(self.db) as db:
            self.assertEqual(db.execute("SELECT SUM(on_hand_delta) FROM ledger WHERE event_type='COUNT_ADJUST'").fetchone()[0],-2)

    def test_measurement_lock_blocks_mutations_and_reserve_uses_other_bin(self):
        self.replenish(10)
        self.put(5,location=self.other_location)
        session = self.post('/stock_counts',self.body())
        order = self.reserved(3)
        allocation = next(a for a in self.snapshot()['allocations'] if a['order_id']==order['id'])
        inv = next(i for i in self.snapshot()['inventory'] if i['id']==allocation['inventory_id'])
        self.assertEqual(inv['location_id'],self.other_location['id'])
        receipt = self.receive(1)
        self.post(f"/receipts/{receipt['id']}/qc",{'accepted_qty':1,'rejected_qty':0})
        self.denied(f"/receipts/{receipt['id']}/putaway",{'location_id':self.location['id']})
        source = next(i for i in self.snapshot()['inventory'] if i['location_id']==self.location['id'])
        self.denied('/movements',{'source_inventory_id':source['id'],'destination_location_id':self.other_location['id'],'reference':'BLOCKED','kind':'MOVE','qty':1})
        incoming = self.post('/movements',{'source_inventory_id':inv['id'],'destination_location_id':self.location['id'],'reference':'INCOMING','kind':'MOVE','qty':1})
        self.post(f"/movements/{incoming['id']}/claim",{})
        self.post(f"/movements/{incoming['id']}/dispatch",{'barcode':self.sku['barcode'],'location_id':self.other_location['id'],'qty':1})
        self.denied(f"/movements/{incoming['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':1})
        self.submit_count(10)
        self.post(f"/receipts/{receipt['id']}/putaway",{'location_id':self.location['id']})
        self.post(f"/movements/{incoming['id']}/receive",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':1})
        self.approve(session)
        self.assertStock(16,13,3,0)

    def test_count_requires_no_orders_or_movement_commitments(self):
        self.replenish(10)
        order = self.reserved(1)
        self.denied('/stock_counts',self.body())
        self.post(f"/orders/{order['id']}/cancel",{})
        inv = self.snapshot()['inventory'][0]
        move = self.post('/movements',{'source_inventory_id':inv['id'],'destination_location_id':self.other_location['id'],'reference':'MOVE','kind':'MOVE','qty':1})
        self.denied('/stock_counts',self.body())
        self.post(f"/movements/{move['id']}/cancel",{})
        self.post('/stock_counts',self.body())

    def test_blind_counter_has_no_book_or_other_counter_read_paths(self):
        self.replenish()
        self.post('/stock_counts',self.body())
        task = self.attempt(self.first)
        self.assertFalse({'baseline_on_hand','cutoff_seq','delta','hold_qty'} & task.keys())
        snap = self.snapshot(self.first)
        for table in ['inventory','ledger','stock_summary','orders','receipts','movements','stock_counts','count_lines','count_operators']:
            self.assertEqual(snap[table],[],table)
        for path in [f"/inventory/{self.snapshot()['inventory'][0]['id']}",f"/skus/{self.sku['id']}",f"/owners/{self.owner['id']}"]:
            self.assertEqual(self.client.get('/api'+path,headers=self.headers(self.first)).status_code,403)
        self.assertEqual(self.client.get(f"/api/count_attempts/{task['id']}",headers=self.headers(self.second)).status_code,404)
        self.denied('/owners',{'name':'Not allowed'},account=self.first)
        self.denied(f"/count_attempts/{task['id']}/submit",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':100},account=self.admin)
        result = self.submit_count(98)
        self.assertFalse({'baseline_on_hand','cutoff_seq','delta','hold_qty'} & result.keys())

    def test_recount_mismatch_requires_two_consecutive_independent_deltas(self):
        self.replenish()
        session = self.post('/stock_counts',self.body())
        self.submit_count(98)
        self.denied(f"/count_lines/{self.line(session)['id']}/recount",{'counter_id':self.first['user_id']})
        self.recount(session)
        self.submit_count(97,self.second)
        self.denied(f"/stock_counts/{session['id']}/approve",{'reason':'Cannot approve mismatched counts'})
        self.assertEqual(self.snapshot()['inventory'][0]['count_reserved'],3)
        self.recount(session,self.first)
        self.submit_count(97,self.first)
        self.approve(session)
        self.assertStock(97,97,0,0)

    def test_known_empty_bin_surplus_and_zero_count(self):
        session = self.post('/stock_counts',self.body(location_ids=[self.location['id'],self.other_location['id']]))
        tasks = self.snapshot(self.first)['count_attempts']
        for task in tasks:
            self.submit_count(4 if task['location_id']==self.location['id'] else 0,attempt=task)
        self.assertEqual(len(self.snapshot()['inventory']),2)
        self.assertStock(0,0,0,0)
        line = next(r for r in self.snapshot()['count_lines'] if r['status']=='RECOUNT_REQUIRED')
        self.post(f"/count_lines/{line['id']}/recount",{'counter_id':self.second['user_id']})
        self.submit_count(4,self.second)
        self.approve(session)
        self.assertStock(4,4,0,0)

    def test_new_receipt_after_cutoff_is_not_overwritten_by_approval(self):
        self.replenish(10)
        session = self.post('/stock_counts',self.body())
        self.submit_count(8)
        self.recount(session)
        self.submit_count(8,self.second)
        self.put(3)
        self.approve(session)
        self.assertStock(11,11,0,0)

    def test_idempotency_and_observation_immutability(self):
        self.replenish(10)
        body,key = self.body(),str(uuid4())
        session = self.post('/stock_counts',body,key=key)
        self.assertEqual(self.post('/stock_counts',body,key=key),session)
        task = self.attempt(self.first)
        key = str(uuid4())
        observed = self.submit_count(10,attempt=task,key=key)
        for _ in range(10):
            self.assertEqual(self.submit_count(10,attempt=task,key=key),observed)
        self.denied(f"/count_attempts/{task['id']}/submit",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':9},account=self.first,key=key)
        self.denied(f"/count_attempts/{task['id']}/submit",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':10},account=self.first)
        for statement in ["UPDATE count_attempts SET counted_qty=9",'UPDATE count_attempts SET baseline_on_hand=9','DELETE FROM count_attempts']:
            with self.assertRaises(sqlite3.IntegrityError):
                with transaction(self.db) as db:
                    db.execute(statement)
        key = str(uuid4())
        approved = self.approve(session,key=key)
        self.assertEqual(self.approve(session,key=key),approved)
        self.denied(f"/stock_counts/{session['id']}/approve",{'reason':'Duplicate approval'})
        with connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ledger WHERE event_type='COUNT_ADJUST'").fetchone()[0],1)

    def test_count_shortage_hold_prevents_over_reservation_or_movement(self):
        self.replenish(10)
        session = self.post('/stock_counts',self.body())
        self.submit_count(2)
        self.denied(f"/orders/{self.order(3)['id']}/reserve",{})
        inv = self.snapshot()['inventory'][0]
        self.denied('/movements',{'source_inventory_id':inv['id'],'destination_location_id':self.other_location['id'],'reference':'OVER','kind':'MOVE','qty':3})
        self.recount(session)
        self.submit_count(2,self.second)
        order = self.reserved(2)
        self.approve(session)
        self.assertStock(2,0,2,0)
        self.assertEqual(self.snapshot()['inventory'][0]['count_reserved'],0)

    def test_cancel_releases_measurement_and_hold_without_stock_adjustment(self):
        self.replenish()
        session = self.post('/stock_counts',self.body(location_ids=[self.location['id'],self.other_location['id']]))
        task = next(a for a in self.snapshot(self.first)['count_attempts'] if a['location_id']==self.location['id'])
        self.submit_count(98,attempt=task)
        self.post(f"/stock_counts/{session['id']}/cancel",{'reason':'Scope withdrawn; physical variance remains for investigation'})
        self.assertStock(100,100,0,0)
        self.assertFalse(any(a['status']=='ACTIVE' for a in self.snapshot()['count_attempts']))
        self.assertTrue(all(r['active']==0 for r in self.snapshot()['count_lines']))
        self.reserved(100)

    def test_duplicate_scope_concurrency_and_atomic_multi_location_creation(self):
        self.replenish()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _:self.request('/stock_counts',self.body()),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        session = next(r.json() for r in responses if r.status_code==200)
        self.post(f"/stock_counts/{session['id']}/cancel",{'reason':'Test cancelled'})
        warehouse = self.post('/warehouses',{'name':'Other'})
        foreign = self.post('/locations',{'warehouse_id':warehouse['id'],'code':'FOREIGN'})
        self.denied('/stock_counts',self.body(location_ids=[self.location['id'],foreign['id']]))
        with connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM count_locks').fetchone()[0],0)

    def test_concurrent_approval_posts_once(self):
        self.replenish(10)
        session = self.post('/stock_counts',self.body())
        self.submit_count(8)
        self.recount(session)
        self.submit_count(8,self.second)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _:self.request(f"/stock_counts/{session['id']}/approve",{'reason':'Independent verification'}),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertStock(8,8,0,0)

    def test_concurrent_count_start_and_last_unit_reservation_have_one_winner(self):
        self.replenish(1)
        order = self.order(1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(self.request,'/stock_counts',self.body()),pool.submit(self.request,f"/orders/{order['id']}/reserve",{})]
            results = [job.result() for job in jobs]
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.assertEqual(self.stock()['available'],0)
        self.assertTrue(self.snapshot()['reconciliation']['ok'])

    def test_receiving_failure_rolls_back_multi_line_approval(self):
        self.replenish(10)
        self.put(10,location=self.other_location)
        session = self.post('/stock_counts',self.body(location_ids=[self.location['id'],self.other_location['id']]))
        for task in self.snapshot(self.first)['count_attempts']:
            self.submit_count(9,attempt=task)
        for line in self.snapshot()['count_lines']:
            self.post(f"/count_lines/{line['id']}/recount",{'counter_id':self.second['user_id']})
        for task in self.snapshot(self.second)['count_attempts']:
            self.submit_count(9,self.second,task)
        before = self.snapshot()
        with transaction(self.db) as db:
            db.execute("""CREATE TRIGGER fail_count_post BEFORE INSERT ON ledger WHEN NEW.event_type='COUNT_ADJUST'
                AND (SELECT COUNT(*) FROM ledger WHERE event_type='COUNT_ADJUST')>=1
                BEGIN SELECT RAISE(ABORT,'synthetic second line failure'); END""")
        key = str(uuid4())
        self.denied(f"/stock_counts/{session['id']}/approve",{'reason':'Count verification'},key=key)
        self.assertEqual(self.snapshot(),before)
        with transaction(self.db) as db:
            db.execute('DROP TRIGGER fail_count_post')
        self.post(f"/stock_counts/{session['id']}/approve",{'reason':'Count verification'},key=key)
        self.assertStock(18,18,0,0)

    def test_role_tenant_owner_warehouse_and_independent_operator_access(self):
        self.replenish()
        session = self.post('/stock_counts',self.body())
        for account in [self.worker('staff',warehouses=[]),provision(self.db,'Other','Other admin')]:
            self.assertEqual(self.client.get(f"/api/stock_counts/{session['id']}",headers=self.headers(account)).status_code,404)
        for role in ['owner','owner_readonly','picker','receiver','packer','finance']:
            account = self.worker(role,**({'owner_id':self.owner['id']} if role.startswith('owner') else {}))
            self.denied('/stock_counts',self.body(),account=account)
            self.assertEqual(self.snapshot(account)['count_attempts'],[])
        self.submit_count(100)
        self.assertEqual(self.denied(f"/stock_counts/{session['id']}/approve",{'reason':'Not an administrator'},account=self.worker('staff')).status_code,403)
        self.approve(session)
        owner = self.worker('owner',owner_id=self.owner['id'])
        self.assertTrue(self.snapshot(owner)['reconciliation']['ok'])

    def test_wrong_scan_and_zero_quantity_validation_preserve_cutoff(self):
        self.replenish(2)
        self.post('/stock_counts',self.body())
        task = self.attempt(self.first)
        for body in [{'barcode':'wrong','location_id':self.location['id'],'qty':2},{'barcode':self.sku['barcode'],'location_id':self.other_location['id'],'qty':2},
                     {'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':True},{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':-1}]:
            self.denied(f"/count_attempts/{task['id']}/submit",body,account=self.first)
        self.submit_count(0)
        self.assertStock(2,0,0,0)

    def test_cli_count_only_credential_is_protected_and_cannot_use_business_api(self):
        output = Path(self.temp.name)/'counter.token'
        result = subprocess.run([sys.executable,'-m','app.cli','--db',self.db,'user','--tenant-id',self.admin['tenant_id'],'--name','Blind counter',
            '--role','picker','--count-only','--warehouse-id',self.warehouse['id'],'--output',str(output)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        account = json.loads(output.read_text())
        self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600)
        self.assertNotIn(account['token'],result.stdout+result.stderr)
        self.assertEqual(self.client.get('/api/me',headers=self.headers(account)).json()['count_only'],1)
        self.denied('/orders',{},account=account)

    def test_open_count_backup_restore_keeps_lock_and_blind_assignment(self):
        self.replenish()
        session = self.post('/stock_counts',self.body())
        self.submit_count(98)
        self.recount(session)
        target = str(Path(self.temp.name)/'restored.sqlite3')
        restore(self.db,target)
        with TestClient(create_app(target)) as restored:
            self.assertEqual(restored.get('/api/snapshot',headers=self.headers()).json(),self.snapshot())
            task = self.attempt(self.second)
            response = restored.post(f"/api/count_attempts/{task['id']}/submit",json={'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':98},headers=self.headers(self.second))
            self.assertEqual(response.status_code,200,response.text)
            snap = restored.get('/api/snapshot',headers=self.headers()).json()
            self.assertEqual(snap['inventory'][0]['count_reserved'],2)
            response = restored.post(f"/api/stock_counts/{session['id']}/approve",json={'reason':'Independent restored count'},headers=self.headers())
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(restored.get('/api/snapshot',headers=self.headers()).json()['inventory'][0]['on_hand'],98)
        self.assertEqual(self.attempt(self.second)['status'],'ACTIVE')

    def test_real_003_upgrade_preserves_in_transit_and_grants(self):
        self.replenish()
        source = self.snapshot()['inventory'][0]
        move = self.post('/movements',{'source_inventory_id':source['id'],'destination_location_id':self.other_location['id'],'reference':'MIGRATE','kind':'MOVE','qty':40})
        self.post(f"/movements/{move['id']}/claim",{})
        self.post(f"/movements/{move['id']}/dispatch",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':40})
        legacy = str(Path(self.temp.name)/'legacy.sqlite3')
        scripts = Path(__file__).resolve().parents[1]/'app/migrations'
        with connect(self.db) as source,connect(legacy) as target:
            target.execute('CREATE TABLE schema_migrations(version TEXT PRIMARY KEY,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
            for name in ['001_initial.sql','002_waves.sql','003_movements.sql']:
                target.executescript((scripts/name).read_text())
                target.execute('INSERT INTO schema_migrations(version) VALUES (?)',(name,))
            for row in target.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'schema_migrations'").fetchall():
                table = row['name']
                columns = [r['name'] for r in target.execute(f'PRAGMA table_info({table})')]
                data = source.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall()
                target.executemany(f"INSERT INTO {table}({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",[tuple(r) for r in data])
        with TestClient(create_app(legacy)) as upgraded:
            self.assertEqual(upgraded.get('/health').status_code,503)
            self.assertEqual(upgraded.get('/api/me',headers=self.headers()).status_code,503)
            migrate(legacy)
            migrate(legacy)
            snap = upgraded.get('/api/snapshot',headers=self.headers()).json()
            self.assertEqual(snap['inventory'],self.snapshot()['inventory'])
            self.assertEqual(snap['ledger'],self.snapshot()['ledger'])
            self.assertEqual(snap['movements'],self.snapshot()['movements'])
            self.assertTrue(snap['reconciliation']['ok'])
            self.assertEqual(upgraded.get('/api/me',headers=self.headers(self.first)).json()['count_only'],0)

    def test_restore_refuses_inconsistent_count_hold_metadata(self):
        self.replenish(10)
        self.post('/stock_counts',self.body())
        self.submit_count(8)
        broken = str(Path(self.temp.name)/'broken.sqlite3')
        with connect(self.db) as source,connect(broken) as destination:
            source.backup(destination)
        with transaction(broken) as db:
            db.execute('UPDATE count_lines SET hold_qty=1')
        with self.assertRaisesRegex(AssertionError,'count hold mismatch'):
            restore(broken,str(Path(self.temp.name)/'must-reject.sqlite3'))
