"""One owner/SKU per transfer, with independent source and destination operators."""
from . import service as s

READ_ROLES = ('staff', 'picker', 'receiver')
IN_FLIGHT = ('DISPATCHED', 'PART_RECEIVED')


def scope(db, actor, transfer, side):
    s.get(db, actor, 'warehouses', transfer[side + '_warehouse_id'])


def create(db, actor, key, data):
    s.permit(actor, 'staff')
    source = s.get(db, actor, 'inventory', data['source_inventory_id'])
    s.get(db, actor, 'warehouses', data['destination_warehouse_id'])
    if source['warehouse_id'] == data['destination_warehouse_id']:
        s.fail('transfer_requires_different_warehouses', 422)
    if data['qty'] > source['on_hand'] - source['reserved'] - source['move_reserved'] - source['count_reserved']:
        s.fail('insufficient_available_stock_for_transfer')
    transfer = s.insert(db, 'transfers', {
        **{k: source[k] for k in ('tenant_id', 'owner_id', 'sku_id')}, **data,
        'source_warehouse_id': source['warehouse_id'], 'source_location_id': source['location_id'],
        'status': 'TRANSFER_PLANNED', 'created_by': actor['id'], 'created_at': s.now()})
    s.stock(db, actor, key, source, transfer['id'], 'TRANSFER_HOLD', move_reserved=data['qty'])
    return s.get(db, actor, 'transfers', transfer['id'])


def authorize(db, actor, object_id, action):
    roles = {'create': ('staff',), 'dispatch': ('staff', 'picker'), 'receive': ('staff', 'receiver'),
             'cancel': ('staff',), 'close_loss': ()}
    s.permit(actor, *roles[action])
    transfer = s.get(db, actor, 'transfers', object_id)
    scope(db, actor, transfer, 'destination' if action == 'receive' else 'source')
    if action in ('create', 'cancel', 'close_loss'):
        scope(db, actor, transfer, 'destination')
    return transfer


def authorize_replay(db, actor, path, result):
    action = 'create' if path == '/api/transfers' else path.rsplit('/',1)[-1]
    authorize(db, actor, result['id'], action)


def action(db, actor, key, object_id, action, data):
    transfer = authorize(db, actor, object_id, action)
    status, qty = transfer['status'], transfer['qty']
    if status in ('COMPLETED', 'CLOSED_WITH_LOSS', 'CANCELLED'):
        s.fail('transfer_already_terminal')
    event_qty, event_location, reference = qty, transfer['source_location_id'], action
    if action in ('dispatch', 'cancel'):
        if status != 'TRANSFER_PLANNED':
            s.fail('transfer_requires_not_dispatched')
        inventory = s.get(db, actor, 'inventory', transfer['source_inventory_id'])
        if action == 'cancel':
            s.stock(db, actor, key, inventory, object_id, 'TRANSFER_CANCEL', move_reserved=-qty)
            db.execute("UPDATE transfers SET status='CANCELLED' WHERE id=?", (object_id,))
        else:
            check_scan(db, actor, transfer, data, transfer['source_location_id'])
            if data['qty'] != qty:
                s.fail('transfer_dispatch_requires_full_quantity')
            s.stock(db, actor, key, inventory, object_id, 'TRANSFER_DISPATCH',
                    on_hand=-qty, move_reserved=-qty, transfer_transit=qty)
            db.execute("UPDATE transfers SET status='DISPATCHED',carrier=?,tracking_number=?,dispatched_at=? WHERE id=?",
                       (data['carrier'], data['tracking_number'], s.now(), object_id))
    else:
        if status not in IN_FLIGHT:
            s.fail('transfer_requires_in_transit')
        remaining = qty - transfer['received_qty'] - transfer['lost_qty']
        event_qty = data['qty']
        if event_qty > remaining:
            s.fail('transfer_quantity_exceeds_remaining')
        if action == 'close_loss':
            if event_qty != remaining:
                s.fail('transfer_loss_must_settle_remaining')
            inventory = s.get(db, actor, 'inventory', transfer['source_inventory_id'])
            s.stock(db, actor, key, inventory, object_id, 'TRANSFER_LOSS',
                    transfer_transit=-remaining, transfer_lost=remaining)
            db.execute("UPDATE transfers SET lost_qty=?,status='CLOSED_WITH_LOSS',completed_at=? WHERE id=?",
                       (remaining, s.now(), object_id))
        else:
            location = s.get(db, actor, 'locations', data['location_id'])
            if location['warehouse_id'] != transfer['destination_warehouse_id']:
                s.fail('transfer_wrong_destination_location', 422)
            check_scan(db, actor, transfer, data, location['id'])
            reference, event_location = data['receipt_reference'], location['id']
            if db.execute("SELECT 1 FROM transfer_events WHERE transfer_id=? AND kind='RECEIVE' AND reference=?",
                          (object_id, reference)).fetchone():
                s.fail('transfer_receipt_reference_already_used')
            inventory = db.execute('''SELECT * FROM inventory WHERE tenant_id=? AND owner_id=? AND warehouse_id=? AND sku_id=? AND location_id=?''',
                (actor['tenant_id'], transfer['owner_id'], transfer['destination_warehouse_id'], transfer['sku_id'], location['id'])).fetchone()
            if not inventory:
                inventory = s.insert(db, 'inventory', {
                    **{k: transfer[k] for k in ('tenant_id', 'owner_id', 'sku_id')},
                    'warehouse_id': transfer['destination_warehouse_id'], 'location_id': location['id']})
            s.stock(db, actor, key, inventory, object_id, 'TRANSFER_RECEIVE',
                    on_hand=event_qty, transfer_transit=-event_qty)
            received = transfer['received_qty'] + event_qty
            complete = received == qty
            db.execute('UPDATE transfers SET received_qty=?,status=?,completed_at=? WHERE id=?',
                       (received, 'COMPLETED' if complete else 'PART_RECEIVED', s.now() if complete else None, object_id))
    s.insert(db, 'transfer_events', {'tenant_id': actor['tenant_id'], 'transfer_id': object_id,
        'kind': {'dispatch':'DISPATCH', 'receive':'RECEIVE', 'cancel':'CANCEL', 'close_loss':'LOSS'}[action],
        'reference': reference, 'qty': event_qty, 'location_id': event_location,
        'actor_id': actor['id'], 'reason': data.get('reason'), 'created_at': s.now()})
    return s.get(db, actor, 'transfers', object_id)


