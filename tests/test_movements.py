"""Physical movement acceptance: holds, custody, rollback, concurrency and scope."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import provision
from app.db import connect, migrate, transaction
from app.main import create_app
from tests.domain_fixtures import DomainCase


class MovementTests(DomainCase):
    def setUp(self):
        super().setUp()
        self.destination = self.post('/locations', {'warehouse_id': self.warehouse['id'], 'code': 'PICK-01'})

    def body(self, qty=40, **overrides):
        source = next(i for i in self.snapshot()['inventory'] if i['sku_id']==self.sku['id'] and i['location_id']==self.location['id'])
        return {'source_inventory_id': source['id'], 'destination_location_id': self.destination['id'],
                'kind': 'REPLENISHMENT', 'reference': str(uuid4()), 'qty': qty, **overrides}

    def scan(self, movement, receive=False, **overrides):
        return {'barcode': self.sku['barcode'], 'location_id': movement['destination_location_id' if receive else 'source_location_id'], 'qty': movement['qty'], **overrides}

    def dispatch(self, movement, account=None):
        self.post(f"/movements/{movement['id']}/claim", {}, account=account)
        return self.post(f"/movements/{movement['id']}/dispatch", self.scan(movement), account=account)

    def assertCustody(self, on_hand, held, transit, physical, available):
        snap = self.snapshot()
        rows = [r for r in snap['stock_summary'] if r['sku_id']==self.sku['id']]
        for field, expected in [('on_hand',on_hand),('move_reserved',held),('in_transit',transit),('physical_total',physical),('available',available)]:
            self.assertEqual(sum(r[field] for r in rows),expected,field)
        self.assertTrue(snap['reconciliation']['ok'],snap['reconciliation'])

    def test_hold_dispatch_receive_conservation_and_order_shipment(self):
        self.replenish()
        order = self.reserved(3)
        self.post('/waves',{'owner_id':self.owner['id'],'warehouse_id':self.warehouse['id'],'reference':'WITH-MOVEMENT','order_ids':[order['id']]})
        task = self.snapshot()['pick_tasks'][0]
        move = self.post('/movements', self.body())
        self.assertCustody(100,40,0,100,57)
        self.assertStock(100,57,3,0)
        worker = self.worker()
        self.dispatch(move, worker)
        self.assertCustody(60,0,40,100,57)
        self.post(f"/pick_tasks/{task['id']}/claim",{},account=worker)
        self.post(f"/pick_tasks/{task['id']}/scan",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':3},account=worker)
        self.assertStock(60,57,3,3)
        self.post(f"/movements/{move['id']}/receive",self.scan(move,True),account=worker)
        self.assertCustody(100,0,0,100,97)
        self.post(f"/orders/{order['id']}/verify", {'barcode':self.sku['barcode'],'qty':3})
        self.post(f"/orders/{order['id']}/pack", {'package_reference':'PKG'})
        self.post(f"/orders/{order['id']}/ship", {'carrier':'Test','tracking_number':'TRACK'})
        self.assertCustody(97,0,0,97,97)

    def test_retries_and_terminal_replays_make_one_pair_of_physical_events(self):
        self.replenish()
        body, key = self.body(), str(uuid4())
        move = self.post('/movements',body,key=key)
        for _ in range(10):
            self.assertEqual(self.post('/movements',body,key=key),move)
        self.denied('/movements',{**body,'qty':39},key=key)
        self.denied('/movements',body)
        self.post(f"/movements/{move['id']}/claim",{})
        for action in ['dispatch','receive']:
            key = str(uuid4())
            scan = self.scan(move,action=='receive')
            result = self.post(f"/movements/{move['id']}/{action}",scan,key=key)
            for _ in range(10):
                self.assertEqual(self.post(f"/movements/{move['id']}/{action}",scan,key=key),result)
            self.denied(f"/movements/{move['id']}/{action}",scan)
        with connect(self.db) as db:
            events = [tuple(r) for r in db.execute('SELECT event_type,on_hand_delta,move_reserved_delta,in_transit_delta FROM ledger WHERE source_id=? ORDER BY rowid',(move['id'],))]
            self.assertEqual(events,[('MOVE_HOLD',0,40,0),('MOVE_DISPATCH',-40,-40,40),('MOVE_RECEIVE',40,0,-40)])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE resource_id=?",(move['id'],)).fetchone()[0],4)
        self.assertCustody(100,0,0,100,100)

    def test_pre_dispatch_cancel_release_and_no_post_dispatch_cancel(self):
        self.replenish()
        move = self.post('/movements', self.body())
        worker = self.worker()
        self.post(f"/movements/{move['id']}/claim",{},account=worker)
        self.post(f"/movements/{move['id']}/release",{},account=worker)
        self.assertCustody(100,40,0,100,60)
        self.post(f"/movements/{move['id']}/cancel",{})
        self.assertCustody(100,0,0,100,100)
        self.denied(f"/movements/{move['id']}/claim",{})
        move = self.post('/movements',self.body())
        self.dispatch(move)
        for action in ['cancel','release','claim']:
            self.denied(f"/movements/{move['id']}/{action}",{})
        self.assertCustody(60,0,40,100,60)

    def test_wrong_scan_quantity_stage_and_assignee_are_rejected(self):
        self.replenish()
        move = self.post('/movements',self.body())
        self.denied(f"/movements/{move['id']}/dispatch",self.scan(move))
        worker, other = self.worker(), self.worker()
        self.post(f"/movements/{move['id']}/claim",{},account=worker)
        self.denied(f"/movements/{move['id']}/claim",{},account=other)
        self.denied(f"/movements/{move['id']}/receive",self.scan(move,True),account=worker)
        for scan in [self.scan(move,barcode='wrong'),self.scan(move,location_id=self.destination['id']),self.scan(move,qty=39),self.scan(move,qty=41)]:
            self.denied(f"/movements/{move['id']}/dispatch",scan,account=worker)
        self.assertCustody(100,40,0,100,60)
        self.post(f"/movements/{move['id']}/dispatch",self.scan(move),account=worker)
        self.assertEqual(self.denied(f"/movements/{move['id']}/receive",self.scan(move,True),account=other).status_code,403)
        self.denied(f"/movements/{move['id']}/receive",self.scan(move,True,location_id=self.location['id']),account=worker)
        self.assertCustody(60,0,40,100,60)

    def test_invalid_locations_quantities_and_order_reserves_cannot_move(self):
        self.replenish(10)
        self.reserved(3)
        warehouse = self.post('/warehouses',{'name':'Other warehouse'})
        location = self.post('/locations',{'warehouse_id':warehouse['id'],'code':'OTHER'})
        for body in [self.body(8),self.body(1,destination_location_id=self.location['id']),self.body(1,destination_location_id=location['id']),self.body(0),self.body(True),self.body(1,kind='UNKNOWN')]:
            self.denied('/movements',body)
            self.assertEqual(self.snapshot()['movements'],[])
        move = self.post('/movements',self.body(7))
        self.denied('/movements',self.body(1))
        self.assertCustody(10,7,0,10,0)
        self.dispatch(move)
        self.assertCustody(3,0,7,10,0)

    def test_order_reservation_cannot_consume_movement_hold(self):
        self.replenish(5)
        self.post('/movements',self.body(4))
        order = self.order(2)
        self.denied(f"/orders/{order['id']}/reserve",{})
        self.assertCustody(5,4,0,5,1)
        with transaction(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('UPDATE inventory SET reserved=2')

    def test_concurrent_movement_and_order_compete_for_last_unit(self):
        self.replenish(1)
        order = self.order(1)
        body = self.body(1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(self.request,'/movements',body),pool.submit(self.request,f"/orders/{order['id']}/reserve",{})]
            results = [job.result() for job in jobs]
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.assertEqual(self.stock()['available'],0)
        inv = self.snapshot()['inventory'][0]
        self.assertEqual(inv['reserved']+inv['move_reserved'],1)
        self.assertTrue(self.snapshot()['reconciliation']['ok'])

    def test_concurrent_holds_and_receipts_have_one_winner(self):
        self.replenish(1)
        bodies = [self.body(1),self.body(1)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda body:self.request('/movements',body),bodies))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        move = next(r.json() for r in results if r.status_code==200)
        self.dispatch(move)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _:self.request(f"/movements/{move['id']}/receive",self.scan(move,True)),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.assertCustody(1,0,0,1,1)

    def test_failure_receiving_rolls_back_and_same_key_can_recover(self):
        self.replenish()
        move = self.post('/movements',self.body())
        self.dispatch(move)
        with transaction(self.db) as db:
            db.execute("""CREATE TRIGGER fail_receive BEFORE INSERT ON ledger
                WHEN NEW.event_type='MOVE_RECEIVE' BEGIN SELECT RAISE(ABORT,'test failure'); END""")
        key = str(uuid4())
        self.denied(f"/movements/{move['id']}/receive",self.scan(move,True),key=key)
        self.assertEqual(len(self.snapshot()['inventory']),1)
        self.assertCustody(60,0,40,100,60)
        with transaction(self.db) as db:
            db.execute('DROP TRIGGER fail_receive')
        self.post(f"/movements/{move['id']}/receive",self.scan(move,True),key=key)
        self.assertCustody(100,0,0,100,100)

    def test_tenant_warehouse_roles_and_owner_custody_isolation(self):
        self.replenish()
        body = self.body()
        move = self.post('/movements',body)
        outsiders = [self.worker(warehouses=[]),provision(self.db,'Other','Other admin')]
        for account in outsiders:
            self.assertEqual(self.client.get(f"/api/movements/{move['id']}",headers=self.headers(account)).status_code,404)
            self.denied(f"/movements/{move['id']}/claim",{},account=account)
            self.assertEqual(self.snapshot(account)['movements'],[])
        for role in ['owner','owner_readonly','packer','finance']:
            account = self.worker(role,**({'owner_id':self.owner['id']} if role.startswith('owner') else {}))
            self.assertEqual(self.denied('/movements',body,account=account).status_code,403)
            self.assertEqual(self.denied(f"/movements/{move['id']}/claim",{},account=account).status_code,403)
            self.assertEqual(self.client.get(f"/api/movements/{move['id']}",headers=self.headers(account)).status_code,403)
            self.assertEqual(self.snapshot(account)['movements'],[])
        self.dispatch(move)
        account = self.worker('owner',owner_id=self.owner['id'])
        snap = self.snapshot(account)
        self.assertEqual(snap['stock_summary'][0]['in_transit'],40)
        self.assertEqual(snap['stock_summary'][0]['physical_total'],100)
        self.assertTrue(snap['reconciliation']['ok'])
        other_owner = self.post('/owners',{'name':'Other owner'})
        other = self.worker('owner',owner_id=other_owner['id'])
        self.assertEqual(self.snapshot(other)['stock_summary'],[])

    def test_same_sku_string_of_other_owner_keeps_separate_inventory(self):
        self.replenish(10)
        other = self.post('/owners',{'name':'Other owner'})
        sku = self.post('/skus',{'owner_id':other['id'],'code':self.sku['code'],'barcode':self.sku['barcode'],'name':'Other'})
        self.put(8,sku=sku,owner=other)
        move = self.post('/movements',self.body(10,kind='MOVE'))
        self.dispatch(move)
        self.post(f"/movements/{move['id']}/receive",self.scan(move,True))
        self.assertEqual(sum(i['on_hand'] for i in self.snapshot()['inventory'] if i['owner_id']==other['id']),8)
        self.assertEqual(sum(i['on_hand'] for i in self.snapshot()['inventory'] if i['owner_id']==self.owner['id']),10)
        self.assertCustody(10,0,0,10,10)

    def test_in_transit_restart_and_independent_backup_restore(self):
        self.replenish()
        move = self.post('/movements',self.body())
        self.dispatch(move)
        restored = str(Path(self.temp.name)/'restored.sqlite3')
        with connect(self.db) as source,connect(restored) as destination:
            source.backup(destination)
        migrate(restored)
        with TestClient(create_app(restored)) as restarted:
            snap = restarted.get('/api/snapshot',headers=self.headers()).json()
            self.assertEqual(snap,self.snapshot())
            response = restarted.post(f"/api/movements/{move['id']}/receive",json=self.scan(move,True),headers=self.headers())
            self.assertEqual(response.status_code,200,response.text)
            snap = restarted.get('/api/snapshot',headers=self.headers()).json()
            self.assertEqual(snap['stock_summary'][0]['physical_total'],100)
            self.assertEqual(snap['stock_summary'][0]['in_transit'],0)
        self.assertCustody(60,0,40,100,60)

    def test_real_002_upgrade_preserves_active_wave_picks_and_ledger(self):
        self.replenish()
        order = self.reserved()
        wave = self.post('/waves',{'owner_id':self.owner['id'],'warehouse_id':self.warehouse['id'],'reference':'UPGRADE','order_ids':[order['id']]})
        task = self.snapshot()['pick_tasks'][0]
        self.post(f"/pick_tasks/{task['id']}/claim",{})
        self.post(f"/pick_tasks/{task['id']}/scan",{'barcode':self.sku['barcode'],'location_id':self.location['id'],'qty':1})
        legacy = str(Path(self.temp.name)/'legacy.sqlite3')
        migrations = Path(__file__).resolve().parents[1]/'app/migrations'
        with connect(self.db) as source,connect(legacy) as target:
            target.execute('CREATE TABLE schema_migrations(version TEXT PRIMARY KEY,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
            for name in ['001_initial.sql','002_waves.sql']:
                target.executescript((migrations/name).read_text())
                target.execute('INSERT INTO schema_migrations(version) VALUES (?)',(name,))
            for row in target.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'schema_migrations'").fetchall():
                table = row['name']
                columns = [r['name'] for r in target.execute(f'PRAGMA table_info({table})')]
                data = source.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall()
                target.executemany(f"INSERT INTO {table}({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",[tuple(r) for r in data])
        with TestClient(create_app(legacy)) as upgraded:
            self.assertEqual(upgraded.get('/health').status_code,503)
            migrate(legacy)
            migrate(legacy)
            self.assertEqual(upgraded.get('/health').status_code,200)
            snap = upgraded.get('/api/snapshot',headers=self.headers()).json()
            self.assertEqual(snap,self.snapshot())
        with connect(legacy) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
