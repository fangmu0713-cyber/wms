"""Blind observations with locked cutoffs; approval posts a delta, never a balance."""
from datetime import datetime, timezone
from . import service as s


BLIND_FIELDS = ('id','owner_id','warehouse_id','sku_id','location_id','session_id','line_id',
                'counter_id','round','status','counted_qty','created_at','submitted_at')


def restrict(actor, method, path):
    if not actor['count_only']:
        return
    parts = path.strip('/').split('/')
    allowed = method == 'GET' and path in ('/api/me','/api/snapshot')
    allowed |= len(parts) == 3 and parts[:2] == ['api','count_attempts'] and method == 'GET'
    allowed |= len(parts) == 4 and parts[:2] == ['api','count_attempts'] and parts[3] == 'submit' and method == 'POST'
    if not allowed:
        s.fail('count_only_credential_scope',403)


def blind(row):
    return {k:row[k] for k in BLIND_FIELDS}


def get_attempt(db, actor, object_id):
    row = s.get(db,actor,'count_attempts',object_id)
    if actor['count_only']:
        if row['counter_id'] != actor['id']:
            s.fail('resource_not_found_or_outside_scope',404)
        return blind(row)
    s.permit(actor,'staff')
    return row


def eligible(db, actor, counter_id, warehouse_id):
    row = db.execute('''SELECT u.* FROM users u JOIN user_warehouses uw ON uw.user_id=u.id
        WHERE u.id=? AND u.tenant_id=? AND u.active=1 AND u.count_only=1 AND uw.warehouse_id=?''',
        (counter_id,actor['tenant_id'],warehouse_id)).fetchone()
    if not row or (row['expires_at'] and datetime.fromisoformat(row['expires_at'])<=datetime.now(timezone.utc)):
        s.fail('authorized_count_only_operator_required',422)


def start_attempt(db, actor, line, counter_id):
    eligible(db,actor,counter_id,line['warehouse_id'])
    inventory = s.get(db,actor,'inventory',line['inventory_id'])
    if (inventory['reserved'] or inventory['picked'] or inventory['move_reserved']
            or inventory['count_reserved'] != line['hold_qty']):
        s.fail('count_requires_unencumbered_inventory')
    cutoff = db.execute('SELECT COALESCE(MAX(rowid),0) FROM ledger').fetchone()[0]
    round_no = db.execute('SELECT COALESCE(MAX(round),0)+1 FROM count_attempts WHERE line_id=?',(line['id'],)).fetchone()[0]
    attempt = s.insert(db,'count_attempts',{
        **{k:line[k] for k in ('tenant_id','owner_id','warehouse_id','sku_id','location_id','session_id')},
        'line_id':line['id'],'counter_id':counter_id,'round':round_no,'baseline_on_hand':inventory['on_hand'],
        'cutoff_seq':cutoff,'status':'ACTIVE','counted_qty':None,'delta':None,'created_at':s.now(),'submitted_at':None})
    db.execute('INSERT INTO count_locks VALUES (?,?,?,?)',(inventory['id'],line['session_id'],line['id'],attempt['id']))
    db.execute("UPDATE count_lines SET status='COUNTING',accepted_delta=NULL WHERE id=?",(line['id'],))
    return attempt


def create(db, actor, data):
    s.permit(actor,'staff')
    s.get(db,actor,'owners',data['owner_id'])
    s.get(db,actor,'warehouses',data['warehouse_id'])
    s.same_owner(s.get(db,actor,'skus',data['sku_id']),data['owner_id'])
    eligible(db,actor,data['counter_id'],data['warehouse_id'])
    if len(set(data['location_ids'])) != len(data['location_ids']):
        s.fail('duplicate_count_locations',422)
    session = s.insert(db,'stock_counts',{
        'tenant_id':actor['tenant_id'],**{k:data[k] for k in ('owner_id','warehouse_id','sku_id','reference')},
        'status':'OPEN','created_by':actor['id'],'created_at':s.now()})
    for location_id in data['location_ids']:
        location = s.get(db,actor,'locations',location_id)
        if location['warehouse_id'] != data['warehouse_id']:
            s.fail('location_warehouse_mismatch',422)
        inventory = db.execute('''SELECT * FROM inventory WHERE tenant_id=? AND owner_id=? AND warehouse_id=? AND sku_id=? AND location_id=?''',
            (actor['tenant_id'],data['owner_id'],data['warehouse_id'],data['sku_id'],location_id)).fetchone()
        if not inventory:
            inventory = s.insert(db,'inventory',{'tenant_id':actor['tenant_id'],
                **{k:data[k] for k in ('owner_id','warehouse_id','sku_id')},'location_id':location_id})
        if dict(inventory).get('count_reserved',0):
            s.fail('inventory_already_has_count_hold')
        line = s.insert(db,'count_lines',{
            **{k:session[k] for k in ('tenant_id','owner_id','warehouse_id','sku_id')},
            'location_id':location_id,'inventory_id':inventory['id'],'session_id':session['id'],
            'status':'COUNTING','hold_qty':0,'accepted_delta':None,'active':1})
        start_attempt(db,actor,line,data['counter_id'])
    return session


