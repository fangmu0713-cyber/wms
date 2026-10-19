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

## 0.4 盘点、盲盘凭证与差异审批（004）

盘点范围是一个货主、一个仓库、一个已知SKU及1–100个明确库位，包含该SKU在所选空库位的零余额；不是整仓所有SKU，也不含待检、残次、库内搬运中或尚未归属的商品。盘点为实盘程序，操作员应核对货主标识、SKU和库位，不在测量暂停范围内移入/取出货物。

POST `/api/stock_counts {owner_id,warehouse_id,sku_id,location_ids,reference,counter_id}`：admin/staff。reference在tenant/warehouse唯一，库位不得重复且均同仓，SKU归属货主。创建每行快照baseline_on_hand和只追加ledger的rowid截点cutoff_seq，同事务取得inventory级测量锁。存在订单预占/已拣/待搬、其他盘点差异锁或其他有效盘点行时拒绝，整单原子创建。

### 专用盲盘凭证

users.count_only默认0，不改变原8角色或既有权限。CLI `user --role picker --count-only`单独签发；仅可GET `/api/me`、`/api/snapshot`、本人的`/api/count_attempts/{id}`，以及POST本人的`/api/count_attempts/{id}/submit`。不能读取库存、流水、收发单、费用、别人的读数或主管盘点依据，也不能调用原picker业务写接口。

专用snapshot只含本人任务和对应货主/仓库/SKU/库位主数据；库存、流水、库存汇总、盘点单/行、其他业务和操作员名单数组为空。任务投影只有id、owner/warehouse/SKU/location/session/line、counter_id、round、status、本人counted_qty、created_at/submitted_at；不含baseline、cutoff、delta或短少锁。原键重试响应也使用同一脱敏投影。

admin/staff在snapshot的count_operators查看有仓授权、有效且未撤销的专用盘点账号{id,name,warehouse_id}，可查看盘点单、行和原始实盘依据。其他普通角色的盘点数组为空。服务器区分不同账号，不验证现实人员身份；人员独立性由仓库管理保证。

### 实盘与复盘

POST `/api/count_attempts/{id}/submit {barcode,location_id,qty}`：仅分配到该任务的专用盘点凭证，qty为0–1,000,000严格整数。必须匹配SKU/库位；任务ACTIVE且测量锁与截点均仍有效。提交后读数与截点不可更改/删除，原键可重放，其他新键不得改数。

测量锁暂停该库存的上架、预占、拣货、搬运等数量写入；预占可选其他未暂停库位。snapshot.inventory.count_locked为true时available=0，不能把该暂停余额当成可立即分配。读数提交后释放测量锁，允许合法作业继续。

每次delta=counted_qty−baseline_on_hand。首盘delta=0可CONFIRMED；非零须RECOUNT_REQUIRED。POST `/api/count_lines/{id}/recount {counter_id}`由admin/staff分配另一有效专用账号；不得与最近一次读数账号相同。复盘重新取得当时的账面与流水截点，并暂停该行作业；仍要求无订单/搬运占用（允许本行已有count_reserved）。最近两次不同账号的delta相同才CONFIRMED；不一致继续复盘，比较的是各自截点的差额，不能直接比较两个不同时刻的实盘总数。

短少一经记录即增加inventory.count_reserved及ledger.count_reserved_delta，取历次观察短少最大值保守锁定；复盘期间不因为单次新读数减少锁定。该锁不改变on_hand，但阻止订单/搬运重复占用已知短少数量。除测量暂停外，available=on_hand−reserved−move_reserved−count_reserved。

### 审批与取消

所有行CONFIRMED后盘点单REVIEW。POST `/api/stock_counts/{id}/approve {reason}`仅admin，原因3–500字符；按行在当前on_hand上加accepted_delta，并释放本行count_reserved，写COUNT_ADJUST账本，整单库存/流水/状态/幂等/审计同事务。绝不把当前余额覆盖成历史counted_qty。

例如100账面实盘98（差额−2），期间发3，复盘时账面97实盘95（仍−2），复盘后再发5，审批前账面92，审批后90；不会恢复到95或98。盘后新上架、移位/搬运与已存在预占同样保留，负向差额与锁释放在一次原子库存更新完成。

POST `/api/stock_counts/{id}/cancel {reason}`允许admin/staff在OPEN/REVIEW取消，释放测量锁及差异锁，保留提交证据/审计，不更正实物差异；必须继续调查，不能当作差异已解决。终态不能以新键再审批/取消。

状态：盘点单OPEN→REVIEW→APPROVED或CANCELLED；库位行COUNTING→RECOUNT_REQUIRED/CONFIRMED→APPROVED/CANCELLED；测量任务ACTIVE→SUBMITTED或未提交时CANCELLED。一个库存余额同时最多一个有效盘点行，一行最多一个ACTIVE实盘任务。

核对增加count_reserved投影=账本累加=有效count_lines.hold_qty之和；备份恢复验证该投影和ACTIVE任务的持久测量锁，缺004服务健康/认证返回503。既有用户迁移后count_only=0；专用盘点账号必须明确另行签发。

