CREATE TABLE waves(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 owner_id TEXT NOT NULL REFERENCES owners(id), warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 reference TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('OPEN','PICKING','COMPLETED','CANCELLED')),
 created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
 UNIQUE(tenant_id,warehouse_id,reference)
);
CREATE TABLE wave_orders(
 wave_id TEXT NOT NULL REFERENCES waves(id), order_id TEXT NOT NULL REFERENCES orders(id),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), PRIMARY KEY(wave_id,order_id)
);
CREATE UNIQUE INDEX one_active_wave_per_order ON wave_orders(order_id) WHERE active=1;
CREATE TABLE pick_tasks(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 owner_id TEXT NOT NULL REFERENCES owners(id), warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 wave_id TEXT NOT NULL REFERENCES waves(id), order_id TEXT NOT NULL REFERENCES orders(id),
 allocation_id TEXT NOT NULL REFERENCES allocations(id), sku_id TEXT NOT NULL REFERENCES skus(id),
 location_id TEXT NOT NULL REFERENCES locations(id), sequence INTEGER NOT NULL CHECK(sequence>0),
 qty INTEGER NOT NULL CHECK(qty>0), picked_qty INTEGER NOT NULL DEFAULT 0 CHECK(picked_qty>=0 AND picked_qty<=qty),
 status TEXT NOT NULL CHECK(status IN ('READY','CLAIMED','DONE','CANCELLED')),
 assignee_id TEXT REFERENCES users(id), created_at TEXT NOT NULL,
 CHECK((status='READY' AND assignee_id IS NULL AND picked_qty=0) OR
       (status='CLAIMED' AND assignee_id IS NOT NULL AND picked_qty<qty) OR
       (status='DONE' AND assignee_id IS NOT NULL AND picked_qty=qty) OR
       (status='CANCELLED' AND picked_qty=0)),
 UNIQUE(wave_id,allocation_id), UNIQUE(wave_id,sequence)
);
CREATE INDEX waves_scope ON waves(tenant_id,owner_id,warehouse_id,status);
CREATE INDEX pick_tasks_scope ON pick_tasks(tenant_id,owner_id,warehouse_id,wave_id,status);