def refresh(db, session_id):
    incomplete = db.execute("SELECT 1 FROM count_lines WHERE session_id=? AND status<>'CONFIRMED'",(session_id,)).fetchone()
    db.execute('UPDATE stock_counts SET status=? WHERE id=?',('OPEN' if incomplete else 'REVIEW',session_id))


def submit(db, actor, key, attempt_id, data):
    if not actor['count_only']:
        s.fail('count_only_credential_required',403)
    attempt = s.get(db,actor,'count_attempts',attempt_id)
    if attempt['counter_id'] != actor['id']:
        s.fail('resource_not_found_or_outside_scope',404)
    if attempt['status'] != 'ACTIVE':
        s.fail('count_attempt_already_closed')
    line = s.get(db,actor,'count_lines',attempt['line_id'])
    session = s.get(db,actor,'stock_counts',attempt['session_id'])
    if session['status'] != 'OPEN':
        s.fail('count_session_not_open')
    sku = s.get(db,actor,'skus',attempt['sku_id'])
    if data['barcode'] != sku['barcode'] or data['location_id'] != attempt['location_id']:
        s.fail('count_wrong_barcode_or_location')
    lock = db.execute('SELECT * FROM count_locks WHERE inventory_id=?',(line['inventory_id'],)).fetchone()
    inventory = s.get(db,actor,'inventory',line['inventory_id'])
    changed = db.execute('SELECT 1 FROM ledger WHERE inventory_id=? AND rowid>?',(inventory['id'],attempt['cutoff_seq'])).fetchone()
    if (not lock or lock['attempt_id'] != attempt_id or changed or inventory['on_hand'] != attempt['baseline_on_hand']
            or inventory['reserved'] or inventory['picked'] or inventory['move_reserved'] or inventory['count_reserved'] != line['hold_qty']):
        s.fail('count_cutoff_invalid')
    delta = data['qty']-attempt['baseline_on_hand']
    previous = db.execute("SELECT * FROM count_attempts WHERE line_id=? AND status='SUBMITTED' ORDER BY round DESC LIMIT 1",(line['id'],)).fetchone()
    confirmed = (previous is None and delta==0) or (previous is not None and previous['delta']==delta and previous['counter_id']!=actor['id'])
    hold = max(line['hold_qty'],max(0,-delta))
    if hold>line['hold_qty']:
        s.stock(db,actor,key,inventory,line['id'],'COUNT_HOLD',count_reserved=hold-line['hold_qty'],count_line_id=line['id'])
    db.execute("UPDATE count_attempts SET status='SUBMITTED',counted_qty=?,delta=?,submitted_at=? WHERE id=?",(data['qty'],delta,s.now(),attempt_id))
    db.execute('UPDATE count_lines SET status=?,hold_qty=?,accepted_delta=? WHERE id=?',
        ('CONFIRMED' if confirmed else 'RECOUNT_REQUIRED',hold,delta if confirmed else None,line['id']))
    db.execute('DELETE FROM count_locks WHERE attempt_id=?',(attempt_id,))
    refresh(db,session['id'])
    return blind(s.get(db,actor,'count_attempts',attempt_id))


def recount(db, actor, line_id, data):
    s.permit(actor,'staff')
    line = s.get(db,actor,'count_lines',line_id)
    session = s.get(db,actor,'stock_counts',line['session_id'])
    if session['status'] != 'OPEN' or line['status'] != 'RECOUNT_REQUIRED':
        s.fail('count_line_not_awaiting_recount')
    previous = db.execute("SELECT * FROM count_attempts WHERE line_id=? AND status='SUBMITTED' ORDER BY round DESC LIMIT 1",(line_id,)).fetchone()
    if previous['counter_id'] == data['counter_id']:
        s.fail('recount_requires_different_operator')
    return start_attempt(db,actor,line,data['counter_id'])