当前无全仓多SKU自动盘点计划、未标识商品认领、货主自助盘点或跨仓盘点。旧0.3不理解测量锁/count_reserved，且不会强制count_only凭证边界，禁止直接切回旧代码。回退须停写、保留新流水、撤销专用盘点凭证并人工对账，优先前向修复；无破坏性down。


## 0.5 跨仓调拨（005）

单货主/单SKU/单源库位、另一目标仓库，不能转移货主归属。POST `/api/transfers {source_inventory_id,destination_warehouse_id,reference,qty}`：admin/staff，主管须源/目标两仓授权；源租户/货主/SKU/库位均由库存推导，目标须同租户不同仓。reference在tenant/source_warehouse唯一。建单状态TRANSFER_PLANNED，来源move_reserved增加qty，与同仓搬运共用待作业锁，预占路径扣除它；测量锁与count_reserved继续生效。

GET `/api/transfers/{id}`与snapshot.transfers/transfer_events仅admin/staff/picker/receiver可读，当前租户且至少有一端仓权限；可见单据含双方ID、数量、参考号、状态、承运方/运单和操作记录，未授权仓的其他主数据/余额不因此开放。货主/财务的调拨操作数组为空，其授权库存汇总/核对仍计算调拨。专用count_only的路由、快照、缓存隔离继续生效，调拨与事件数组为空。

POST `/api/transfers/{id}/dispatch {barcode,location_id,qty,carrier,tracking_number}`：admin/staff/picker，须源仓权限，TRANSFER_PLANNED、正确SKU/源库位、完整单qty；on_hand−qty、move_reserved−qty、transfer_transit_delta+qty，状态DISPATCHED。承运方/运单是手工记录，不代表已连接承运商。无需将两仓权限授给发出人员。

POST `/api/transfers/{id}/receive {barcode,location_id,qty,receipt_reference}`：admin/staff/receiver，须目标仓权限，DISPATCHED/PART_RECEIVED；正整数qty≤剩余在途，正确SKU、目标仓实际库位。仅确认合格实到件；目标on_hand+qty、transfer_transit_delta−qty，不改源仓余额。可多批/多库位，收到全qty后COMPLETED，否则PART_RECEIVED。每个transfer_id/kind=RECEIVE/receipt_reference唯一，跨账号或新幂等键重复同批也拒绝；未知响应重用原键可重放原响应。不能按目标库存增减倒推实际签收。

POST `/api/transfers/{id}/cancel {reason}`：admin/staff，须两仓权限，仅TRANSFER_PLANNED，释放来源move_reserved、不改变实物，CANCELLED。原因3–500字符。

POST `/api/transfers/{id}/close_loss {qty,reason}`：仅admin，在DISPATCHED/PART_RECEIVED、qty必须等于全部剩余在途且>0、原因3–500字符。根据已确认在途丢失依据结案，ledger.transfer_transit_delta−qty、transfer_lost_delta+qty，on_hand不变，CLOSED_WITH_LOSS。不是残次实到登记/报废或赔偿、财务结算；未查明异常继续在途。终态不允许再次接收/取消/反向改写；找回与物理退回待独立流程。结案账本锚定源inventory，源库存实盘测量时需先结束测量再结案。

各动作与余额、不可改删transfer_events、账本、审计、幂等记录同一BEGIN IMMEDIATE事务。事件有kind、qty、reference、location_id、actor_id、reason、created_at。收到响应丢失时只重试原请求；旧键响应重放仍检查当前角色与相应端的仓授权，不重新执行终态动作。新的键不能再dispatch或重复终态处理。正整数严格校验，禁止bool/小数/0/负数。

库存口径：available继续扣订单、move_reserved及count_reserved，测量锁时为0。原in_transit只表示同仓搬运；新增transfer_in_transit按源仓归集仍未结案的qty−received_qty−lost_qty，目标仓不重复计算在途；transfer_lost是源仓累计确认丢失的历史量，不是现存实物。physical_total=on_hand+同仓in_transit+transfer_in_transit+pending_qc+qualified_unstored+rejected。一端权限视图仅计算该端库存与源端责任在途，接收不会双计。全租户调拨时在库+在途守恒，确认丢失时减少保管实物、历史丢失增加。

核对：move_reserved=未搬出同仓任务+未发出调拨；逐调拨事件与当前received/lost/dispatch/cancel状态一致；跨两仓账本on_hand_delta累加=已接收−已发出、transfer_transit_delta=剩余在途、transfer_lost_delta=lost_qty、move_reserved_delta=未发出锁。服务端内部读取可见单据的两端流水来核对，不向调用者返回未授权仓账本。恢复工具同样拒绝账本/调拨事件/锁投影不符。005只增不改001–004，已有ledger新增列为0。缺迁移健康503，无破坏性down；不得切回不理解调拨锁与在途的旧代码继续写入。

当前无多SKU合单、部分发出、跨货主转移、调拨退回、在途找回撤销、残次接收/处置、物流API或实机验收。
