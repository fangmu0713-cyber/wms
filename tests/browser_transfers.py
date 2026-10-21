"""Real local trial: two warehouse accounts, partial arrivals and loss closure."""
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
from app.main import create_app
from scripts.local_trial import prepare


class BrowserTransferFlow(unittest.TestCase):
    def test_trial_partial_receiving_scoped_accounts_retry_and_loss_closure(self):
        with TemporaryDirectory(prefix='wms-browser-transfer-') as root:
            db_path, credentials = prepare(Path(root)/'trial')
            accounts = json.loads(credentials.read_text())['accounts']
            listener = socket.socket()
            listener.bind(('127.0.0.1',0))
            base_url = f'http://127.0.0.1:{listener.getsockname()[1]}'
            server = uvicorn.Server(uvicorn.Config(create_app(db_path),log_level='warning',access_log=False))
            thread = Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
            thread.start()
            evidence = Path(__file__).resolve().parents[1]/'evidence/stage5'
            evidence.mkdir(parents=True,exist_ok=True)
            try:
                deadline = time.monotonic()+10
                while not server.started and time.monotonic()<deadline:
                    time.sleep(0.05)
                self.assertTrue(server.started)
                with httpx.Client(base_url=base_url,headers={'Authorization':'Bearer '+accounts['admin']['token']}) as api, sync_playwright() as p:
                    snap = api.get('/api/snapshot').json()
                    source = snap['inventory'][0]
                    destination = next(w for w in snap['warehouses'] if w['id'] != source['warehouse_id'])
                    locations = [l for l in snap['locations'] if l['warehouse_id']==destination['id']]
                    sku = snap['skus'][0]
                    browser = p.chromium.launch(headless=True,executable_path=os.environ.get('WMS_BROWSER_EXECUTABLE') or shutil.which('chromium'),args=['--no-sandbox'])
                    try:
                        page = browser.new_page(viewport={'width':1440,'height':1000})
                        errors = []
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        page.goto(base_url)
                        expect(page.locator('.skip-link')).to_have_css('opacity','0')
                        page.keyboard.press('Tab')
                        expect(page.locator('.skip-link')).to_be_focused()
                        expect(page.locator('.skip-link')).to_have_css('opacity','1')
                        page.keyboard.press('Tab')
                        expect(page.locator('.skip-link')).to_have_css('opacity','0')
                        def login(label):
                            page.locator('#api-token').fill(accounts[label]['token'])
                            page.locator('#login-form button').click()
                            expect(page.locator('#connected-content')).to_be_visible()
                            expect(page.locator('#refresh')).to_be_enabled()
                        def submit(action,fields,drop=False,status=200):
                            page.locator('[data-view=transfers]').click()
                            form = page.locator(f'#{action}-form')
                            for name,value in fields.items():
                                control = form.locator(f'[name="{name}"]')
                                if control.evaluate('el => el.tagName')=='SELECT':
                                    control.select_option(value)
                                else:
                                    control.fill(str(value))
                            lost = {}
                            if drop:
                                suffix = 'receive' if action=='transfer-receive' else 'close_loss'
                                endpoint = base_url+f"/api/transfers/{fields['transfer_id']}/{suffix}"
                                def lose(route):
                                    result = route.fetch()
                                    self.assertEqual(result.status,200)
                                    lost['key'] = route.request.headers['idempotency-key']
                                    route.abort('failed')
                                page.route(endpoint,lose,times=1)
                                form.locator('[type=submit]').click()
                                expect(form.locator('.form-result')).to_have_class('form-result error')
                                expect(form.locator('[name=qty]')).to_be_disabled()
                            with page.expect_response(lambda r:r.request.method=='POST' and '/api/' in r.url) as response:
                                form.locator('[type=submit]').click()
                            self.assertEqual(response.value.status,status,response.value.text())
                            if drop:
                                self.assertEqual(lost['key'],response.value.request.headers['idempotency-key'])
                            expect(form.locator('.form-result')).to_have_class('form-result success' if status==200 else 'form-result error')
                            expect(page.locator('#refresh')).to_be_enabled()
                            return response.value.json()
                        def check(hand,transit,lost=0):
                            snapshot = api.get('/api/snapshot').json()
                            self.assertTrue(snapshot['reconciliation']['ok'],snapshot['reconciliation'])
                            self.assertEqual(sum(i['on_hand'] for i in snapshot['inventory']),hand)
                            self.assertEqual(sum(i['transfer_in_transit'] for i in snapshot['stock_summary']),transit)
                            self.assertEqual(sum(i['transfer_lost'] for i in snapshot['stock_summary']),lost)
                            self.assertEqual(sum(i['physical_total'] for i in snapshot['stock_summary']),hand+transit)
                            return snapshot
                        login('admin')
                        t = submit('transfer-create',{'source_inventory_id':source['id'],'destination_warehouse_id':destination['id'],'reference':'BROWSER-XFER-20','qty':20})
                        check(100,0)
                        self.assertEqual(api.get('/api/snapshot').json()['inventory'][0]['available'],80)
                        page.locator('#logout').click()
                        login('source_picker')
                        expect(page.locator('#transfer-create-form')).to_be_hidden()
                        expect(page.locator('#transfer-receive-form')).to_be_hidden()
                        submit('transfer-dispatch',{'transfer_id':t['id'],'barcode':sku['barcode'],'location_id':source['location_id'],'qty':20,'carrier':'示例承运方','tracking_number':'TRIAL-XFER-20'})
                        check(80,20)
                        page.screenshot(path=str(evidence/'transfer-zh-dispatched.png'),full_page=True)
                        page.locator('#logout').click()
                        login('destination_receiver')
                        expect(page.locator('#transfer-dispatch-form')).to_be_hidden()
                        expect(page.locator('#transfer-loss-form')).to_be_hidden()
                        page.locator('#language').select_option('pt-BR')
                        page.set_viewport_size({'width':390,'height':844})
                        submit('transfer-receive',{'transfer_id':t['id'],'barcode':'wrong','location_id':locations[0]['id'],'qty':7,'receipt_reference':'BATCH-1'},status=409)
                        expect(page.locator('#transfer-receive-form .form-result')).to_contain_text('Código de barras')
                        submit('transfer-receive',{'transfer_id':t['id'],'barcode':sku['barcode'],'location_id':locations[0]['id'],'qty':7,'receipt_reference':'BATCH-1'},drop=True)
                        check(87,13)
                        submit('transfer-receive',{'transfer_id':t['id'],'barcode':sku['barcode'],'location_id':locations[0]['id'],'qty':7,'receipt_reference':'BATCH-1'},status=409)
                        expect(page.locator('#transfer-receive-form .form-result')).to_contain_text('Lote já registrado')
                        submit('transfer-receive',{'transfer_id':t['id'],'barcode':sku['barcode'],'location_id':locations[1]['id'],'qty':8,'receipt_reference':'BATCH-2'})
                        check(95,5)
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                        page.screenshot(path=str(evidence/'transfer-pt-partial-mobile.png'),full_page=True)
                        page.locator('#logout').click()
                        login('admin')
                        page.locator('#language').select_option('zh-CN')
                        page.set_viewport_size({'width':1440,'height':1000})
                        submit('transfer-loss',{'transfer_id':t['id'],'qty':5,'reason':'示例验收：承运方确认剩余五件在途丢失，凭据已核对'},drop=True)
                        final = check(95,0,5)
                        self.assertEqual(final['transfers'][0]['status'],'CLOSED_WITH_LOSS')
                        self.assertEqual([e['kind'] for e in final['transfer_events']].count('RECEIVE'),2)
                        self.assertEqual([e['kind'] for e in final['transfer_events']].count('LOSS'),1)
                        expect(page.locator('#transfer-records')).to_contain_text('在途丢失结案')
                        page.screenshot(path=str(evidence/'transfer-zh-closed.png'),full_page=True)
                        # Clear privileged inventory from the DOM before switching roles.
                        page.locator('[data-view=inventory]').click()
                        expect(page.locator('#inventory-records table')).to_have_count(1)
                        # Counter scope must stay isolated after adding transfer data.
                        page.locator('#logout').click()
                        login('counter_a')
                        expect(page.locator('[data-view=transfers]')).to_be_hidden()
                        expect(page.locator('#transfer-records')).to_be_empty()
                        for selector in ['#inventory-records','#ledger-records','#stock-quality-records','#order-records','#receipt-records','#master-records']:
                            expect(page.locator(selector)).to_be_empty()
                        expect(page.locator('#transfer-receive-transfer_id option[value="'+t['id']+'"]')).to_have_count(0)
                        blind = api.get('/api/snapshot',headers={'Authorization':'Bearer '+accounts['counter_a']['token']}).json()
                        self.assertEqual(blind['transfers'],[])
                        self.assertEqual(blind['transfer_events'],[])
                        self.assertEqual(page.evaluate('Object.keys(localStorage).length+Object.keys(sessionStorage).length'),0)
                        self.assertEqual(errors,[])
                        report = {'environment':'isolated local trial; synthetic stock; real SQLite/HTTP/Chromium',
                            'initial':100,'dispatched':20,'received_batches':[7,8],'confirmed_transit_loss':5,
                            'final_source':80,'final_destination':15,'final_physical':95,'final_transit':0,
                            'source_only_dispatch':True,'destination_only_receive':True,'count_only_hidden':True,'previous_account_business_dom_cleared':True,
                            'duplicate_batch_rejected':True,'response_loss_same_key_retry':['receive batch','loss close'],
                            'reconciliation':final['reconciliation'],'languages':['zh-CN','pt-BR'],
                            'viewports':['1440x1000','390x844'],'javascript_errors':errors,
                            'production_deployed':False,'physical_devices_tested':False,'erp_connected':False}
                        (evidence/'browser-transfers.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                    finally:
                        browser.close()
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                listener.close()


if __name__=='__main__':
    unittest.main()
