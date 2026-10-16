# ERP 适配开发与接续

核查日期：2026-10-16。当前五家供应商均待接入，详见 [ERP_CAPABILITIES.md](ERP_CAPABILITIES.md)。本阶段的真实内部业务由手工订单和本系统 API 驱动；第三方没有接通。

## 已交付代码

`app/integrations.py` 定义 `ERPAdapter` Protocol、规范仓库/库存观测/订单/包裹出库通知模型和能力枚举。`get_registry()` 每次返回新的 JSON 数据，不携带凭证；每个能力分别记录官方文档是否已确认、是否实现、是否启用和是否真实测试。`documented=true` 仅表示官方已公开能力，不表示具备协议全部细节或账号权限。

`create_adapter("upseller")` 等工厂当前只创建 PendingAdapter。UpSeller 两个官方公开读取方法抛出 `ConnectorNotConfigured`，原因包括协议图片未核验和未授权；其他未实现/未确认业务方法抛出 `UnsupportedCapability`。任何方法都不会返回假成功或空列表掩盖未接入。未知供应商拒绝创建，未知能力拒绝执行。

```python
from app.integrations import ConnectorNotConfigured, create_adapter

adapter = create_adapter("upseller")
try:
    adapter.list_warehouses()
except ConnectorNotConfigured:
    # UI 应显示待接入，不能把此异常转换为成功或空仓库数据。
    pass
```

没有可启用的第三方 HTTP 传输、回调接收路由或密钥配置项。设置环境变量不会让占位适配器变为真实对接。

## UpSeller 只读实现为什么仍被阻塞

[官方中文指南](https://www.upseller.com/zh-CN/help-doc-article-3403)已核实 POST/JSON、两个精确 URL、请求头传递 API 密钥、适用套餐及主账号要求。API 专业版/企业版/企业 Plus 每接口每分钟分别 100/200/500 次；MCP 的额度独立，不能代替 API 限额。

然而鉴权头字段名、通用响应码、仓库和 SKU 的响应映射、HTTP 库存请求参数以图片发布。本次网页读取可取得图片链接但不能取得内容，官方指向的飞书详细文档也读取失败。只有地址不足以安全实现协议，因此未发起无凭证试探、未猜测 Authorization/User ID 头、未猜库存字段。葡语指南较旧（页面 2026-09-11），同样使用图片，不能填补此缺口。

后续应通过获授权的官方文档或可读取的公开图片核对所有头/字段/错误码；固定 HTTPS 域名 `openapi.upseller.com` 和上述两个路径，不允许用户自定义 URL 或跟随重定向携带密钥；设置连接/读取超时、响应大小上限、错误脱敏和明确退避。只读 POST 可以按已核验协议处理重试，但业务写入结果未知时必须先查询恢复。

## 适配器落地次序

1. 冻结每货主/店铺连接与权限范围，验证主账号、套餐、scopes、服务商准入各自证据，避免混用 A/B/C 路径。
2. 保存公开官方协议版本和内部字段映射；未知 SKU 入待映射队列，禁止依据文本相似度自动合并货主 SKU。
3. 以规范模型转换数据；库存字段必须注明物理在库/可售/占用的供应商原义，再决定对账口径。
4. 先实现只读和官方协议契约测试，再经过授权测试环境验证；真实证据须记录供应商、脱敏账户范围、接口、环境、时间及返回结果。
5. 在正式启用订单推送/发货回传之前，实现持久化 inbox/outbox、唯一事件键、验签/防重放、队列重试/死信、游标/水位、乱序检测、权限与审计。当前没有这些第三方同步能力。
6. 外部回调先验证协议与授权，原子持久化事件后再确认；不接受所有任意 JSON 都返回 200 的端点。
7. 通过重复事件、超时、限流、token 失效、未知结果恢复、跨货主隔离、状态回退和库存对账测试后，再申请生产启用。

## 当前验证命令

在仓库根目录运行 `python -m unittest tests.test_integrations -v`。该测试证明待接入状态可信，不证明任何厂商 API 已通过沙箱或真实账户验收。
