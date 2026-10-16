import hashlib
import secrets
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from .db import transaction


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def provision(db_path, tenant_name, user_name, role='admin', owner_id=None,
              tenant_id=None, warehouse_ids=None):
    """Local administrator-only provisioning. Return credential to caller, never log it."""
    token = secrets.token_urlsafe(32)
    user_id = str(uuid4())
    with transaction(db_path) as db:
        if tenant_id is None:
            if role != 'admin':
                raise ValueError('new tenant requires admin')
            tenant_id = str(uuid4())
            db.execute('INSERT INTO tenants VALUES (?,?)', (tenant_id, tenant_name))
        elif not db.execute('SELECT 1 FROM tenants WHERE id=?', (tenant_id,)).fetchone():
            raise ValueError('unknown tenant')
        if role in ('owner','owner_readonly') and not owner_id:
            raise ValueError('owner account requires owner_id')
        if owner_id and not db.execute('SELECT 1 FROM owners WHERE id=? AND tenant_id=?', (owner_id,tenant_id)).fetchone():
            raise ValueError('owner outside tenant')
        if role not in ('owner','owner_readonly') and owner_id:
            raise ValueError('owner_id only permitted on owner account')
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        db.execute('INSERT INTO users(id,tenant_id,name,role,owner_id,token_hash,expires_at) VALUES (?,?,?,?,?,?,?)',
                   (user_id,tenant_id,user_name,role,owner_id,digest(token),expires))
        for warehouse_id in warehouse_ids or []:
            if not db.execute('SELECT 1 FROM warehouses WHERE id=? AND tenant_id=?', (warehouse_id,tenant_id)).fetchone():
                raise ValueError('warehouse outside tenant')
            db.execute('INSERT INTO user_warehouses VALUES (?,?)', (user_id,warehouse_id))
    return {'token':token,'user_id':user_id,'tenant_id':tenant_id}
