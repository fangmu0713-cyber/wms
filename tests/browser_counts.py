"""End-to-end blind count/recount and approval across real shipments."""
import json
import os
from pathlib import Path
import shutil
import socket
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
from uuid import uuid4
import httpx
from playwright.sync_api import sync_playwright, expect
import uvicorn
from app.auth import provision
from app.db import migrate
from app.main import create_app


class BrowserCountFlow(unittest.TestCase):
    def test_blind_recount_shipments_and_exactly_once_delta_approval(self):
        with TemporaryDirectory(prefix='wms-browser-count-') as directory:
            db_path = str(Path(directory)/'test.sqlite3')
            migrate(db_path)
            admin = provision(db_path,'Synthetic inventory count','Count administrator')
            listener = socket.socket()
            listener.bind(('127.0.0.1',0))
            base_url = f'http://127.0.0.1:{listener.getsockname()[1]}'
            server = uvicorn.Server(uvicorn.Config(create_app(db_path),log_level='warning',access_log=False))
            thread = Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
            thread.start()
            deadline = time.monotonic()+10
            while not server.started and time.monotonic()<deadline:
                time.sleep(0.05)
            self.assertTrue(server.started)
            evidence = Path(__file__).resolve().parents[1]/'evidence/stage4'
            evidence.mkdir(parents=True,exist_ok=True)
            try:
                with httpx.Client(base_url=base_url,headers={'Authorization':'Bearer '+admin['token']}) as api,sync_playwright() as playwright:
                    def post(path,body):
                        response = api.post('/api'+path,json=body,headers={'Idempotency-Key':str(uuid4())})
                        self.assertEqual(response.status_code,200,response.text)
                        return response.json()
                    owner = post('/owners',{'name':'盘点验收测试货主'})
                    warehouse = post('/warehouses',{'name':'São Paulo · Count test'})
                    location = post('/locations',{'warehouse_id':warehouse['id'],'code':'COUNT-01'})
                    sku = post('/skus',{'owner_id':owner['id'],'code':'COUNT-SKU','barcode':'789000004','name':'盘点测试商品'})
                    store = post('/stores',{'owner_id':owner['id'],'name':'Loja de teste'})
                    receipt = post('/receipts',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'sku_id':sku['id'],'reference':'COUNT-IN-100','qty':100})
                    post(f"/receipts/{receipt['id']}/qc",{'accepted_qty':100,'rejected_qty':0})
                    post(f"/receipts/{receipt['id']}/putaway",{'location_id':location['id']})
                    first = provision(db_path,'','初盘员 A',role='picker',tenant_id=admin['tenant_id'],warehouse_ids=[warehouse['id']],count_only=True)
                    second = provision(db_path,'','Recontador B',role='picker',tenant_id=admin['tenant_id'],warehouse_ids=[warehouse['id']],count_only=True)
                    browser = playwright.chromium.launch(headless=True,executable_path=os.environ.get('WMS_BROWSER_EXECUTABLE') or shutil.which('chromium'),args=['--no-sandbox'])
                    try:
                        page = browser.new_page(viewport={'width':1440,'height':1000})
                        errors = []
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        page.goto(base_url)
                        def login(account):
                            page.locator('#api-token').fill(account['token'])
                            page.locator('#login-form button').click()
                            expect(page.locator('#connected-content')).to_be_visible()
                            expect(page.locator('#refresh')).to_be_enabled()
                        def submit(action,fields,drop_endpoint=None):
                            page.locator('[data-view=counts]').click()
                            form = page.locator(f'#{action}-form')
                            for name,value in fields.items():
                                control = form.locator(f'[name="{name}"]')
                                if control.evaluate('el => el.tagName')=='SELECT':
                                    control.select_option(value)
                                else:
                                    control.fill(str(value))
                            lost = {}
                            if drop_endpoint:
                                endpoint = base_url+drop_endpoint
                                def drop(route):
                                    upstream = route.fetch()
                                    self.assertEqual(upstream.status,200)
                                    lost['key'] = route.request.headers['idempotency-key']
                                    route.abort('failed')
                                page.route(endpoint,drop,times=1)
                                form.locator('[type=submit]').click()
                                expect(form.locator('.form-result')).to_have_class('form-result error')
                                expect(form.locator('select').first).to_be_disabled()
                            with page.expect_response(lambda r:r.request.method=='POST' and '/api/' in r.url) as response:
                                form.locator('[type=submit]').click()
                            self.assertEqual(response.value.status,200)
                            if drop_endpoint:
                                self.assertEqual(response.value.request.headers['idempotency-key'],lost['key'])
                            expect(form.locator('.form-result')).to_have_class('form-result success')
                            expect(page.locator('#refresh')).to_be_enabled()
                            return response.value.json()
                        def ship(qty):
                            order = post('/orders',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'store_id':store['id'],'reference':str(uuid4()),'lines':[{'sku_id':sku['id'],'qty':qty}]})
                            post(f"/orders/{order['id']}/reserve",{})
                            post(f"/orders/{order['id']}/pick",{'barcode':sku['barcode'],'location_id':location['id'],'qty':qty})
                            post(f"/orders/{order['id']}/verify",{'barcode':sku['barcode'],'qty':qty})
                            post(f"/orders/{order['id']}/pack",{'package_reference':str(uuid4())})
                            post(f"/orders/{order['id']}/ship",{'carrier':'Test carrier','tracking_number':str(uuid4())})
                        def blind_snapshot(account):
                            response = api.get('/api/snapshot',headers={'Authorization':'Bearer '+account['token']})
                            self.assertEqual(response.status_code,200)
                            snap = response.json()
                            for name in ['inventory','ledger','stock_summary','stock_counts','count_lines','orders','receipts','count_operators']:
                                self.assertEqual(snap[name],[])
                            for task in snap['count_attempts']:
                                self.assertFalse({'baseline_on_hand','delta','cutoff_seq'} & task.keys())
                            return snap

                        login(admin)
                        session = submit('count-create',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'sku_id':sku['id'],'location_ids':[location['id']],'reference':'COUNT-BROWSER','counter_id':first['user_id']})
                        page.locator('#logout').click()
                        login(first)
                        expect(page.locator('#page-title')).to_have_text('盘点与复盘')
                        expect(page.locator('[data-view=inventory]')).to_be_hidden()
                        expect(page.locator('#count-create-form')).to_be_hidden()
                        expect(page.locator('#count-submit-form')).to_be_visible()
                        first_task = blind_snapshot(first)['count_attempts'][0]
                        self.assertNotIn('截点账面',page.locator('#count-attempt-records').inner_text())
                        self.assertEqual(api.get(f"/api/count_attempts/{first_task['id']}",headers={'Authorization':'Bearer '+second['token']}).status_code,404)
                        submit('count-submit',{'attempt_id':first_task['id'],'barcode':sku['barcode'],'location_id':location['id'],'qty':98},drop_endpoint=f"/api/count_attempts/{first_task['id']}/submit")
                        page.screenshot(path=str(evidence/'count-zh-blind.png'),full_page=True)
                        snap = api.get('/api/snapshot').json()
                        self.assertEqual(snap['inventory'][0]['count_reserved'],2)
                        ship(3)
                        page.locator('#logout').click()
                        login(admin)
                        line = api.get('/api/snapshot').json()['count_lines'][0]
                        attempt = submit('count-recount',{'line_id':line['id'],'counter_id':second['user_id']})
                        self.assertEqual(attempt['baseline_on_hand'],97)
                        page.locator('#logout').click()
                        login(second)
                        page.locator('#language').select_option('pt-BR')
                        page.set_viewport_size({'width':390,'height':844})
                        second_task = blind_snapshot(second)['count_attempts'][0]
                        self.assertEqual(second_task['round'],2)
                        submit('count-submit',{'attempt_id':second_task['id'],'barcode':sku['barcode'],'location_id':location['id'],'qty':95})
                        self.assertNotIn('Saldo no corte',page.locator('#count-attempt-records').inner_text())
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                        page.screenshot(path=str(evidence/'count-pt-mobile.png'),full_page=True)
                        ship(5)
                        page.locator('#logout').click()
                        login(admin)
                        page.locator('#language').select_option('zh-CN')
                        page.set_viewport_size({'width':1440,'height':1000})
                        submit('count-approve',{'session_id':session['id'],'reason':'两名独立盘点员确认差异，保留截点后的出库流水'},drop_endpoint=f"/api/stock_counts/{session['id']}/approve")
                        final = api.get('/api/snapshot').json()
                        self.assertEqual(final['stock_counts'][0]['status'],'APPROVED')
                        self.assertEqual(final['inventory'][0]['on_hand'],90)
                        self.assertEqual(final['inventory'][0]['count_reserved'],0)
                        adjustments = [e for e in final['ledger'] if e['event_type']=='COUNT_ADJUST']
                        self.assertEqual(len(adjustments),1)
                        self.assertEqual(adjustments[0]['on_hand_delta'],-2)
                        self.assertTrue(final['reconciliation']['ok'])
                        page.screenshot(path=str(evidence/'count-zh-approved.png'),full_page=True)
                        self.assertEqual(errors,[])
                        self.assertEqual(page.evaluate('Object.keys(localStorage).length+Object.keys(sessionStorage).length'),0)
                        report = {'environment':'isolated SQLite; synthetic data; real browser/HTTP',
                            'scope':'one SKU, one specified bin','first':{'baseline':100,'observed':98,'held':2},
                            'recount':{'baseline_after_shipment':97,'observed':95,'delta':-2,'different_operator':True},
                            'subsequent_shipments':[3,5],'book_before_approval':92,'after_delta_approval':90,
                            'count_adjust_events':1,'blind_api_book_fields_absent':True,'other_operator_attempt_denied':True,
                            'committed_response_loss_retry':['blind submission','administrator approval'],
                            'reconciliation':final['reconciliation'],'javascript_errors':errors,
                            'languages':['zh-CN','pt-BR'],'viewports':['1440x1000','390x844'],
                            'physical_devices_tested':False,'erp_connected':False}
                        (evidence/'browser-counts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                    finally:
                        browser.close()
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                listener.close()


if __name__=='__main__':
    unittest.main()
