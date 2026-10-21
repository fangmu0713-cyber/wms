ALTER TABLE inventory ADD COLUMN move_reserved INTEGER NOT NULL DEFAULT 0
 CHECK(move_reserved>=0 AND reserved+move_reserved<=on_hand);
ALTER TABLE ledger ADD COLUMN move_reserved_delta INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ledger ADD COLUMN in_transit_delta INTEGER NOT NULL DEFAULT 0;
CREATE TABLE movements(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 owner_id TEXT NOT NULL REFERENCES owners(id), warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 sku_id TEXT NOT NULL REFERENCES skus(id), source_inventory_id TEXT NOT NULL REFERENCES inventory(id),
 source_location_id TEXT NOT NULL REFERENCES locations(id), destination_location_id TEXT NOT NULL REFERENCES locations(id),
 kind TEXT NOT NULL CHECK(kind IN ('MOVE','REPLENISHMENT')), reference TEXT NOT NULL,
 qty INTEGER NOT NULL CHECK(qty>0),
 status TEXT NOT NULL CHECK(status IN ('PLANNED','CLAIMED','IN_TRANSIT','COMPLETED','CANCELLED')),
 assignee_id TEXT REFERENCES users(id), created_by TEXT NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL, dispatched_at TEXT, completed_at TEXT,
 CHECK(source_location_id<>destination_location_id),
 CHECK((status='PLANNED' AND assignee_id IS NULL AND dispatched_at IS NULL AND completed_at IS NULL) OR
       (status='CLAIMED' AND assignee_id IS NOT NULL AND dispatched_at IS NULL AND completed_at IS NULL) OR
       (status='IN_TRANSIT' AND assignee_id IS NOT NULL AND dispatched_at IS NOT NULL AND completed_at IS NULL) OR
       (status='COMPLETED' AND assignee_id IS NOT NULL AND dispatched_at IS NOT NULL AND completed_at IS NOT NULL) OR
       (status='CANCELLED' AND dispatched_at IS NULL AND completed_at IS NULL)),
 UNIQUE(tenant_id,warehouse_id,reference)
);
CREATE INDEX movements_scope ON movements(tenant_id,owner_id,warehouse_id,status);
CREATE INDEX movements_source ON movements(source_inventory_id,status);
