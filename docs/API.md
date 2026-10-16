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
