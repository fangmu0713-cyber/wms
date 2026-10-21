"""Explicit, loopback-only trial with synthetic data in a separate new directory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from app import service as s
from app.auth import provision, digest
from app.db import migrate, transaction, connect

FORMAT = 'wms-isolated-local-trial-v1'


def prepare(directory):
    directory = Path(directory).absolute()
    if directory.is_symlink():
        raise ValueError('Trial directory must not be a symlink')
    database = directory/'trial.sqlite3'
    credentials = directory/'accounts.token'
    if directory.exists():
        if not credentials.is_file() or credentials.is_symlink() or not database.is_file() or database.is_symlink():
            raise ValueError('Existing directory is not a complete trial. Choose a new --directory; nothing was overwritten.')
        data = json.loads(credentials.read_text())
        if data.get('format') != FORMAT:
            raise ValueError('Unrecognized trial; choose a new directory')
        with connect(database) as db:
            for account in data['accounts'].values():
                row = db.execute('SELECT * FROM users WHERE id=? AND token_hash=? AND active=1',
                                 (account['user_id'],digest(account['token']))).fetchone()
                if not row or row['tenant_id'] != data['tenant_id'] or (row['expires_at'] and datetime.fromisoformat(row['expires_at'])<=datetime.now(timezone.utc)):
                    raise ValueError('Trial credentials expired, revoked or mismatched; choose a new trial directory or use the administrator CLI.')
        migrate(database)
        return database, credentials
    directory.mkdir(parents=True, mode=0o700)
    migrate(database)
    admin = provision(database,'本地试用 · 示例公司','试用管理员')
    with transaction(database) as db:
        actor = dict(db.execute('SELECT * FROM users WHERE id=?',(admin['user_id'],)).fetchone())
        def execute(action, operation):
            key = str(uuid4())
            result = operation(key)
            s.insert(db,'audit',{'tenant_id':actor['tenant_id'],'actor_id':actor['id'],
                'action':'LOCAL_TRIAL_PREPARE:'+action,'resource_id':result['id'],
                'idempotency_key':key,'created_at':s.now()})
            db.execute('INSERT INTO idempotency VALUES (?,?,?,?,?,?)',
                (actor['tenant_id'],actor['id'],key,hashlib.sha256(('local-trial:'+action).encode()).hexdigest(),json.dumps(result),s.now()))
            return result
        def master(table,data):
            return execute(table,lambda key:s.create_master(db,actor,table,data))
        owner = master('owners',{'name':'示例货主 · 仅供试用'})
        source = master('warehouses',{'name':'示例圣保罗仓','timezone':'America/Sao_Paulo'})
        destination = master('warehouses',{'name':'示例里约仓','timezone':'America/Sao_Paulo'})
        source_bin = master('locations',{'warehouse_id':source['id'],'code':'SP-A01'})
        master('locations',{'warehouse_id':source['id'],'code':'SP-A02'})
        master('locations',{'warehouse_id':destination['id'],'code':'RIO-A01'})
        master('locations',{'warehouse_id':destination['id'],'code':'RIO-A02'})
        sku = master('skus',{'owner_id':owner['id'],'code':'TRIAL-SKU-01','barcode':'789000000001','name':'示例商品 · 非真实库存'})
        store = master('stores',{'owner_id':owner['id'],'name':'示例店铺'})
        receipt = execute('receipt',lambda key:s.create_receipt(db,actor,{'owner_id':owner['id'],'warehouse_id':source['id'],'sku_id':sku['id'],'reference':'TRIAL-IN-100','qty':100}))
        execute('qc',lambda key:s.receipt_action(db,actor,key,receipt['id'],'qc',{'accepted_qty':100,'rejected_qty':0}))
        execute('putaway',lambda key:s.receipt_action(db,actor,key,receipt['id'],'putaway',{'location_id':source_bin['id']}))
        execute('order',lambda key:s.create_order(db,actor,{'owner_id':owner['id'],'warehouse_id':source['id'],'store_id':store['id'],'reference':'TRIAL-ORDER-3','lines':[{'sku_id':sku['id'],'qty':3}]}))
    accounts = {'admin':admin}
    for label, name, role, warehouses, count_only in (
        ('source_picker','源仓发货/拣货员','picker',[source['id']],False),
        ('destination_receiver','目标仓收货员','receiver',[destination['id']],False),
        ('counter_a','初盘员 A','picker',[source['id']],True),
        ('counter_b','复盘员 B','picker',[source['id']],True),
    ):
        accounts[label] = provision(database,'',name,role=role,tenant_id=admin['tenant_id'],warehouse_ids=warehouses,count_only=count_only)
    fd = os.open(credentials,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump({'format':FORMAT,'tenant_id':admin['tenant_id'],'accounts':accounts},stream,ensure_ascii=False,indent=2)
    return database, credentials


def main():
    parser = argparse.ArgumentParser(description='Isolated local WMS trial; binds only to 127.0.0.1')
    parser.add_argument('--directory',default='var/local-trial')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--prepare-only',action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be 1..65535')
    try:
        database, credentials = prepare(args.directory)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1,f'Trial setup stopped: {error}\n')
    print('Local trial uses synthetic data only; do not enter real customer data.')
    print(f'Database: {database}')
    print(f'Protected accounts: {credentials} (open locally; copy the selected account token into the login form).')
    print(f'Browser: http://127.0.0.1:{args.port} ; stop with Ctrl+C. Data is retained between starts.')
    if not args.prepare_only:
        import uvicorn
        from app.main import create_app
        uvicorn.run(create_app(database),host='127.0.0.1',port=args.port,workers=1,access_log=False)


if __name__=='__main__':
    main()
