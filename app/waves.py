"""Explicit order selection and allocation-level tasks; caller owns transaction."""
from . import service as s


def create(db, actor, data):
    s.permit(actor, 'staff')
    s.get(db, actor, 'owners', data['owner_id'])
    s.get(db, actor, 'warehouses', data['warehouse_id'])
    if len(set(data['order_ids'])) != len(data['order_ids']):
        s.fail('duplicate_wave_orders', 422)
    allocations = []
    for order_id in data['order_ids']:
        order = s.get(db, actor, 'orders', order_id)
        if any(order[k] != data[k] for k in ('owner_id', 'warehouse_id')):
            s.fail('wave_requires_same_owner_and_warehouse', 422)
        if order['status'] != 'RESERVED':
            s.fail('wave_requires_unpicked_reserved_orders')
        if db.execute('SELECT 1 FROM wave_orders WHERE order_id=? AND active=1', (order_id,)).fetchone():
            s.fail('order_already_in_active_wave')
        rows = db.execute('''SELECT a.*, l.code location_code, s.code sku_code, o.reference order_reference,
                            i.location_id, i.sku_id
            FROM allocations a JOIN inventory i ON i.id=a.inventory_id
            JOIN locations l ON l.id=i.location_id JOIN skus s ON s.id=i.sku_id
            JOIN orders o ON o.id=a.order_id
            WHERE a.tenant_id=? AND a.order_id=? AND a.status='ACTIVE' ''',
            (actor['tenant_id'], order_id)).fetchall()
        if not rows or any(r['picked_qty'] for r in rows):
            s.fail('wave_requires_unpicked_active_allocations')
        allocations.extend(rows)
    wave = s.insert(db, 'waves', {'tenant_id': actor['tenant_id'],
        **{k: data[k] for k in ('owner_id', 'warehouse_id', 'reference')},
        'status': 'OPEN', 'created_by': actor['id'], 'created_at': s.now()})
    for order_id in data['order_ids']:
        db.execute('INSERT INTO wave_orders(wave_id,order_id) VALUES (?,?)', (wave['id'], order_id))
    route = sorted(allocations, key=lambda r: (r['location_code'], r['sku_code'], r['order_reference'], r['id']))
    for sequence, allocation in enumerate(route, 1):
        s.insert(db, 'pick_tasks', {'tenant_id': actor['tenant_id'], 'wave_id': wave['id'],
            **{k: wave[k] for k in ('owner_id', 'warehouse_id')},
            **{k: allocation[k] for k in ('order_id', 'sku_id', 'location_id', 'qty')},
            'allocation_id': allocation['id'], 'sequence': sequence, 'picked_qty': 0,
            'status': 'READY', 'assignee_id': None, 'created_at': s.now()})
    return wave


def refresh_status(db, wave_id):
    tasks = db.execute('SELECT status FROM pick_tasks WHERE wave_id=?', (wave_id,)).fetchall()
    live = [r['status'] for r in tasks if r['status'] != 'CANCELLED']
    status = ('CANCELLED' if not live else 'COMPLETED' if all(v == 'DONE' for v in live)
              else 'PICKING' if any(v != 'READY' for v in live) else 'OPEN')
    db.execute('UPDATE waves SET status=? WHERE id=?', (status, wave_id))


def cancel_order_tasks(db, order_id):
    """Only called after the order's unpicked-state check, in the same transaction."""
    memberships = db.execute('SELECT wave_id FROM wave_orders WHERE order_id=? AND active=1', (order_id,)).fetchall()
    for row in memberships:
        db.execute("UPDATE pick_tasks SET status='CANCELLED' WHERE wave_id=? AND order_id=?", (row['wave_id'], order_id))
        db.execute('UPDATE wave_orders SET active=0 WHERE wave_id=? AND order_id=?', (row['wave_id'], order_id))
        refresh_status(db, row['wave_id'])


def cancel(db, actor, wave_id):
    s.permit(actor, 'staff')
    wave = s.get(db, actor, 'waves', wave_id)
    if wave['status'] in ('COMPLETED', 'CANCELLED'):
        s.fail('wave_already_terminal')
    if db.execute('SELECT 1 FROM pick_tasks WHERE wave_id=? AND picked_qty>0', (wave_id,)).fetchone():
        s.fail('wave_cancel_requires_no_physical_picks')
    db.execute("UPDATE pick_tasks SET status='CANCELLED' WHERE wave_id=?", (wave_id,))
    db.execute('UPDATE wave_orders SET active=0 WHERE wave_id=?', (wave_id,))
    refresh_status(db, wave_id)
    return s.get(db, actor, 'waves', wave_id)


def task_action(db, actor, key, task_id, action, data):
    s.permit(actor, 'staff', 'picker')
    task = s.get(db, actor, 'pick_tasks', task_id)
    wave = s.get(db, actor, 'waves', task['wave_id'])
    if wave['status'] not in ('OPEN', 'PICKING') or task['status'] not in ('READY', 'CLAIMED'):
        s.fail('task_or_wave_not_active')
    if action == 'claim':
        if task['assignee_id'] and task['assignee_id'] != actor['id']:
            s.fail('task_already_claimed')
        db.execute("UPDATE pick_tasks SET status='CLAIMED',assignee_id=? WHERE id=?", (actor['id'], task_id))
    elif action == 'release':
        if task['assignee_id'] != actor['id']:
            s.fail('task_requires_current_assignee', 403)
        if task['picked_qty']:
            s.fail('task_release_requires_no_physical_picks')
        db.execute("UPDATE pick_tasks SET status='READY',assignee_id=NULL WHERE id=?", (task_id,))
    elif action == 'scan':
        if task['status'] != 'CLAIMED' or task['assignee_id'] != actor['id']:
            s.fail('task_requires_current_assignee', 403)
        sku = s.get(db, actor, 'skus', task['sku_id'])
        if data['barcode'] != sku['barcode'] or data['location_id'] != task['location_id'] or data['qty'] > task['qty'] - task['picked_qty']:
            s.fail('wrong_barcode_location_or_excess_pick')
        s.order_action(db, actor, key, task['order_id'], 'pick', data, task_id=task_id)
        picked = task['picked_qty'] + data['qty']
        db.execute('UPDATE pick_tasks SET picked_qty=?,status=? WHERE id=?',
                   (picked, 'DONE' if picked == task['qty'] else 'CLAIMED', task_id))
    else:
        s.fail('unsupported_action', 422)
    refresh_status(db, wave['id'])
    return s.get(db, actor, 'pick_tasks', task_id)
