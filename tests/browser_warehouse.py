"""Browser acceptance for reconstructed waves and same-warehouse movement."""
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


class BrowserWarehouseFlow(unittest.TestCase):
    def test_movements_custody_retry_waves_and_shipping(self):
        with TemporaryDirectory(prefix='wms-browser-warehouse-') as directory:
            db_path = str(Path(directory)/'test.sqlite3')
            migrate(db_path)
            admin = provision(db_path,'Synthetic warehouse test','Warehouse test administrator')
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
            evidence = Path(__file__).resolve().parents[1]/'evidence/stage3'
            evidence.mkdir(parents=True,exist_ok=True)
            try:
                with httpx.Client(base_url=base_url,headers={'Authorization':'Bearer '+admin['token']}) as api,sync_playwright() as playwright:
                    def post(path,body):
                        response = api.post('/api'+path,json=body,headers={'Idempotency-Key':str(uuid4())})
                        self.assertEqual(response.status_code,200,response.text)
                        return response.json()

                    owner = post('/owners',{'name':'验收测试货主'})
                    warehouse = post('/warehouses',{'name':'São Paulo · Test'})
                    source = post('/locations',{'warehouse_id':warehouse['id'],'code':'A-01'})
                    destination = post('/locations',{'warehouse_id':warehouse['id'],'code':'PICK-01'})
                    sku = post('/skus',{'owner_id':owner['id'],'code':'WAREHOUSE-SKU','barcode':'789123456','name':'库内作业测试商品'})
                    store = post('/stores',{'owner_id':owner['id'],'name':'Loja de teste'})
                    receipt = post('/receipts',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'sku_id':sku['id'],'reference':'IN-100','qty':100})
                    post(f"/receipts/{receipt['id']}/qc",{'accepted_qty':100,'rejected_qty':0})
                    post(f"/receipts/{receipt['id']}/putaway",{'location_id':source['id']})
                    source_inventory = api.get('/api/snapshot').json()['inventory'][0]
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

                        def submit(view,action,fields,drop_response=False,expect_status=200):
                            page.locator(f'[data-view="{view}"]').click()
                            form = page.locator(f'#{action}-form')
                            for name,value in fields.items():
                                control = form.locator(f'[name="{name}"]')
                                if control.evaluate('el => el.tagName')=='SELECT':
                                    control.select_option(value)
                                else:
                                    control.fill(str(value))
                            lost = {}
                            if drop_response:
                                endpoint = base_url+'/api/movements/'+fields['move_id']+'/receive'
                                def drop(route):
                                    upstream = route.fetch()
                                    self.assertEqual(upstream.status,200)
                                    lost['key'] = route.request.headers['idempotency-key']
                                    route.abort('failed')
                                page.route(endpoint,drop,times=1)
                                form.locator('[type=submit]').click()
                                expect(form.locator('.form-result')).to_have_class('form-result error')
                                expect(form.locator('[name=qty]')).to_be_disabled()
                            with page.expect_response(lambda r:r.request.method=='POST' and '/api/' in r.url) as response:
                                form.locator('[type=submit]').click()
                            self.assertEqual(response.value.status,expect_status)
                            if drop_response:
                                self.assertEqual(response.value.request.headers['idempotency-key'],lost['key'])
                            expect(form.locator('.form-result')).to_have_class('form-result success' if expect_status==200 else 'form-result error')
                            expect(page.locator('#refresh')).to_be_enabled()
                            return response.value.json()

                        def check(on_hand,held,transit,available):
                            snap = api.get('/api/snapshot').json()
                            summary = snap['stock_summary'][0]
                            self.assertEqual({k:summary[k] for k in ['on_hand','move_reserved','in_transit','available','physical_total']},
                                {'on_hand':on_hand,'move_reserved':held,'in_transit':transit,'available':available,'physical_total':on_hand+transit})
                            self.assertTrue(snap['reconciliation']['ok'])
                            return snap

                        login(admin)
                        move = submit('movements','movement',{'source_inventory_id':source_inventory['id'],'destination_location_id':destination['id'],'kind':'REPLENISHMENT','reference':'BROWSER-REPLENISH-40','qty':40})
                        check(100,40,0,60)
                        submit('movements','movement-claim',{'move_id':move['id']})
                        submit('movements','movement-dispatch',{'move_id':move['id'],'barcode':sku['barcode'],'location_id':source['id'],'qty':40})
                        check(60,0,40,60)
                        expect(page.locator(f'#movement-cancel-move_id option[value="{move["id"]}"]')).to_have_count(0)
                        page.locator('[data-view=inventory]').click()
                        expect(page.locator('#stock-quality-records')).to_contain_text('40')
                        page.screenshot(path=str(evidence/'movement-zh-custody.png'),full_page=True)
                        owner_account = provision(db_path,'','Test owner',role='owner',owner_id=owner['id'],tenant_id=admin['tenant_id'],warehouse_ids=[warehouse['id']])
                        page.locator('#logout').click()
                        login(owner_account)
                        expect(page.locator('[data-view=movements]')).to_be_hidden()
                        expect(page.locator('[data-view=waves]')).to_be_hidden()
                        page.locator('[data-view=inventory]').click()
                        expect(page.locator('#stock-quality-records')).to_contain_text('40')
                        page.locator('#logout').click()
                        login(admin)
                        page.locator('#language').select_option('pt-BR')
                        page.set_viewport_size({'width':390,'height':844})
                        submit('movements','movement-receive',{'move_id':move['id'],'barcode':'wrong','location_id':destination['id'],'qty':40},expect_status=409)
                        expect(page.locator('#movement-receive-form .form-result')).to_contain_text('Produto, endereço ou quantidade incorreta')
                        submit('movements','movement-receive',{'move_id':move['id'],'barcode':sku['barcode'],'location_id':destination['id'],'qty':40},drop_response=True)
                        check(100,0,0,100)
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                        page.screenshot(path=str(evidence/'movement-pt-mobile.png'),full_page=True)
                        # Exercise the second task kind and cancellation with stock held.
                        destination_inventory = next(i for i in api.get('/api/snapshot').json()['inventory'] if i['location_id']==destination['id'])
                        cancel = submit('movements','movement',{'source_inventory_id':destination_inventory['id'],'destination_location_id':source['id'],'kind':'MOVE','reference':'BROWSER-CANCEL-5','qty':5})
                        check(100,5,0,95)
                        submit('movements','movement-cancel',{'move_id':cancel['id']})
                        check(100,0,0,100)
                        orders = []
                        for number,qty in enumerate([3,2],1):
                            order = post('/orders',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'store_id':store['id'],'reference':f'ORDER-{number}','lines':[{'sku_id':sku['id'],'qty':qty}]})
                            post(f"/orders/{order['id']}/reserve",{})
                            orders.append(order)
                        page.locator('#refresh').click()
                        expect(page.locator('#refresh')).to_be_enabled()
                        wave = submit('waves','wave',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'reference':'BROWSER-WAVE','order_ids':[o['id'] for o in orders]})
                        tasks = api.get('/api/snapshot').json()['pick_tasks']
                        self.assertEqual(len(tasks),2)
                        for task in tasks:
                            submit('waves','task-claim',{'task_id':task['id']})
                            submit('waves','task-scan',{'task_id':task['id'],'barcode':sku['barcode'],'location_id':task['location_id'],'qty':task['qty']})
                        check(100,0,0,95)
                        self.assertEqual(api.get('/api/snapshot').json()['waves'][0]['status'],'COMPLETED')
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                        page.screenshot(path=str(evidence/'waves-pt-mobile.png'),full_page=True)
                        for order,qty in zip(orders,[3,2]):
                            submit('pda','verify',{'order_id':order['id'],'barcode':sku['barcode'],'qty':qty})
                            submit('pda','pack',{'order_id':order['id'],'package_reference':'PKG-'+order['reference']})
                            submit('pda','ship',{'order_id':order['id'],'tracking_number':'TRACK-'+order['reference'],'carrier':'Test carrier'})
                        final = check(95,0,0,95)
                        self.assertEqual(page.evaluate('Object.keys(localStorage).length+Object.keys(sessionStorage).length'),0)
                        self.assertEqual(errors,[])
                        report = {'environment':'isolated SQLite; synthetic data; real HTTP/browser',
                            'movement':{'qty':40,'after_hold':{'on_hand':100,'move_reserved':40,'available':60,'physical_total':100},
                                'after_dispatch':{'on_hand':60,'in_transit':40,'physical_total':100},
                                'after_receive':{'on_hand':100,'in_transit':0,'physical_total':100}},
                            'committed_receive_response_loss':'same-key retry; one destination credit',
                            'pre_dispatch_cancel_tested':True,'owner_task_ui_hidden':True,'wave_orders':2,'wave_picked':5,
                            'after_shipping':{'on_hand':95,'reserved':0,'picked':0,'move_reserved':0,'in_transit':0},
                            'reconciliation':final['reconciliation'],'languages':['zh-CN','pt-BR'],'viewports':['1440x1000','390x844'],
                            'javascript_errors':errors,'physical_devices_tested':False,'erp_connected':False}
                        (evidence/'browser-warehouse.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                    finally:
                        browser.close()
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                listener.close()


if __name__=='__main__':
    unittest.main()