def check_scan(db, actor, transfer, data, location_id):
    sku = s.get(db, actor, 'skus', transfer['sku_id'])
    if data['barcode'] != sku['barcode'] or data['location_id'] != location_id:
        s.fail('transfer_wrong_barcode_or_location')


def rows(db, actor):
    return [dict(row) for row in db.execute('SELECT * FROM transfers WHERE tenant_id=? ORDER BY created_at,id',
        (actor['tenant_id'],)) if s.visible(db, actor, row)]


def remaining(transfer):
    return transfer['qty'] - transfer['received_qty'] - transfer['lost_qty'] if transfer['status'] in IN_FLIGHT else 0


def reconcile(db, transfers):
    """Read both sides internally even when the caller can view only one warehouse."""
    issues = []
    for transfer in transfers:
        events = {r['kind']: r['q'] for r in db.execute('SELECT kind,SUM(qty) q FROM transfer_events WHERE transfer_id=? GROUP BY kind', (transfer['id'],))}
        sums = db.execute('''SELECT COALESCE(SUM(on_hand_delta),0) hand,
            COALESCE(SUM(transfer_transit_delta),0) transit, COALESCE(SUM(transfer_lost_delta),0) lost,
            COALESCE(SUM(move_reserved_delta),0) held FROM ledger WHERE tenant_id=? AND source_id=?''',
            (transfer['tenant_id'], transfer['id'])).fetchone()
        dispatched = transfer['status'] not in ('TRANSFER_PLANNED', 'CANCELLED')
        expected_dispatch = transfer['qty'] if dispatched else 0
        expected_hold = transfer['qty'] if transfer['status'] == 'TRANSFER_PLANNED' else 0
        if (events.get('DISPATCH',0) != expected_dispatch or events.get('RECEIVE',0) != transfer['received_qty']
                or events.get('LOSS',0) != transfer['lost_qty']
                or events.get('CANCEL',0) != (transfer['qty'] if transfer['status']=='CANCELLED' else 0)
                or sums['hand'] != transfer['received_qty'] - expected_dispatch
                or sums['transit'] != remaining(transfer) or sums['lost'] != transfer['lost_qty']
                or sums['held'] != expected_hold):
            issues.append({'transfer_id':transfer['id'], 'reason':'transfer_custody_mismatch'})
    return issues
