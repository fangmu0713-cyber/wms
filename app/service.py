"""Warehouse domain operations; caller owns one immediate write transaction."""
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException


def now():
    return datetime.now(timezone.utc).isoformat()


def fail(message, status=409):
    raise HTTPException(status, message)


def insert(db, table, data):
    record = {'id':str(uuid4()), **data}
    keys = ','.join(record)
    db.execute(f"INSERT INTO {table} ({keys}) VALUES ({','.join('?' for _ in record)})", tuple(record.values()))
    return record


def allowed_warehouse(db, actor, warehouse_id):
    return actor['role'] == 'admin' or bool(db.execute('SELECT 1 FROM user_warehouses WHERE user_id=? AND warehouse_id=?', (actor['id'],warehouse_id)).fetchone())


def visible(db, actor, row):
    if row['tenant_id'] != actor['tenant_id']:
        return False
    if actor['owner_id'] and 'owner_id' in row.keys() and row['owner_id'] != actor['owner_id']:
        return False
    if 'warehouse_id' in row.keys() and not allowed_warehouse(db,actor,row['warehouse_id']):
        return False
    if 'source_warehouse_id' in row.keys() and not any(allowed_warehouse(db,actor,row[k]) for k in ('source_warehouse_id','destination_warehouse_id')):
        return False
    return True


def get(db, actor, table, object_id):
    # table is internal constant, never user SQL.
    row = db.execute(f'SELECT * FROM {table} WHERE id=? AND tenant_id=?', (object_id,actor['tenant_id'])).fetchone()
    if not row or not visible(db,actor,row):
        fail('resource_not_found_or_outside_scope',404)
    if table == 'owners' and actor['owner_id'] and row['id'] != actor['owner_id']:
        fail('resource_not_found_or_outside_scope',404)
    if table == 'warehouses' and not allowed_warehouse(db,actor,row['id']):
        fail('resource_not_found_or_outside_scope',404)
    return dict(row)


def permit(actor, *roles):
    if actor['role'] != 'admin' and actor['role'] not in roles:
        fail('role_not_permitted',403)


def same_owner(obj, owner_id):
    if obj['owner_id'] != owner_id:
        fail('resource_owner_mismatch',422)


def stock(db, actor, key, inventory, source, event, on_hand=0, reserved=0, picked=0, move_reserved=0, in_transit=0, count_reserved=0, count_line_id=None, transfer_transit=0, transfer_lost=0):
    lock = db.execute('SELECT line_id FROM count_locks WHERE inventory_id=?',(inventory['id'],)).fetchone()
    if lock and lock['line_id'] != count_line_id:
        fail('inventory_locked_for_count')
    changed = db.execute('''UPDATE inventory SET on_hand=on_hand+?,reserved=reserved+?,picked=picked+?,move_reserved=move_reserved+?,count_reserved=count_reserved+?
        WHERE id=? AND tenant_id=? AND on_hand+?>=0 AND reserved+?>=0
        AND move_reserved+?>=0 AND count_reserved+?>=0
        AND reserved+?+move_reserved+?+count_reserved+?<=on_hand+?
        AND picked+?>=0 AND picked+?<=reserved+?''',
        (on_hand,reserved,picked,move_reserved,count_reserved,inventory['id'],actor['tenant_id'],on_hand,reserved,
         move_reserved,count_reserved,reserved,move_reserved,count_reserved,on_hand,picked,picked,reserved)).rowcount
    if changed != 1:
        fail('insufficient_or_inconsistent_stock')
    insert(db,'ledger',{'tenant_id':actor['tenant_id'],
        **{k:inventory[k] for k in ('owner_id','warehouse_id','sku_id','location_id')},
        'inventory_id':inventory['id'],'event_type':event,'source_id':source,
        'on_hand_delta':on_hand,'reserved_delta':reserved,'picked_delta':picked,
        'move_reserved_delta':move_reserved,'in_transit_delta':in_transit,
        'count_reserved_delta':count_reserved,
        'transfer_transit_delta':transfer_transit,'transfer_lost_delta':transfer_lost,
        'actor_id':actor['id'],'idempotency_key':key,'created_at':now()})


