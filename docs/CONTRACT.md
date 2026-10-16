# Phase 1 contract (2026-10-16)
Coordinator owns app/*.py, app/migrations, dependency/deployment files. UI agent owns app/static. Test agent owns tests. Research agent owns docs/ERP_INTEGRATIONS.md and app/integrations.py only. Migrations exclusively coordinator.

Python FastAPI + SQLite on-disk, single deployment node; BEGIN IMMEDIATE serialized write transactions, guarded stock updates. All requests scoped by hashed Bearer token to tenant; owner users restricted to owner_id, staff/admin to granted warehouses. No built-in default credentials. CLI bootstrap creates tenant/admin; CLI user creates staff/owner access. API mutations require Idempotency-Key (8..128 chars), conflict if different payload reused. Errors JSON {detail: string}. All created objects returned directly with id and fields. Actions return updated object. All POST body JSON. IDs UUID strings. Quantities positive integers. Money integer BRL cents.

GET /api/me -> {id,tenant_id,role,owner_id,name}
GET /api/snapshot -> {owners,warehouses,locations,skus,stores,receipts,orders,order_lines,allocations,inventory,ledger,returns,fees,reconciliation,integrations}. All arrays except reconciliation {ok,issues}, integrations adapter metadata. inventory fields owner_id,warehouse_id,sku_id,location_id,on_hand,reserved,picked,available. Reconciliation checks balances vs ledger and active allocations. Snapshot is read only.
POST /api/owners {name}
POST /api/warehouses {name}
POST /api/locations {warehouse_id,code}
POST /api/skus {owner_id,code,barcode,name}
POST /api/stores {owner_id,name}
POST /api/receipts {owner_id,warehouse_id,sku_id,reference,qty} -> status RECEIVED
POST /api/receipts/{id}/qc {accepted_qty,rejected_qty} -> QC_DONE; accepted+rejected=qty
POST /api/receipts/{id}/putaway {location_id} -> PUTAWAY; only accepted qty to sellable stock
POST /api/orders {owner_id,warehouse_id,store_id,reference,lines:[{sku_id,qty}]} -> CREATED
POST /api/orders/{id}/reserve {} -> RESERVED; atomic full allocation; no physical decrement
POST /api/orders/{id}/pick {barcode,location_id,qty} -> PICKING/PICKED; consumes reserved task qty into picked; on_hand unchanged
POST /api/orders/{id}/verify {barcode,qty} -> PICKED/VERIFIED; tracks verified qty independently
POST /api/orders/{id}/pack {package_reference} -> PACKED; all lines verified
POST /api/orders/{id}/ship {tracking_number,carrier} -> SHIPPED; decrements on_hand and reserved/picked once
POST /api/orders/{id}/cancel {} -> CANCELLED; only CREATED/RESERVED; picked stock requires explicit physical unpick (future), shipping never restores stock
POST /api/returns {order_id,sku_id,qty,reference} -> EXPECTED; shipped qty limit incl existing returns
POST /api/returns/{id}/receive {} -> RECEIVED
POST /api/returns/{id}/qc {accepted_qty,rejected_qty} -> QC_DONE
POST /api/returns/{id}/putaway {location_id} -> PUTAWAY
POST /api/fees {order_id,code,amount_cents} -> unique order/code charge; admin only, BRL
GET /health -> no sensitive data, DB readiness.

UI: Chinese default + pt-BR switch, WMS/OMS/PDA tabs, forms and real server refresh only, token kept only in JS memory, no localStorage business/auth persistence. Render data via textContent to avoid XSS. Explicit unsupported modules, ERP pending authorization. Show resource IDs with labels to support workflows; barcode scanner as keyboard input. Responsive mobile forms. Fetch calls same origin. No third party scripts.

Additive: snapshot.stock_summary aggregates per owner_id/warehouse_id/sku_id with on_hand (qualified putaway bin stock), reserved,picked,available,pending_qc,qualified_unstored,rejected,physical_total. Total physical custody = on_hand+pending_qc+qualified_unstored+rejected. EXPECTED returns not physically present. Rejected goods remain custody until a future authorized scrap/disposal flow (not yet implemented). This avoids counting quality-held goods as sellable or hiding actual receipts.
Roles: finance as well as admin may create manual fees, only after SHIPPED; warehouse timezone optional on create, IANA string default America/Sao_Paulo. Non-admin needs explicit warehouse grants.
OpenAPI JSON at /openapi.json; CDN Swagger UI disabled under strict self-only CSP.
