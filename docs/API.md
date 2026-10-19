# API 使用说明

契约：GET `/openapi.json` 自动生成；仓库副本 `docs/openapi.json`。全部 `/api/*` 要求 `Authorization: Bearer ...`；POST 同时要求 `Idempotency-Key`（8–128 ASCII 字符）。为同一业务提交生成 UUID，网络失败或响应未知时重试原 body/path/key，不能重新生成 key。不同请求复用 key 返回 409。所有创建接口返回 200 与实际记录 ID；读 `/api/snapshot` 核对授权数据，`/api/{resource}/{id}` 单条读取受同样范围控制。

凭证由 CLI 安全签发，30 天有效，仅存 SHA256 摘要，可撤销。没有匿名演示账号、第三方 cookie 或 ERP 共享密码。货主 scope 来自认证，与 body owner_id/仓库/store/SKU二次校验，不信任客户端 tenant_id（未知字段拒绝）。数量 strict integer，不接受 bool/小数。BRL 金额 integer cents。

## 库存口径

`inventory.on_hand` 为合格上架库位库存，`reserved` 为尚未交接的有效预占总量，`picked` 是其已拣子集。`available=on_hand-reserved`。拣货作业仍关联来源库位，视为订单暂存，不支持对已拣单直接取消；不会重复扣库。只有 ship 同事务扣 on_hand/reserved/picked，并将 allocations 标记 SHIPPED。

`stock_summary` 补充待检、合格未上架、不合格/异常保管和物理总量，不能将待检/残次当作可售。退货 EXPECTED 无实收数量；receive 进入 pending_qc；qc 后到 qualified_unstored/rejected；putaway 才入可售库位。残次目前保留，报废/销毁流后续实现。

`reconciliation` 同时校验余额=流水求和、预占/已拣=有效分配求和。收货 QC/上架、所有订单动作和退货动作都由状态机阻断乱序；流水 SQL trigger 禁止业务 update/delete，余额无普通编辑 API。数据库文件访问者仍为受信运维，SQLite 不是多数据库角色隔离系统。

## 业务与权限

具体 body 和状态见 CONTRACT.md；OpenAPI 为可机读 schema。admin 管理本租户，其他角色逐仓授权，货主账号进一步只见自己的商品/订单/库存/收费。返回 401 表示凭证无效/过期/撤销；403 为角色不符；404 为不存在或不在范围；409 为状态/余量/唯一性冲突；422 为输入/归属错误；429 需等待；503 DB忙或不可用，可同key重试。错误 detail 为稳定技术代码，页面展示原文辅助排错；完整中葡业务错误词典后续完善。

当前只支持整单单包裹、可多 SKU 多库位分配；不支持部分发货、多包裹、波次、实体回位撤销。pack登记包裹参考，ship登记已有运单和实际交接，不购买物流或打印标签。手工费用只允许实际已发订单，每 order_id/code 唯一；没有自动收费、报价版本、正式账单/支付。关联退货总申请不超过原发货数量。

当前 API 是任务书路径 C，本系统开放 API。ERP 的卖家 API A 与服务商接入 B 均待正式协议/权限；不把内部接口称为已对接第三方。无 webhook/inbox/outbox/worker 成功响应，可靠同步后续独立实现。

## 服务容量与日志

请求 body 上限 256KiB；单节点认证失败 30/分钟（进程内按直接连接 IP），生产须网关限流，反代下此计数可能共享同一入口IP。快照当前返回全部授权记录，分页/时间筛选后续实现，大数据量不适用；小样本测试不等于生产容量。禁用 uvicorn access log，应用仅记 status/duration；部署人员不得启用请求头/正文记录。

## 0.3库内作业补充（本节覆盖旧阶段1限制）

已支持波次/独立拣货任务和同仓人工补货/移位，仍不支持部分发货、多包裹、盘点、跨仓调拨和实体回位取消。完整body/角色/状态见CONTRACT。

- 管理员/staff选择同货主同仓已预占订单建波次；picker领取任务后按订单容器逐单扫码，COMPLETED仅拣货完成，仍需原逐单verify/pack/ship。活动波次不能通过旧pick绕过。
- POST `/api/movements {source_inventory_id,destination_location_id,kind,reference,qty}`，kind为MOVE或REPLENISHMENT。任务创建锁定来源可用数量。claim领取、dispatch来源实际搬出、receive目标实际到位；dispatch/receive body均为{barcode,location_id,qty}，必须整任务数量。
- move_reserved独立于订单reserved；available=on_hand−reserved−move_reserved。库内搬运中in_transit不可销售，仍计入physical_total。release只释放领取，cancel才在搬出前释放数量锁；搬出后不能直接取消。
- 仓内任务数据不对货主等非作业角色开放，库存数量汇总仍准确包含自身搬运中实物。错误扫描、状态冲突、权限不足和未知响应均由服务端处理；若响应未知，保留原body/path/key重试。

旧文中“available=on_hand-reserved”仅适用于无搬运锁的阶段1数据，当前口径以上式为准；本轮迁移003给旧记录新增字段默认0。

## 0.4盘点入口

新增stock_counts/count_lines/count_attempts/count_operators；范围为单货主、单仓、单SKU及明确库位。admin/staff建单、安排不同专用账号实盘/复盘；admin填写原因后审批。详见CONTRACT。专用盘点凭证由CLI `user --role picker --count-only`签发，只能读取/提交自己的任务，不能读账面或其他业务数据。

盘点截点只在测量暂停时采集，读数提交即释放测量锁。短少另记count_reserved，其他数量可以正常作业。inventory.count_locked=true时available=0；其他时候available=on_hand−reserved−move_reserved−count_reserved。审批只把差额加到当时余额，保留截点后所有合法流水；不能按历史实盘数覆盖当前库存。本文前面“尚未支持盘点”属于旧版本范围，0.4以上述契约为准。
