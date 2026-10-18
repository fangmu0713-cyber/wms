# Phase 1 contract (2026-10-16)
Coordinator owns app/*.py, app/migrations, dependency/deployment files. UI agent owns app/static. Test agent owns tests. Research agent owns docs/ERP_INTEGRATIONS.md and app/integrations.py only. Migrations exclusively coordinator.

Python FastAPI + SQLite on-disk, single deployment node; BEGIN IMMEDIATE serialized write transactions, guarded stock updates. All requests scoped by hashed Bearer token to tenant; owner users restricted to owner_id, staff/admin to granted warehouses. No built-in default credentials. CLI bootstrap creates tenant/admin; CLI user creates staff/owner access. API mutations require Idempotency-Key (8..128 chars), conflict if different payload reused. Errors JSON {detail: string}. All created objects returned directly with id and fields. Actions return updated object. All POST body JSON. IDs UUID strings. Quantities positive integers. Money integer BRL cents.

GET /api/me -> {id,tenant_id,role,owner_id,name}
GET /api/snapshot -> {owners,warehouses,locations,skus,stores,receipts,orders,order_lines,allocations,inventory,ledger,returns,fees,reconciliation,integrations}. All arrays except reconciliation {ok,issues}, integrations adapter metadata. inventory fields owner_id,warehouse_id,sku_id,location_id,on_hand,reserved,picked,available. Current additions: waves, pick_tasks, wave_orders, movements; inventory.move_reserved, stock_summary.in_transit. Reconciliation checks balances vs ledger, active allocations and movement custody. Snapshot is read only.
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

## 波次与独立拣货任务（002）

POST `/api/waves {owner_id,warehouse_id,reference,order_ids:[...]}`：admin/staff，1–100个不同订单，同货主同仓、RESERVED且分配零已拣；任一无效整笔回滚。租户/仓库/reference唯一，每订单至多一个有效波次。按库位代码、SKU代码、订单参考号、分配ID字典序生成任务，不代表最优路径或汇总后二次分拣。

POST `/api/waves/{id}/cancel {}`：admin/staff，只有零实拣时允许，撤任务/成员关系但保留订单预占。取消未拣订单同步撤对应任务并释放其预占。活动波次订单旧pick报pick_via_wave_task_required。

POST `/api/pick_tasks/{id}/claim {}`、`release {}`、`scan {barcode,location_id,qty}`：admin/staff/picker，self claim；只有领取人可扫描，零已拣可release。任务状态READY→CLAIMED→DONE，未拣取消为CANCELLED；波次OPEN→PICKING→COMPLETED，全部取消则CANCELLED。COMPLETED只表示拣货完成，不代表交接出库。部分已拣不支持直接取消/换人/回位。

GET单条waves/pick_tasks和snapshot中的waves/pick_tasks/wave_orders仅admin/staff/picker可见，均受租户/仓授权过滤；其他角色数组为空。wave_orders为{wave_id,order_id,active}。任务包括wave/order/allocation/SKU/location及owner/warehouse、sequence、qty、picked_qty、status、assignee_id、created_at。

## 同仓补货与移位（003）

POST `/api/movements {source_inventory_id,destination_location_id,kind,reference,qty}`：admin/staff。kind=MOVE或REPLENISHMENT，qty为正整数；来源由服务端库存记录推导owner/warehouse/SKU，目标必须同仓不同库位。只允许来源可分配数量，不能移动订单已预占/已拣或其他搬运锁定数量。人工补货使用同一物理流程，不声称有自动阈值、库区类型或需求预测规则。

创建即增加来源inventory.move_reserved；on_hand仍包含待搬实物。ledger增加move_reserved_delta和in_transit_delta，旧事件默认0。

|动作|角色/状态|结果|
|---|---|---|
|claim {}|admin/staff/picker/receiver，PLANNED或同一领取人CLAIMED|自领，CLAIMED；并发其他领取人409|
|release {}|当前领取人，CLAIMED|回PLANNED，释放领取，保留库存锁|
|cancel {}|admin/staff，PLANNED/CLAIMED|CANCELLED，释放move_reserved，不移动实物|
|dispatch {barcode,location_id,qty}|当前领取人，CLAIMED|必须源库位/正确SKU条码/整任务qty；源on_hand和move_reserved各减qty，in_transit_delta+qty，IN_TRANSIT|
|receive {barcode,location_id,qty}|当前领取人，IN_TRANSIT|必须目标库位/正确SKU条码/整任务qty；目标on_hand+qty，in_transit_delta−qty，COMPLETED|

动作路径为POST `/api/movements/{id}/{action}`，全部使用既有actor-scoped幂等键；重试原body/path/key。库存与任务、状态、时间戳、账本、审计、幂等同一BEGIN IMMEDIATE事务。未知响应不能另建任务、重新计件或取消已经实际搬出的货。

movement字段：id、tenant/owner/warehouse/SKU、source_inventory_id、source_location_id、destination_location_id、kind/reference/qty/status、assignee_id、created_by、created_at/dispatched_at/completed_at。reference在tenant/warehouse下唯一。终态禁止新键重复动作；原键可以重放原确认结果。

GET `/api/movements/{id}`及snapshot.movements仅admin/staff/picker/receiver可读，租户/仓范围照常检查。货主只见自己库存/质量汇总和账本数量，不暴露搬运任务及领取人记录；汇总和核对在服务器内使用同范围任务计算，不能因隐藏任务而漏算实物。

当前库存口径：
- available = on_hand − reserved − move_reserved，数据库CHECK保证reserved+move_reserved≤on_hand且均非负。
- picked是reserved子集，不能重复扣可用。搬出减少来源库位on_hand而增加同仓in_transit，目标确认再反向转换；并非销售出库。
- stock_summary新增move_reserved、in_transit；physical_total = on_hand + in_transit + pending_qc + qualified_unstored + rejected。搬运中不可再次预占。
- 核对：库位on_hand/reserved/picked/move_reserved等于账本累加，订单预占/已拣等于有效分配，move_reserved等于未搬出任务数量，逐任务in_transit_delta累加等于IN_TRANSIT任务qty，否则0。

当前仅整任务数量、同仓、同SKU/货主；不支持部分搬出/接收、损耗、跨仓调拨、搬出后取消/回位/换人。迁移只增量改变003，保留原库存/已拣波次；健康检查必须全部已发布迁移齐全。存在新业务后不能直接回退旧版本代码，不提供破坏性down。
