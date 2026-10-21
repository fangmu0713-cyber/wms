import hashlib
import json
import logging
import os
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Depends, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from . import db as database, models, service, waves, movements, stock_counts, transfers
from .auth import digest

LOG = logging.getLogger('wms')
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    LOG.addHandler(logging.StreamHandler())
STATIC = Path(__file__).parent / 'static'


def authenticate(db, request):
    header = request.headers.get('authorization','')
    if not header.startswith('Bearer ') or len(header)>300:
        service.fail('valid_bearer_token_required',401)
    row = db.execute('SELECT * FROM users WHERE token_hash=? AND active=1',(digest(header[7:]),)).fetchone()
    if not row:
        service.fail('invalid_or_revoked_token',401)
    if row['expires_at'] and datetime.fromisoformat(row['expires_at'])<=datetime.now(timezone.utc):
        service.fail('token_expired',401)
    actor = dict(row)
    if 'count_only' not in actor:
        service.fail('database_migrations_required',503)
    stock_counts.restrict(actor,request.method,request.url.path)
    return actor


def create_app(db_path=None):
    path = str(db_path or database.default_path())
    app = FastAPI(title='Overseas WMS / OMS',version='0.5.0',docs_url=None,redoc_url=None,description='Internal WMS API; no third-party ERP is enabled. Mutations require Idempotency-Key. Quantities are units, money BRL cents.')
    app.state.db_path = path
    failures = defaultdict(deque)
    security = HTTPBearer(auto_error=False)

    def require_idempotency(idempotency_key: str = Header(min_length=8,max_length=128)):
        return idempotency_key

    @app.middleware('http')
    async def safeguards(request, call_next):
        # Single node limiter; production gateway must supply global throttling.
        ip = request.client.host if request.client else 'unknown'
        moment = time.monotonic()
        attempts = failures[ip]
        while attempts and attempts[0]<moment-60:
            attempts.popleft()
        if len(attempts)>=30 and request.url.path.startswith('/api/'):
            response = JSONResponse({'detail':'authentication_rate_limit'},status_code=429,headers={'Retry-After':'60'})
        else:
            if request.method in ('POST','PUT','PATCH'):
                chunks, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size>262144:
                        return JSONResponse({'detail':'request_too_large'},status_code=413)
                    chunks.append(chunk)
                request._body = b''.join(chunks)
            started = time.monotonic()
            response = await call_next(request)
            if response.status_code==401:
                attempts.append(moment)
            # No URLs, headers, bodies, barcode, customer details or credentials.
            if request.url.path.startswith('/api/'):
                LOG.info('api_request status=%s duration_ms=%.1f',response.status_code,(time.monotonic()-started)*1000)
        response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse({'detail':'duplicate_reference_or_constraint_violation'},status_code=409)

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        LOG.error('database_operation_failed')
        return JSONResponse({'detail':'database_unavailable_or_busy_retry_same_key'},status_code=503)

    def execute(request, data, operation):
        key = request.headers.get('idempotency-key','')
        if not 8<=len(key)<=128 or not key.isascii() or not key.isprintable():
            service.fail('idempotency_key_required_8_to_128_ascii_characters',422)
        encoded = json.dumps({'path':request.url.path,'body':data},sort_keys=True,separators=(',',':'))
        request_hash = hashlib.sha256(encoded.encode()).hexdigest()
        with database.transaction(path) as db:
            actor = authenticate(db,request)
            previous = db.execute('SELECT * FROM idempotency WHERE tenant_id=? AND actor_id=? AND key=?',(actor['tenant_id'],actor['id'],key)).fetchone()
            if previous:
                if previous['request_hash'] != request_hash:
                    service.fail('idempotency_key_reused_with_different_request')
                result = json.loads(previous['response'])
                if request.url.path == '/api/transfers' or request.url.path.startswith('/api/transfers/'):
                    transfers.authorize_replay(db,actor,request.url.path,result)
                return result
            result = operation(db,actor,key,data)
            db.execute('INSERT INTO idempotency VALUES (?,?,?,?,?,?)',
                (actor['tenant_id'],actor['id'],key,request_hash,json.dumps(result),service.now()))
            service.insert(db,'audit',{'tenant_id':actor['tenant_id'],'actor_id':actor['id'],'action':request.url.path.split('/')[2] + ':' + request.url.path.split('/')[-1],
                'resource_id':result['id'],'idempotency_key':key,'created_at':service.now()})
            return result

    def add_post(route, model, operation):
        def endpoint(request: Request, payload: model):
            return execute(request,payload.model_dump(),operation)
        app.add_api_route(route,endpoint,methods=['POST'],name=route.replace('/','_'),dependencies=[Depends(security),Depends(require_idempotency)])

    for table, model in (('owners',models.Named),('warehouses',models.Warehouse),('locations',models.Location),('skus',models.SKU),('stores',models.Store)):
        def master_operation(table):
            return lambda db,actor,key,data: service.create_master(db,actor,table,data)
        add_post('/api/'+table,model,master_operation(table))

    add_post('/api/receipts',models.Receipt,lambda db,a,k,d:service.create_receipt(db,a,d))
    add_post('/api/orders',models.Order,lambda db,a,k,d:service.create_order(db,a,d))
    add_post('/api/returns',models.Return,lambda db,a,k,d:service.create_return(db,a,d))
    add_post('/api/fees',models.Fee,lambda db,a,k,d:service.create_fee(db,a,d))
    add_post('/api/waves',models.Wave,lambda db,a,k,d:waves.create(db,a,d))
    add_post('/api/movements',models.Movement,lambda db,a,k,d:movements.create(db,a,k,d))
    add_post('/api/stock_counts',models.StockCount,lambda db,a,k,d:stock_counts.create(db,a,d))

    add_post('/api/transfers',models.Transfer,lambda db,a,k,d:transfers.create(db,a,k,d))

    def add_transfer_action(action, model):
        def endpoint(object_id: str, request: Request, payload: model):
            return execute(request,payload.model_dump(),lambda db,a,k,d:transfers.action(db,a,k,object_id,action,d))
        app.add_api_route('/api/transfers/{object_id}/'+action,endpoint,methods=['POST'],name='transfers_'+action,dependencies=[Depends(security),Depends(require_idempotency)])

    for action, model in (('dispatch',models.TransferDispatch),('receive',models.TransferReceive),('cancel',models.CountReview),('close_loss',models.TransferLoss)):
        add_transfer_action(action,model)

    def add_count_action(table, action, model):
        def endpoint(object_id: str, request: Request, payload: model):
            def operation(db,a,k,d):
                if table=='stock_counts':
                    return stock_counts.review(db,a,k,object_id,action,d)
                if table=='count_lines':
                    return stock_counts.recount(db,a,object_id,d)
                return stock_counts.submit(db,a,k,object_id,d)
            return execute(request,payload.model_dump(),operation)
        app.add_api_route('/api/'+table+'/{object_id}/'+action,endpoint,methods=['POST'],name=table+'_'+action,dependencies=[Depends(security),Depends(require_idempotency)])

    add_count_action('count_attempts','submit',models.CountScan)
    add_count_action('count_lines','recount',models.Recount)
    for action in ('approve','cancel'):
        add_count_action('stock_counts',action,models.CountReview)

    def add_movement_action(action, model):
        def endpoint(object_id: str, request: Request, payload: model):
            return execute(request,payload.model_dump(),lambda db,a,k,d:movements.action(db,a,k,object_id,action,d))
        app.add_api_route('/api/movements/{object_id}/'+action,endpoint,methods=['POST'],name='movements_'+action,dependencies=[Depends(security),Depends(require_idempotency)])

    for action, model in (('claim',models.Empty),('release',models.Empty),('cancel',models.Empty),('dispatch',models.Pick),('receive',models.Pick)):
        add_movement_action(action,model)

    def add_wave_action(table, action, model):
        def endpoint(object_id: str, request: Request, payload: model):
            operation = (lambda db,a,k,d:waves.cancel(db,a,object_id)) if table=='waves' else (lambda db,a,k,d:waves.task_action(db,a,k,object_id,action,d))
            return execute(request,payload.model_dump(),operation)
        app.add_api_route('/api/'+table+'/{object_id}/'+action,endpoint,methods=['POST'],name=table+'_'+action,dependencies=[Depends(security),Depends(require_idempotency)])

    add_wave_action('waves','cancel',models.Empty)
    for action, model in (('claim',models.Empty),('release',models.Empty),('scan',models.Pick)):
        add_wave_action('pick_tasks',action,model)

    def add_action(table, action, model):
        def endpoint(object_id: str, request: Request, payload: model):
            if table=='orders':
                operation = lambda db,a,k,d:service.order_action(db,a,k,object_id,action,d)
            else:
                operation = lambda db,a,k,d:service.receipt_action(db,a,k,object_id,action,d,table)
            return execute(request,payload.model_dump(),operation)
        app.add_api_route('/api/'+table+'/{object_id}/'+action,endpoint,methods=['POST'],name=table+'_'+action,dependencies=[Depends(security),Depends(require_idempotency)])

    for table in ('receipts','returns'):
        for action,model in (('qc',models.QC),('putaway',models.Putaway)):
            add_action(table,action,model)
    add_action('returns','receive',models.Empty)
    for action,model in (('reserve',models.Empty),('pick',models.Pick),('verify',models.Verify),('pack',models.Pack),('ship',models.Ship),('cancel',models.Empty)):
        add_action('orders',action,model)

    @app.get('/api/me',dependencies=[Depends(security)])
    def me(request: Request):
        with database.transaction(path) as db:
            actor = authenticate(db,request)
            service.insert(db,'audit',{'tenant_id':actor['tenant_id'],'actor_id':actor['id'],'action':'AUTHENTICATED_SESSION','resource_id':actor['id'],'idempotency_key':'','created_at':service.now()})
            return {k:actor[k] for k in ('id','tenant_id','role','owner_id','name','count_only')}

    @app.get('/api/snapshot',dependencies=[Depends(security)])
    def snapshot(request: Request):
        with database.connect(path) as db:
            db.execute('BEGIN')  # Consistent read snapshot across all balance/ledger queries.
            actor = authenticate(db,request)
            result = service.snapshot(db,actor)
            from .integrations import get_registry
            result['integrations'] = get_registry()
            return result

    def add_get(table):
        def endpoint(object_id: str, request: Request):
            with database.connect(path) as db:
                actor = authenticate(db,request)
                if table=='fees':
                    service.permit(actor,'finance','owner','owner_readonly')
                if table in ('waves','pick_tasks'):
                    service.permit(actor,'staff','picker')
                if table=='transfers':
                    service.permit(actor,*transfers.READ_ROLES)
                if table=='movements':
                    service.permit(actor,*movements.EXECUTION_ROLES)
                if table=='count_attempts':
                    return stock_counts.get_attempt(db,actor,object_id)
                if table in ('stock_counts','count_lines'):
                    service.permit(actor,'staff')
                return service.get(db,actor,table,object_id)
        app.add_api_route('/api/'+table+'/{object_id}',endpoint,methods=['GET'],name=table+'_get',dependencies=[Depends(security)])
    for table in ('owners','warehouses','locations','skus','stores','receipts','orders','inventory','ledger','returns','fees','waves','pick_tasks','movements','transfers','stock_counts','count_lines','count_attempts'):
        add_get(table)

    @app.get('/health')
    def health():
        try:
            with database.connect(path) as db:
                required = {script.name for script in (Path(__file__).parent/'migrations').glob('*.sql')}
                applied = {row[0] for row in db.execute('SELECT version FROM schema_migrations')}
                ready = required <= applied
                db.execute('SELECT 1 FROM inventory LIMIT 1')
            return JSONResponse({'status':'ok' if ready else 'not_ready'},status_code=200 if ready else 503)
        except sqlite3.Error:
            return JSONResponse({'status':'not_ready'},status_code=503)

    @app.get('/',include_in_schema=False)
    def index():
        return FileResponse(STATIC/'index.html',headers={'Cache-Control':'no-store'})

    app.mount('/static',StaticFiles(directory=STATIC),name='static')
    return app


app = create_app()
