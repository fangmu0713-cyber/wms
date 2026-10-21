"""Reconstructed wave acceptance from the prior chat's implementation record."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import provision
from app.db import connect, migrate, transaction
from app.main import create_app
from tests.domain_fixtures import DomainCase


class WaveTests(DomainCase):
    def body(self, orders):
        return {'owner_id': self.owner['id'], 'warehouse_id': self.warehouse['id'],
                'reference': str(uuid4()), 'order_ids': [o['id'] for o in orders]}

    def scan(self, **overrides):
        return {'barcode': self.sku['barcode'], 'location_id': self.location['id'], 'qty': 3, **overrides}

    def task(self, wave):
        return next(t for t in self.snapshot()['pick_tasks'] if t['wave_id'] == wave['id'])

    def test_full_flow_idempotency_restart_and_stock(self):
        self.replenish()
        orders = [self.reserved(3), self.reserved(2)]
        body, key = self.body(orders), str(uuid4())
        wave = self.post('/waves', body, key=key)
        self.assertEqual(self.post('/waves', body, key=key), wave)
        tasks = self.snapshot()['pick_tasks']
        worker = self.worker()
        for task in tasks:
            path = f"/pick_tasks/{task['id']}"
            self.post(path + '/claim', {}, account=worker)
            key, scan = str(uuid4()), self.scan(qty=task['qty'])
            result = self.post(path + '/scan', scan, account=worker, key=key)
            for _ in range(10):
                self.assertEqual(self.post(path + '/scan', scan, account=worker, key=key), result)
            self.denied(path + '/scan', scan, account=worker)
        self.assertStock(100, 95, 5, 5)
        self.assertEqual(self.snapshot()['waves'][0]['status'], 'COMPLETED')
        with connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ledger WHERE event_type='PICK'").fetchone()[0], 2)
        with TestClient(create_app(self.db)) as restarted:
            self.assertEqual(restarted.get('/api/snapshot', headers=self.headers()).json()['pick_tasks'], self.snapshot()['pick_tasks'])
        for order, qty in zip(orders, [3, 2]):
            self.post(f"/orders/{order['id']}/verify", {'barcode': self.sku['barcode'], 'qty': qty})
            self.post(f"/orders/{order['id']}/pack", {'package_reference': str(uuid4())})
            key = str(uuid4())
            ship = {'carrier': 'Test', 'tracking_number': str(uuid4())}
            self.post(f"/orders/{order['id']}/ship", ship, key=key)
            self.post(f"/orders/{order['id']}/ship", ship, key=key)
        self.assertStock(95, 95, 0, 0)

    def test_concurrent_wave_creation_and_claim(self):
        self.replenish()
        order = self.reserved()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.request('/waves', self.body([order])), range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        task = self.snapshot()['pick_tasks'][0]
        workers = [self.worker(), self.worker()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda a: self.request(f"/pick_tasks/{task['id']}/claim", {}, account=a), workers))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        loser = next(a for a, r in zip(workers, responses) if r.status_code != 200)
        self.assertEqual(self.denied(f"/pick_tasks/{task['id']}/scan", self.scan(), account=loser).status_code, 403)

    def test_guards_release_and_no_legacy_bypass(self):
        self.replenish()
        order = self.reserved()
        wave = self.post('/waves', self.body([order]))
        task = self.task(wave)
        path = f"/pick_tasks/{task['id']}"
        self.denied(path + '/scan', self.scan())
        self.denied(f"/orders/{order['id']}/pick", self.scan())
        self.post(path + '/claim', {})
        self.post(path + '/release', {})
        self.post(path + '/claim', {})
        for scan in [self.scan(barcode='wrong'), self.scan(qty=4), self.scan(location_id='wrong')]:
            self.denied(path + '/scan', scan)
        self.post(path + '/scan', self.scan(qty=1))
        self.denied(path + '/release', {})
        self.denied(f"/waves/{wave['id']}/cancel", {})
        self.denied(f"/orders/{order['id']}/cancel", {})
        self.assertStock(100, 97, 3, 1)

    def test_wave_cancel_preserves_reservations_and_rewave(self):
        self.replenish()
        order = self.reserved()
        wave = self.post('/waves', self.body([order]))
        task = self.task(wave)
        self.post(f"/pick_tasks/{task['id']}/claim", {})
        self.post(f"/waves/{wave['id']}/cancel", {})
        self.denied(f"/pick_tasks/{task['id']}/scan", self.scan())
        self.assertStock(100, 97, 3, 0)
        self.post('/waves', self.body([order]))

    def test_order_cancel_only_its_tasks(self):
        self.replenish()
        orders = [self.reserved(), self.reserved(2)]
        self.post('/waves', self.body(orders))
        self.post(f"/orders/{orders[0]['id']}/cancel", {})
        dead, live = [next(t for t in self.snapshot()['pick_tasks'] if t['order_id'] == order['id']) for order in orders]
        self.assertEqual(dead['status'], 'CANCELLED')
        self.post(f"/pick_tasks/{live['id']}/claim", {})
        self.post(f"/pick_tasks/{live['id']}/scan", self.scan(qty=2))
        self.assertEqual(self.snapshot()['waves'][0]['status'], 'COMPLETED')
        self.assertStock(100, 98, 2, 2)

    def test_atomic_selection_and_idempotency_conflict(self):
        self.replenish()
        good, unreserved = self.reserved(), self.order()
        other_owner = self.post('/owners',{'name':'Other owner'})
        other_sku = self.post('/skus',{'owner_id':other_owner['id'],'code':self.sku['code'],'barcode':self.sku['barcode'],'name':'Other owner SKU'})
        other_store = self.post('/stores',{'owner_id':other_owner['id'],'name':'Other store'})
        other_order = self.order(owner=other_owner,store=other_store,sku=other_sku)
        other_warehouse = self.post('/warehouses',{'name':'Other warehouse'})
        other_warehouse_order = self.order(warehouse=other_warehouse)
        for body in [self.body([good, unreserved]), self.body([good, good]), self.body([good,other_order]), self.body([good,other_warehouse_order]), {**self.body([good]), 'order_ids': [good['id'], 'missing']}]:
            self.denied('/waves', body)
            self.assertEqual(self.snapshot()['waves'], [])
        body, key = self.body([good]), str(uuid4())
        self.post('/waves', body, key=key)
        self.denied('/waves', {**body, 'reference': 'changed'}, key=key)
        self.denied('/waves', body)

    def test_tenant_owner_warehouse_and_roles(self):
        self.replenish()
        wave = self.post('/waves', self.body([self.reserved()]))
        task = self.task(wave)
        outsiders = [self.worker(warehouses=[]), provision(self.db, 'Other tenant', 'Other admin')]
        for account in outsiders:
            for table, row in [('waves', wave), ('pick_tasks', task)]:
                self.assertEqual(self.client.get(f"/api/{table}/{row['id']}", headers=self.headers(account)).status_code, 404)
            self.denied(f"/pick_tasks/{task['id']}/claim", {}, account=account)
            self.assertEqual(self.snapshot(account)['pick_tasks'], [])
        for role in ['owner', 'owner_readonly', 'receiver', 'packer', 'finance']:
            account = self.worker(role, **({'owner_id': self.owner['id']} if role.startswith('owner') else {}))
            self.assertEqual(self.denied(f"/pick_tasks/{task['id']}/claim", {}, account=account).status_code, 403)
            self.assertEqual(self.snapshot(account)['pick_tasks'], [])

    def test_route_multiple_skus_locations_partial_scan(self):
        second = self.post('/locations', {'warehouse_id': self.warehouse['id'], 'code': 'B-02'})
        sku2 = self.post('/skus', {'owner_id': self.owner['id'], 'code': 'SKU-002', 'barcode': '789000002', 'name': 'Second'})
        self.put(2)
        self.put(3, location=second)
        self.put(4, sku=sku2, location=second)
        order = self.post('/orders', {'owner_id': self.owner['id'], 'warehouse_id': self.warehouse['id'], 'store_id': self.store['id'], 'reference': 'MULTI', 'lines': [{'sku_id': self.sku['id'], 'qty': 5}, {'sku_id': sku2['id'], 'qty': 4}]})
        self.post(f"/orders/{order['id']}/reserve", {})
        self.post('/waves', self.body([order]))
        tasks = self.snapshot()['pick_tasks']
        self.assertEqual([(t['location_id'], t['sku_id']) for t in tasks], [(self.location['id'], self.sku['id']), (second['id'], self.sku['id']), (second['id'], sku2['id'])])
        for task in tasks:
            self.post(f"/pick_tasks/{task['id']}/claim", {})
            for _ in range(task['qty']):
                self.post(f"/pick_tasks/{task['id']}/scan", {'barcode': self.sku['barcode'] if task['sku_id'] == self.sku['id'] else sku2['barcode'], 'location_id': task['location_id'], 'qty': 1})
        self.assertStock(5, 0, 5, 5)

    def test_migration_and_existing_picked_orders(self):
        self.replenish()
        order = self.reserved()
        self.pick(order)
        with transaction(self.db) as db:
            for table in ['pick_tasks', 'wave_orders', 'waves']:
                db.execute(f'DROP TABLE {table}')
            db.execute("DELETE FROM schema_migrations WHERE version='002_waves.sql'")
        self.assertEqual(self.client.get('/health').status_code, 503)
        migrate(self.db)
        migrate(self.db)
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertStock(100, 97, 3, 3)
        self.assertEqual(self.snapshot()['pick_tasks'], [])

    def test_last_task_unit_concurrency(self):
        self.replenish(1)
        task = self.task(self.post('/waves', self.body([self.reserved(1)])))
        self.post(f"/pick_tasks/{task['id']}/claim", {})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.request(f"/pick_tasks/{task['id']}/scan", self.scan(qty=1)), range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        self.assertStock(1, 0, 1, 1)
