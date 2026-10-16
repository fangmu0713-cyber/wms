"""Disposable, network-isolated Docker acceptance. Touches only resources it creates."""
import json
import os
import subprocess
import time
from uuid import uuid4


def docker(*args, input=None):
    return subprocess.run(['docker',*args],input=input,text=True,capture_output=True,check=True).stdout.strip()


FLOW = r'''
import json, urllib.request
from uuid import uuid4
from app.auth import provision
from app.db import default_path
credential = provision(default_path(),'Container synthetic test','Container operator')
base = 'http://127.0.0.1:8000'
def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(base+path,headers={'Authorization':'Bearer '+credential['token']})))
def post(path,body):
    headers = {'Authorization':'Bearer '+credential['token'],'Content-Type':'application/json','Idempotency-Key':str(uuid4())}
    return json.load(urllib.request.urlopen(urllib.request.Request(base+'/api/'+path,json.dumps(body).encode(),headers=headers)))
assert get('/health')['status']=='ok'
owner=post('owners',{'name':'Synthetic owner'})
warehouse=post('warehouses',{'name':'Synthetic Sao Paulo'})
location=post('locations',{'warehouse_id':warehouse['id'],'code':'A-01'})
sku=post('skus',{'owner_id':owner['id'],'code':'SMOKE','barcode':'SMOKE001','name':'Synthetic item'})
store=post('stores',{'owner_id':owner['id'],'name':'Synthetic store'})
receipt=post('receipts',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'sku_id':sku['id'],'reference':'SMOKE-IN','qty':100})
post('receipts/'+receipt['id']+'/qc',{'accepted_qty':100,'rejected_qty':0})
post('receipts/'+receipt['id']+'/putaway',{'location_id':location['id']})
order=post('orders',{'owner_id':owner['id'],'warehouse_id':warehouse['id'],'store_id':store['id'],'reference':'SMOKE-OUT','lines':[{'sku_id':sku['id'],'qty':3}]})
path='orders/'+order['id']+'/'
post(path+'reserve',{})
post(path+'pick',{'barcode':sku['barcode'],'location_id':location['id'],'qty':3})
post(path+'verify',{'barcode':sku['barcode'],'qty':3})
post(path+'pack',{'package_reference':'SYNTHETIC-PACK'})
assert get('/api/snapshot')['inventory'][0]['on_hand']==100
post(path+'ship',{'tracking_number':'SYNTHETIC-TRACK','carrier':'Internal acceptance'})
snapshot=get('/api/snapshot')
assert snapshot['inventory'][0]['on_hand']==97
assert snapshot['reconciliation']['ok']
assert snapshot['stock_summary'][0]['physical_total']==97
assert all(not x['configured'] for x in snapshot['integrations'])
assert b'<html' in urllib.request.urlopen(base+'/').read()
assert urllib.request.urlopen(base+'/static/app.js').status==200
schema=get('/openapi.json')
assert 'Idempotency-Key' in str(schema) or 'idempotency-key' in str(schema)
print(json.dumps({'http_flow':'100 -> reserve/pick/pack 3 -> ship -> 97','reconciliation':True,'non_root_uid':__import__('os').getuid(),'erp_enabled':False}))
'''


def main():
    name = 'wms-acceptance-' + uuid4().hex[:10]
    volume = name + '-data'
    started = time.perf_counter()
    docker('volume','create',volume)
    try:
        docker('run','-d','--name',name,'--network','none','--read-only','--tmpfs','/tmp:rw,size=32m',
               '--cap-drop','ALL','--security-opt','no-new-privileges','-v',volume+':/data','overseas-wms:0.1.0')
        def ready():
            for _ in range(30):
                try:
                    docker('exec',name,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)")
                    return
                except subprocess.CalledProcessError:
                    time.sleep(0.2)
            raise RuntimeError('container readiness timeout')
        ready()
        result = json.loads(docker('exec','-i',name,'python','-',input=FLOW))
        docker('restart',name)
        ready()
        check = "from app.db import connect,default_path; db=connect(default_path()); assert db.execute('select sum(on_hand) from inventory').fetchone()[0]==97; assert db.execute(\"select count(*) from orders where status='SHIPPED'\").fetchone()[0]==1; print('persisted')"
        result['restart_persistence'] = docker('exec',name,'python','-c',check)=='persisted'
        result['network'] = 'none; no published ports'
        result['elapsed_seconds'] = round(time.perf_counter()-started,3)
        print(json.dumps(result,indent=2))
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True)
        subprocess.run(['docker','volume','rm',volume],capture_output=True)

if __name__=='__main__':
    main()
