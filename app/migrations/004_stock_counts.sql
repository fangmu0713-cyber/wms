ALTER TABLE users ADD COLUMN count_only INTEGER NOT NULL DEFAULT 0 CHECK(count_only IN (0,1));
ALTER TABLE inventory ADD COLUMN count_reserved INTEGER NOT NULL DEFAULT 0
 CHECK(count_reserved>=0 AND reserved+move_reserved+count_reserved<=on_hand);
ALTER TABLE ledger ADD COLUMN count_reserved_delta INTEGER NOT NULL DEFAULT 0;
CREATE TABLE stock_counts(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 owner_id TEXT NOT NULL REFERENCES owners(id), warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 sku_id TEXT NOT NULL REFERENCES skus(id), reference TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('OPEN','REVIEW','APPROVED','CANCELLED')),
 created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
 reviewed_by TEXT REFERENCES users(id), reviewed_at TEXT, reason TEXT,
 UNIQUE(tenant_id,warehouse_id,reference)
);
CREATE TABLE count_lines(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 owner_id TEXT NOT NULL REFERENCES owners(id), warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 sku_id TEXT NOT NULL REFERENCES skus(id), location_id TEXT NOT NULL REFERENCES locations(id),
 session_id TEXT NOT NULL REFERENCES stock_counts(id), inventory_id TEXT NOT NULL REFERENCES inventory(id),
 status TEXT NOT NULL CHECK(status IN ('COUNTING','RECOUNT_REQUIRED','CONFIRMED','APPROVED','CANCELLED')),
 hold_qty INTEGER NOT NULL DEFAULT 0 CHECK(hold_qty>=0), accepted_delta INTEGER,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 UNIQUE(session_id,inventory_id)
);
CREATE UNIQUE INDEX one_active_count_per_inventory ON count_lines(inventory_id) WHERE active=1;
CREATE TABLE count_attempts(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 owner_id TEXT NOT NULL REFERENCES owners(id), warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
 sku_id TEXT NOT NULL REFERENCES skus(id), location_id TEXT NOT NULL REFERENCES locations(id),
 session_id TEXT NOT NULL REFERENCES stock_counts(id), line_id TEXT NOT NULL REFERENCES count_lines(id),
 counter_id TEXT NOT NULL REFERENCES users(id), round INTEGER NOT NULL CHECK(round>0),
 baseline_on_hand INTEGER NOT NULL CHECK(baseline_on_hand>=0), cutoff_seq INTEGER NOT NULL CHECK(cutoff_seq>=0),
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','SUBMITTED','CANCELLED')),
 counted_qty INTEGER CHECK(counted_qty>=0), delta INTEGER,
 created_at TEXT NOT NULL, submitted_at TEXT,
 CHECK((status='ACTIVE' AND counted_qty IS NULL AND delta IS NULL AND submitted_at IS NULL) OR
       (status='SUBMITTED' AND counted_qty IS NOT NULL AND delta=counted_qty-baseline_on_hand AND submitted_at IS NOT NULL) OR status='CANCELLED'),
 UNIQUE(line_id,round)
);
CREATE UNIQUE INDEX one_active_count_attempt ON count_attempts(line_id) WHERE status='ACTIVE';
CREATE TABLE count_locks(
 inventory_id TEXT PRIMARY KEY REFERENCES inventory(id),
 session_id TEXT NOT NULL REFERENCES stock_counts(id), line_id TEXT NOT NULL REFERENCES count_lines(id),
 attempt_id TEXT NOT NULL UNIQUE REFERENCES count_attempts(id)
);
CREATE INDEX stock_counts_scope ON stock_counts(tenant_id,owner_id,warehouse_id,status);
CREATE INDEX count_attempts_assignee ON count_attempts(tenant_id,counter_id,status);
CREATE TRIGGER count_cutoff_immutable BEFORE UPDATE OF baseline_on_hand,cutoff_seq,counter_id,line_id,round ON count_attempts
 BEGIN SELECT RAISE(ABORT,'immutable count cutoff'); END;
CREATE TRIGGER submitted_count_immutable BEFORE UPDATE ON count_attempts WHEN OLD.status='SUBMITTED'
 BEGIN SELECT RAISE(ABORT,'immutable submitted count'); END;
CREATE TRIGGER count_attempt_no_delete BEFORE DELETE ON count_attempts
 BEGIN SELECT RAISE(ABORT,'retained count evidence'); END;
