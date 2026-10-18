"""Same-warehouse movement with a stock hold and explicit physical custody."""
from . import service as s


EXECUTION_ROLES = ('staff', 'picker', 'receiver')


def create(db, actor, key, data):
    s.permit(actor, 'staff')
    source = s.get(db, actor, 'inventory', data['source_inventory_id'])
    destination = s.get(db, actor, 'locations', data['destination_location_id'])
    if source['warehouse_id'] != destination['warehouse_id']:
        s.fail('movement_requires_same_warehouse', 422)
    if source['location_id'] == destination['id']:
        s.fail('movement_requires_different_locations', 422)
    if data['qty'] > source['on_hand'] - source['reserved'] - source['move_reserved']:
        s.fail('insufficient_available_stock_for_movement')
    movement = s.insert(db, 'movements', {
        **{k: source[k] for k in ('tenant_id', 'owner_id', 'warehouse_id', 'sku_id')},
        **data, 'source_location_id': source['location_id'], 'status': 'PLANNED',
        'assignee_id': None, 'created_by': actor['id'], 'created_at': s.now(),
        'dispatched_at': None, 'completed_at': None})
    s.stock(db, actor, key, source, movement['id'], 'MOVE_HOLD', move_reserved=data['qty'])
    return movement


def action(db, actor, key, object_id, action, data):
    if action == 'cancel':
        s.permit(actor, 'staff')
    else:
        s.permit(actor, *EXECUTION_ROLES)
    movement = s.get(db, actor, 'movements', object_id)
    status = movement['status']
    if status in ('COMPLETED', 'CANCELLED'):
        s.fail('movement_already_terminal')
    if action == 'cancel':
        if status not in ('PLANNED', 'CLAIMED'):
            s.fail('movement_cancel_requires_not_dispatched')
        source = s.get(db, actor, 'inventory', movement['source_inventory_id'])
        s.stock(db, actor, key, source, object_id, 'MOVE_CANCEL', move_reserved=-movement['qty'])
        db.execute("UPDATE movements SET status='CANCELLED' WHERE id=?", (object_id,))
    elif action == 'claim':
        if status not in ('PLANNED', 'CLAIMED'):
            s.fail('movement_claim_requires_not_dispatched')
        if movement['assignee_id'] and movement['assignee_id'] != actor['id']:
            s.fail('movement_already_claimed')
        db.execute("UPDATE movements SET status='CLAIMED',assignee_id=? WHERE id=?", (actor['id'], object_id))
    else:
        if movement['assignee_id'] != actor['id']:
            s.fail('movement_requires_current_assignee', 403)
        if action == 'release':
            if status != 'CLAIMED':
                s.fail('movement_release_requires_not_dispatched')
            db.execute("UPDATE movements SET status='PLANNED',assignee_id=NULL WHERE id=?", (object_id,))
        elif action in ('dispatch', 'receive'):
            expected_status = 'CLAIMED' if action == 'dispatch' else 'IN_TRANSIT'
            if status != expected_status:
                s.fail('movement_wrong_physical_stage')
            location_field = 'source_location_id' if action == 'dispatch' else 'destination_location_id'
            sku = s.get(db, actor, 'skus', movement['sku_id'])
            if (data['barcode'] != sku['barcode'] or data['location_id'] != movement[location_field]
                    or data['qty'] != movement['qty']):
                s.fail('movement_wrong_barcode_location_or_quantity')
            if action == 'dispatch':
                source = s.get(db, actor, 'inventory', movement['source_inventory_id'])
                s.stock(db, actor, key, source, object_id, 'MOVE_DISPATCH',
                        on_hand=-movement['qty'], move_reserved=-movement['qty'], in_transit=movement['qty'])
                db.execute("UPDATE movements SET status='IN_TRANSIT',dispatched_at=? WHERE id=?", (s.now(), object_id))
            else:
                destination = s.get(db, actor, 'locations', movement['destination_location_id'])
                if destination['warehouse_id'] != movement['warehouse_id']:
                    s.fail('movement_requires_same_warehouse', 422)
                inventory = db.execute('''SELECT * FROM inventory
                    WHERE tenant_id=? AND owner_id=? AND warehouse_id=? AND sku_id=? AND location_id=?''',
                    (actor['tenant_id'], movement['owner_id'], movement['warehouse_id'], movement['sku_id'], destination['id'])).fetchone()
                if not inventory:
                    inventory = s.insert(db, 'inventory', {
                        **{k: movement[k] for k in ('tenant_id', 'owner_id', 'warehouse_id', 'sku_id')},
                        'location_id': destination['id']})
                s.stock(db, actor, key, inventory, object_id, 'MOVE_RECEIVE',
                        on_hand=movement['qty'], in_transit=-movement['qty'])
                db.execute("UPDATE movements SET status='COMPLETED',completed_at=? WHERE id=?", (s.now(), object_id))
        else:
            s.fail('unsupported_action', 422)
    return s.get(db, actor, 'movements', object_id)
