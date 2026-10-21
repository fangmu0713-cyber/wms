ALTER TABLE ledger ADD COLUMN transfer_transit_delta INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ledger ADD COLUMN transfer_lost_delta INTEGER NOT NULL DEFAULT 0;
CREATE TABLE transfers(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 owner_id TEXT NOT NULL REFERENCES owners(id), sku_id TEXT NOT NULL REFERENCES skus(id),
 source_warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 destination_warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 source_inventory_id TEXT NOT NULL REFERENCES inventory(id),
 source_location_id TEXT NOT NULL REFERENCES locations(id), reference TEXT NOT NULL,
 qty INTEGER NOT NULL CHECK(qty>0), received_qty INTEGER NOT NULL DEFAULT 0 CHECK(received_qty>=0),
 lost_qty INTEGER NOT NULL DEFAULT 0 CHECK(lost_qty>=0),
 status TEXT NOT NULL CHECK(status IN ('TRANSFER_PLANNED','DISPATCHED','PART_RECEIVED','COMPLETED','CLOSED_WITH_LOSS','CANCELLED')),
 carrier TEXT, tracking_number TEXT, created_by TEXT NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL, dispatched_at TEXT, completed_at TEXT,
 CHECK(source_warehouse_id<>destination_warehouse_id),
 CHECK(received_qty+lost_qty<=qty),
 CHECK((status IN ('TRANSFER_PLANNED','CANCELLED') AND received_qty=0 AND lost_qty=0 AND dispatched_at IS NULL AND completed_at IS NULL) OR
       (status='DISPATCHED' AND received_qty=0 AND lost_qty=0 AND dispatched_at IS NOT NULL AND completed_at IS NULL) OR
       (status='PART_RECEIVED' AND received_qty>0 AND received_qty<qty AND lost_qty=0 AND dispatched_at IS NOT NULL AND completed_at IS NULL) OR
       (status='COMPLETED' AND received_qty=qty AND lost_qty=0 AND dispatched_at IS NOT NULL AND completed_at IS NOT NULL) OR
       (status='CLOSED_WITH_LOSS' AND received_qty+lost_qty=qty AND lost_qty>0 AND dispatched_at IS NOT NULL AND completed_at IS NOT NULL)),
 UNIQUE(tenant_id,source_warehouse_id,reference)
);
CREATE INDEX transfer_scope ON transfers(tenant_id,owner_id,source_warehouse_id,destination_warehouse_id,status);
CREATE INDEX transfer_source ON transfers(source_inventory_id,status);
CREATE TABLE transfer_events(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 transfer_id TEXT NOT NULL REFERENCES transfers(id),
 kind TEXT NOT NULL CHECK(kind IN ('DISPATCH','RECEIVE','LOSS','CANCEL')),
 reference TEXT NOT NULL, qty INTEGER NOT NULL CHECK(qty>0),
 location_id TEXT REFERENCES locations(id), actor_id TEXT NOT NULL REFERENCES users(id),
 reason TEXT, created_at TEXT NOT NULL,
 UNIQUE(transfer_id,kind,reference)
);
CREATE TRIGGER transfer_event_no_update BEFORE UPDATE ON transfer_events BEGIN SELECT RAISE(ABORT,'immutable transfer event'); END;
CREATE TRIGGER transfer_event_no_delete BEFORE DELETE ON transfer_events BEGIN SELECT RAISE(ABORT,'immutable transfer event'); END;