def put_stock(db, actor, key, obj, location_id, event):
    location = get(db,actor,'locations',location_id)
    if location['warehouse_id'] != obj['warehouse_id']:
        fail('location_warehouse_mismatch',422)
    inventory = db.execute('SELECT * FROM inventory WHERE owner_id=? AND warehouse_id=? AND sku_id=? AND location_id=?',
                         (obj['owner_id'],obj['warehouse_id'],obj['sku_id'],location_id)).fetchone()
    if not inventory:
        inventory = insert(db,'inventory', {k:obj[k] for k in ('tenant_id','owner_id','warehouse_id','sku_id')} | {'location_id':location_id})
    if obj['accepted_qty']:
        stock(db,actor,key,inventory,obj['id'],event,on_hand=obj['accepted_qty'])


def create_master(db, actor, table, data):
    if table in ('owners','warehouses'):
        permit(actor)
    else:
        permit(actor,'staff','owner')
    if 'owner_id' in data:
        get(db,actor,'owners',data['owner_id'])
    if 'warehouse_id' in data:
        get(db,actor,'warehouses',data['warehouse_id'])
    if table == 'warehouses':
        try:
            ZoneInfo(data['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            fail('invalid_timezone',422)
    return insert(db,table,{'tenant_id':actor['tenant_id'],**data})


def create_receipt(db, actor, data):
    permit(actor,'staff','receiver')
    get(db,actor,'owners',data['owner_id'])
    get(db,actor,'warehouses',data['warehouse_id'])
    same_owner(get(db,actor,'skus',data['sku_id']),data['owner_id'])
    return insert(db,'receipts',{'tenant_id':actor['tenant_id'],**data,'status':'RECEIVED','created_at':now()})


def receipt_action(db, actor, key, object_id, action, data, table='receipts'):
    permit(actor,'staff','receiver')
    obj = get(db,actor,table,object_id)
    if action == 'receive' and table == 'returns':
        if obj['status'] != 'EXPECTED':
            fail('return_already_received_or_processed')
        db.execute('UPDATE returns SET status=? WHERE id=?',('RECEIVED',object_id))
    elif action == 'qc':
        if obj['status'] != 'RECEIVED':
            fail('qc_requires_actual_receipt')
        if data['accepted_qty'] + data['rejected_qty'] != obj['qty']:
            fail('qc_quantities_must_equal_received',422)
        db.execute(f'UPDATE {table} SET accepted_qty=?,rejected_qty=?,status=? WHERE id=?',
                   (data['accepted_qty'],data['rejected_qty'],'QC_DONE',object_id))
    elif action == 'putaway':
        if obj['status'] != 'QC_DONE':
            fail('putaway_requires_qc_and_only_once')
        put_stock(db,actor,key,obj,data['location_id'],'RETURN_PUTAWAY' if table=='returns' else 'RECEIPT_PUTAWAY')
        db.execute(f'UPDATE {table} SET status=?,location_id=? WHERE id=?',('PUTAWAY',data['location_id'],object_id))
    else:
        fail('unsupported_action',422)
    return get(db,actor,table,object_id)


def create_order(db, actor, data):
    permit(actor,'staff','owner')
    get(db,actor,'owners',data['owner_id'])
    get(db,actor,'warehouses',data['warehouse_id'])
    same_owner(get(db,actor,'stores',data['store_id']),data['owner_id'])
    if len({line['sku_id'] for line in data['lines']}) != len(data['lines']):
        fail('duplicate_sku_lines',422)
    for line in data['lines']:
        same_owner(get(db,actor,'skus',line['sku_id']),data['owner_id'])
    order = insert(db,'orders',{'tenant_id':actor['tenant_id'],**{k:v for k,v in data.items() if k!='lines'},'status':'CREATED','created_at':now()})
    for line in data['lines']:
        insert(db,'order_lines',{'tenant_id':actor['tenant_id'],'order_id':order['id'],**line})
    return order


def lines(db, order_id):
    return [dict(r) for r in db.execute('SELECT * FROM order_lines WHERE order_id=? ORDER BY id',(order_id,))]


def order_action(db, actor, key, object_id, action, data, task_id=None):
    roles = {'reserve':('staff','owner'),'cancel':('staff','owner'),'pick':('staff','picker'),
             'verify':('staff','packer'),'pack':('staff','packer'),'ship':('staff','packer')}
    permit(actor,*roles[action])
    order = get(db,actor,'orders',object_id)
    order_lines = lines(db,object_id)
    status = order['status']
    next_status = status
    if action == 'reserve':
        if status != 'CREATED':
            fail('reserve_requires_created_order')
        for line in order_lines:
            remaining = line['qty']
            rows = db.execute('''SELECT * FROM inventory WHERE tenant_id=? AND owner_id=? AND warehouse_id=? AND sku_id=? AND on_hand>reserved+move_reserved+count_reserved
                AND NOT EXISTS (SELECT 1 FROM count_locks WHERE inventory_id=inventory.id) ORDER BY location_id''',
                (actor['tenant_id'],order['owner_id'],order['warehouse_id'],line['sku_id'])).fetchall()
            for inv in rows:
                qty = min(remaining,inv['on_hand']-inv['reserved']-inv['move_reserved']-inv['count_reserved'])
                if not qty:
                    continue
                stock(db,actor,key,inv,object_id,'RESERVE',reserved=qty)
                insert(db,'allocations',{'tenant_id':actor['tenant_id'],'order_id':object_id,'line_id':line['id'],'inventory_id':inv['id'],'qty':qty,'status':'ACTIVE'})
                remaining -= qty
                if not remaining:
                    break
            if remaining:
                fail('insufficient_available_stock')
        next_status = 'RESERVED'
    elif action == 'pick':
        if status not in ('RESERVED','PICKING'):
            fail('pick_requires_reserved_order')
        membership = db.execute('SELECT 1 FROM wave_orders WHERE order_id=? AND active=1', (object_id,)).fetchone()
        if membership and task_id is None:
            fail('pick_via_wave_task_required')
        allocations = db.execute('''SELECT a.*,i.owner_id,i.warehouse_id,i.sku_id,i.location_id FROM allocations a JOIN inventory i ON i.id=a.inventory_id JOIN skus s ON s.id=i.sku_id
            WHERE a.order_id=? AND a.status='ACTIVE' AND s.barcode=? AND i.location_id=?''', (object_id,data['barcode'],data['location_id'])).fetchall()
        if len(allocations)!=1 or data['qty'] > allocations[0]['qty'] - allocations[0]['picked_qty']:
            fail('wrong_barcode_location_or_excess_pick')
        allocation = dict(allocations[0])
        if task_id and not db.execute('SELECT 1 FROM pick_tasks WHERE id=? AND allocation_id=?', (task_id,allocation['id'])).fetchone():
            fail('task_allocation_mismatch')
        inv = get(db,actor,'inventory',allocation['inventory_id'])
        stock(db,actor,key,inv,object_id,'PICK',picked=data['qty'])
        db.execute('UPDATE allocations SET picked_qty=picked_qty+? WHERE id=?',(data['qty'],allocation['id']))
        incomplete = db.execute('SELECT 1 FROM allocations WHERE order_id=? AND picked_qty<qty',(object_id,)).fetchone()
        next_status = 'PICKING' if incomplete else 'PICKED'
    elif action == 'verify':
        if status != 'PICKED':
            fail('verify_requires_fully_picked_order')
        line = db.execute('SELECT l.* FROM order_lines l JOIN skus s ON s.id=l.sku_id WHERE l.order_id=? AND s.barcode=?',(object_id,data['barcode'])).fetchone()
        if not line or data['qty']>line['qty']-line['verified_qty']:
            fail('wrong_barcode_or_excess_verification')
        db.execute('UPDATE order_lines SET verified_qty=verified_qty+? WHERE id=?',(data['qty'],line['id']))
        next_status = 'PICKED' if db.execute('SELECT 1 FROM order_lines WHERE order_id=? AND verified_qty<qty',(object_id,)).fetchone() else 'VERIFIED'
    elif action == 'pack':
        if status != 'VERIFIED':
            fail('pack_requires_verified_order')
        db.execute('UPDATE orders SET package_reference=? WHERE id=?',(data['package_reference'],object_id))
        next_status = 'PACKED'
    elif action == 'ship':
        if status != 'PACKED':
            fail('ship_requires_packed_order')
        for allocation in db.execute("SELECT * FROM allocations WHERE order_id=? AND status='ACTIVE'",(object_id,)).fetchall():
            inv = get(db,actor,'inventory',allocation['inventory_id'])
            stock(db,actor,key,inv,object_id,'SHIP',on_hand=-allocation['qty'],reserved=-allocation['qty'],picked=-allocation['picked_qty'])
        db.execute("UPDATE allocations SET status='SHIPPED' WHERE order_id=?",(object_id,))
        db.execute('UPDATE orders SET tracking_number=?,carrier=? WHERE id=?',(data['tracking_number'],data['carrier'],object_id))
        next_status = 'SHIPPED'
    elif action == 'cancel':
        if status not in ('CREATED','RESERVED'):
            fail('cancel_requires_unpicked_order_physical_return_required')
        from .waves import cancel_order_tasks
        cancel_order_tasks(db,object_id)
        for allocation in db.execute("SELECT * FROM allocations WHERE order_id=? AND status='ACTIVE'",(object_id,)).fetchall():
            inv = get(db,actor,'inventory',allocation['inventory_id'])
            stock(db,actor,key,inv,object_id,'CANCEL_RELEASE',reserved=-allocation['qty'])
        db.execute("UPDATE allocations SET status='RELEASED' WHERE order_id=?",(object_id,))
        next_status = 'CANCELLED'
    db.execute('UPDATE orders SET status=? WHERE id=?',(next_status,object_id))
    return get(db,actor,'orders',object_id)


def create_return(db, actor, data):
    permit(actor,'staff','receiver','owner')
    order = get(db,actor,'orders',data['order_id'])
    if order['status'] != 'SHIPPED':
        fail('return_requires_shipped_order')
    line = db.execute('SELECT * FROM order_lines WHERE order_id=? AND sku_id=?',(order['id'],data['sku_id'])).fetchone()
    existing = db.execute('SELECT COALESCE(SUM(qty),0) FROM returns WHERE order_id=? AND sku_id=?',(order['id'],data['sku_id'])).fetchone()[0]
    if not line or existing+data['qty']>line['qty']:
        fail('return_exceeds_shipped_quantity')
    return insert(db,'returns',{'tenant_id':actor['tenant_id'],'owner_id':order['owner_id'],'warehouse_id':order['warehouse_id'],**data,'status':'EXPECTED','created_at':now()})


def create_fee(db, actor, data):
    permit(actor,'finance')
    order = get(db,actor,'orders',data['order_id'])
    if order['status'] != 'SHIPPED':
        fail('manual_fee_requires_actual_shipment')
    return insert(db,'fees',{'tenant_id':actor['tenant_id'],'owner_id':order['owner_id'],'warehouse_id':order['warehouse_id'],**data,'currency':'BRL','created_at':now()})


def snapshot(db, actor):
    from . import stock_counts, transfers
    if actor['count_only']:
        return stock_counts.blind_snapshot(db,actor)
    result = {}
    for table in ('owners','warehouses','locations','skus','stores','receipts','orders','inventory','ledger','returns','fees'):
        rows = db.execute(f'SELECT * FROM {table} WHERE tenant_id=? ORDER BY rowid DESC',(actor['tenant_id'],)).fetchall()
        result[table] = [dict(r) for r in rows if visible(db,actor,r)]
    result['owners'] = [r for r in result['owners'] if not actor['owner_id'] or r['id']==actor['owner_id']]
    result['warehouses'] = [r for r in result['warehouses'] if allowed_warehouse(db,actor,r['id'])]
    if actor['role'] not in ('admin','finance','owner','owner_readonly'):
        result['fees'] = []
    order_ids = {r['id'] for r in result['orders']}
    result['order_lines'] = [dict(r) for r in db.execute('SELECT * FROM order_lines WHERE tenant_id=?',(actor['tenant_id'],)) if r['order_id'] in order_ids]
    result['allocations'] = [dict(r) for r in db.execute('SELECT * FROM allocations WHERE tenant_id=?',(actor['tenant_id'],)) if r['order_id'] in order_ids]
    result['waves'], result['pick_tasks'], result['wave_orders'] = [], [], []
    if actor['role'] in ('admin','staff','picker'):
        result['waves'] = [dict(r) for r in db.execute('SELECT * FROM waves WHERE tenant_id=? ORDER BY created_at,id',(actor['tenant_id'],)) if visible(db,actor,r)]
        wave_ids = {r['id'] for r in result['waves']}
        result['pick_tasks'] = [dict(r) for r in db.execute('SELECT * FROM pick_tasks WHERE tenant_id=? ORDER BY wave_id,sequence',(actor['tenant_id'],)) if r['wave_id'] in wave_ids and visible(db,actor,r)]
        result['wave_orders'] = [dict(r) for r in db.execute('SELECT wo.* FROM wave_orders wo JOIN waves w ON w.id=wo.wave_id WHERE w.tenant_id=?',(actor['tenant_id'],)) if r['wave_id'] in wave_ids]
    movements = [dict(r) for r in db.execute('SELECT * FROM movements WHERE tenant_id=? ORDER BY created_at,id',(actor['tenant_id'],)) if visible(db,actor,r)]
    result['movements'] = movements if actor['role'] in ('admin','staff','picker','receiver') else []
    transfer_rows = transfers.rows(db,actor)
    can_read_transfers = actor['role'] in ('admin',*transfers.READ_ROLES)
    result['transfers'] = transfer_rows if can_read_transfers else []
    transfer_ids = {row['id'] for row in result['transfers']}
    result['transfer_events'] = [dict(r) for r in db.execute('SELECT * FROM transfer_events WHERE tenant_id=? ORDER BY created_at,id',(actor['tenant_id'],)) if r['transfer_id'] in transfer_ids]
    counts,count_lines = stock_counts.snapshot(db,actor)
    result.update(counts)
    locked_ids = {r['inventory_id'] for r in db.execute('SELECT c.inventory_id FROM count_locks c JOIN inventory i ON i.id=c.inventory_id WHERE i.tenant_id=?',(actor['tenant_id'],))}
    for inv in result['inventory']:
        inv['count_locked'] = inv['id'] in locked_ids
        inv['available'] = 0 if inv['count_locked'] else inv['on_hand'] - inv['reserved'] - inv['move_reserved'] - inv['count_reserved']
    result['reconciliation'] = reconcile(result,movements,count_lines,transfer_rows)
    result['reconciliation']['issues'].extend(transfers.reconcile(db,transfer_rows))
    result['reconciliation']['ok'] = not result['reconciliation']['issues']
    result['stock_summary'] = quality_summary(result,movements,transfer_rows)
    return result


def quality_summary(snapshot, movements=(), transfers=()):
    """Physical custody includes uninspected and rejected goods, never allocatable."""
    groups = {}
    def group(row):
        key = tuple(row[k] for k in ('owner_id','warehouse_id','sku_id'))
        if key not in groups:
            groups[key] = {k:row[k] for k in ('owner_id','warehouse_id','sku_id')} | {
                'on_hand':0,'reserved':0,'picked':0,'move_reserved':0,'count_reserved':0,'available':0,'in_transit':0,
                'transfer_in_transit':0,'transfer_lost':0,
                'pending_qc':0,'qualified_unstored':0,'rejected':0,'physical_total':0}
        return groups[key]
    for row in snapshot['inventory']:
        summary = group(row)
        for k in ('on_hand','reserved','picked','move_reserved','count_reserved','available'):
            summary[k] += row[k]
    for movement in movements:
        if movement['status']=='IN_TRANSIT':
            group(movement)['in_transit'] += movement['qty']
    warehouses = {row['id'] for row in snapshot['warehouses']}
    for transfer in transfers:
        if transfer['source_warehouse_id'] in warehouses:
            row = {**transfer, 'warehouse_id':transfer['source_warehouse_id']}
            summary = group(row)
            if transfer['status'] in ('DISPATCHED','PART_RECEIVED'):
                summary['transfer_in_transit'] += transfer['qty'] - transfer['received_qty'] - transfer['lost_qty']
            summary['transfer_lost'] += transfer['lost_qty']
    for row in snapshot['receipts'] + snapshot['returns']:
        if row['status']=='EXPECTED':
            continue  # A notice is not physical receipt.
        summary = group(row)
        if row['status']=='RECEIVED':
            summary['pending_qc'] += row['qty']
        else:
            summary['rejected'] += row['rejected_qty']
            if row['status']=='QC_DONE':
                summary['qualified_unstored'] += row['accepted_qty']
    for summary in groups.values():
        summary['physical_total'] = summary['on_hand']+summary['in_transit']+summary['transfer_in_transit']+summary['pending_qc']+summary['qualified_unstored']+summary['rejected']
    return list(groups.values())


def reconcile(snapshot, movements=(), count_lines=(), transfers=()):
    issues = []
    sums = {}
    allocations = {}
    movement_holds, transit = {}, {}
    count_holds = {}
    for line in count_lines:
        if line['active']:
            count_holds[line['inventory_id']] = count_holds.get(line['inventory_id'],0)+line['hold_qty']
    for movement in movements:
        if movement['status'] in ('PLANNED','CLAIMED'):
            movement_holds[movement['source_inventory_id']] = movement_holds.get(movement['source_inventory_id'],0)+movement['qty']
    for transfer in transfers:
        if transfer['status']=='TRANSFER_PLANNED':
            movement_holds[transfer['source_inventory_id']] = movement_holds.get(transfer['source_inventory_id'],0)+transfer['qty']
    for entry in snapshot['ledger']:
        values = sums.setdefault(entry['inventory_id'],[0,0,0,0,0])
        for i,k in enumerate(('on_hand_delta','reserved_delta','picked_delta','move_reserved_delta','count_reserved_delta')):
            values[i] += entry[k]
        transit[entry['source_id']] = transit.get(entry['source_id'],0)+entry['in_transit_delta']
    for entry in snapshot['allocations']:
        if entry['status']=='ACTIVE':
            values = allocations.setdefault(entry['inventory_id'],[0,0])
            values[0] += entry['qty']
            values[1] += entry['picked_qty']
    for inv in snapshot['inventory']:
        if [inv['on_hand'],inv['reserved'],inv['picked'],inv['move_reserved'],inv['count_reserved']] != sums.get(inv['id'],[0,0,0,0,0]):
            issues.append({'inventory_id':inv['id'],'reason':'ledger_balance_mismatch'})
        if [inv['reserved'],inv['picked']] != allocations.get(inv['id'],[0,0]):
            issues.append({'inventory_id':inv['id'],'reason':'allocation_balance_mismatch'})
        if inv['move_reserved'] != movement_holds.get(inv['id'],0):
            issues.append({'inventory_id':inv['id'],'reason':'movement_hold_mismatch'})
        if inv['count_reserved'] != count_holds.get(inv['id'],0):
            issues.append({'inventory_id':inv['id'],'reason':'count_hold_mismatch'})
    for movement in movements:
        expected = movement['qty'] if movement['status']=='IN_TRANSIT' else 0
        if transit.get(movement['id'],0) != expected:
            issues.append({'sku_id':movement['sku_id'],'reason':'movement_transit_mismatch'})
    return {'ok':not issues,'issues':issues}