def review(db, actor, key, session_id, action, data):
    s.permit(actor,*(() if action=='approve' else ('staff',)))
    session = s.get(db,actor,'stock_counts',session_id)
    if session['status'] in ('APPROVED','CANCELLED'):
        s.fail('count_session_already_terminal')
    if action=='approve' and session['status']!='REVIEW':
        s.fail('count_requires_confirmed_lines')
    lines = db.execute('SELECT * FROM count_lines WHERE session_id=? ORDER BY id',(session_id,)).fetchall()
    for line in lines:
        inventory = s.get(db,actor,'inventory',line['inventory_id'])
        if inventory['count_reserved'] != line['hold_qty']:
            s.fail('count_hold_mismatch')
        if action=='approve' or line['hold_qty']:
            s.stock(db,actor,key,inventory,line['id'],'COUNT_ADJUST' if action=='approve' else 'COUNT_CANCEL_RELEASE',
                on_hand=line['accepted_delta'] if action=='approve' else 0,count_reserved=-line['hold_qty'],
                count_line_id=line['id'] if action=='cancel' else None)
    db.execute('DELETE FROM count_locks WHERE session_id=?',(session_id,))
    db.execute("UPDATE count_attempts SET status='CANCELLED' WHERE session_id=? AND status='ACTIVE'",(session_id,))
    db.execute('UPDATE count_lines SET status=?,hold_qty=0,active=0 WHERE session_id=?',('APPROVED' if action=='approve' else 'CANCELLED',session_id))
    db.execute('UPDATE stock_counts SET status=?,reviewed_by=?,reviewed_at=?,reason=? WHERE id=?',
        ('APPROVED' if action=='approve' else 'CANCELLED',actor['id'],s.now(),data['reason'],session_id))
    return s.get(db,actor,'stock_counts',session_id)


def snapshot(db, actor):
    sessions = [dict(r) for r in db.execute('SELECT * FROM stock_counts WHERE tenant_id=? ORDER BY created_at,id',(actor['tenant_id'],)) if s.visible(db,actor,r)]
    lines = [dict(r) for r in db.execute('SELECT * FROM count_lines WHERE tenant_id=?',(actor['tenant_id'],)) if s.visible(db,actor,r)]
    attempts = [dict(r) for r in db.execute('SELECT * FROM count_attempts WHERE tenant_id=? ORDER BY line_id,round',(actor['tenant_id'],)) if s.visible(db,actor,r)]
    result = {'stock_counts':[],'count_lines':[],'count_attempts':[],'count_operators':[]}
    if actor['count_only']:
        result['count_attempts'] = [blind(r) for r in attempts if r['counter_id']==actor['id']]
    elif actor['role'] in ('admin','staff'):
        result.update(stock_counts=sessions,count_lines=lines,count_attempts=attempts)
        operators = db.execute('''SELECT u.id,u.name,uw.warehouse_id FROM users u JOIN user_warehouses uw ON uw.user_id=u.id
            WHERE u.tenant_id=? AND u.active=1 AND u.count_only=1 AND (u.expires_at IS NULL OR u.expires_at>?) ORDER BY u.name,u.id''',(actor['tenant_id'],s.now())).fetchall()
        result['count_operators'] = [dict(r) for r in operators if s.allowed_warehouse(db,actor,r['warehouse_id'])]
    return result,lines


def blind_snapshot(db, actor):
    counts,_ = snapshot(db,actor)
    attempts = counts['count_attempts']
    ids = {key:{a[key] for a in attempts} for key in ('owner_id','warehouse_id','sku_id','location_id')}
    result = {name:[] for name in ('stores','receipts','orders','order_lines','allocations','inventory','ledger','returns','fees','waves','pick_tasks','wave_orders','movements','transfers','transfer_events','stock_summary')}
    for table,key in (('owners','owner_id'),('warehouses','warehouse_id'),('skus','sku_id'),('locations','location_id')):
        result[table] = [dict(r) for r in db.execute(f'SELECT * FROM {table} WHERE tenant_id=?',(actor['tenant_id'],)) if r['id'] in ids[key]]
    result.update(counts)
    result['reconciliation'] = {'ok':None,'issues':[]}
    return result
