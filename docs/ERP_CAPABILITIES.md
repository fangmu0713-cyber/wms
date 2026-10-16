# ERP 能力与权限证据

核查日：2026-10-16（Asia/Shanghai）。本记录来自公开官方页面读取，不包含任何真实企业账户授权、合同或 API 调用结果。所有 ERP 当前均为 **待接入**；`app/integrations.py:get_registry()` 提供相同边界的可序列化能力注册表。

## 三条接入路径

| 路径 | 含义 | 当前结果 |
|---|---|---|
| A 卖家自用 API | 经卖家企业授权查询/操作其账户 | 尚无账户、token、AppID 或 OAuth 授权；未做真实验证 |
| B 海外仓服务商接入 | 卖家在 ERP 中选择并授权本仓推单、履约 | 没有服务商合同、准入或发布审批；未接通 |
| C 本系统开放 API | 调用本系统的认证 API | 内部 API 的实现与测试由核心项目交付；不意味着 A 或 B 已接通 |

## 逐家逐接口

| ERP/接口 | 官方依据 | 官方公开事实与账户条件 | 本期实现/实际测试 | 状态/外部阻塞 |
|---|---|---|---|---|
| UpSeller 仓库列表 `getWarehouseList/v1` | [S05](https://www.upseller.com/zh-CN/help-doc-article-3403)，页面更新 2026-09-28 | `POST https://openapi.upseller.com/erp/inventory/getWarehouseList/v1`；`warehouseType` 可选 ALL/SELF_OPERATED/THIRD_PARTY；专业版及以上或组合套餐，主账号生成凭证 | 注册官方地址、规范仓库模型与 fail-closed 方法；**未实现 HTTP 读取，未真实调用** | 待协议详情及主账号授权；鉴权头、错误与响应表格为图片，本环境不能读取；不能猜测 |
| UpSeller SKU 库存 `pageWarehouseSku/v1` | [S05](https://www.upseller.com/zh-CN/help-doc-article-3403) | `POST https://openapi.upseller.com/erp/inventory/pageWarehouseSku/v1`；分页库存查询；公开 MCP 参数含 warehouseIdList、skuList、pageNo、pageSize、updateTime，但不能据此假定 HTTP 字段完全相同 | 注册官方地址、规范库存观测模型；**未实现 HTTP 读取，未真实调用** | 同上；HTTP 分页字段和响应库存口径仍须图片/详细协议核验 |
| UpSeller 订单接收、取消、面单、发货回传、库存写入、入库、退货 | [S06](https://www.upseller.com/zh-CN/help-doc-article-3365)，页面更新 2026-08-28 | 海外仓按服务商逐家单独对接，自研 WMS 可作为服务商系统；收费定制接入 | 所有写入/履约方法明确 UnsupportedCapability；无假接口或模拟成功 | 待服务商商务接入、合同和专用技术协议；Open API 只读能力不能替代此路径 |
| 店小秘 仓库授权、渠道映射、面单推送 | [S07](https://help.dianxiaomi.com/article/freightForwarderAuthorization/3075) | 本次该入口返回读取错误；任务书描述不能充当本次已读取证据 | 注册候选及明确未实现能力；未发真实请求 | 文档待确认；待官方准入协议、费用、接口、账号和联调发布规则 |
| 领星 企业接入鉴权 | [S08](https://apidoc.lingxing.com/new/guides/new-instructions/) | AppID/AppSecret 与公网 IP 白名单均需配置；公共参数 access_token/app_key/timestamp/sign；按 appId+接口 URL 限流；错误码 3001008 | 规范契约预留；业务方法未实现、未真实测试 | 待企业凭证、获批接口、稳定出口 IP；不会将临时开发出口视为生产白名单 |
| 领星 商品/库存/多平台订单/履约 | [S08](https://apidoc.lingxing.com/new/guides/new-instructions/) | 分类目录存在不代表本项目巴西渠道完整可写或已授权 | 无业务接口映射与网络调用 | 逐接口、渠道、字段及账号范围待核验 |
| 马帮 企业鉴权及订单/库存/履约 | [S09](https://help.mabangerp.com/nested/details?id=3034&resource_id=1)，[历史官方索引](https://help.mabangerp.com/kbzx/nested/details?id=3034&resource_id=1) | 两个页面直接读取均报错；搜索索引显示 2024-04-25 指引要求企业 AppKey/密钥和 API 权限，历史文档非当前有效协议证明 | 注册候选；未实现、未真实测试；不采用索引中的示例版本直接调用 | 待当前有效协议、接口版本、权限、限流与凭证 |
| Bling OAuth、商品/订单/库存/物流等候选 | [S10](https://developer.bling.com.br/bling-api)、[S11](https://developer.bling.com.br/referencia)、[应用](https://developer.bling.com.br/aplicativos)、[审核](https://developer.bling.com.br/homologacao)、[限流](https://developer.bling.com.br/limites) | REST/JSON、OAuth 2.0 Bearer；私有应用用于自有账户，公开应用需审核，未审核最多 10 个授权用户；每账户总计 3 次/秒、120000 次/日；429 需退避 | 规范契约预留；S11 动态资源列表未展开；未实现 OAuth 或业务 HTTP 调用 | 待应用创建/授权、实际 scopes、账户及公开审核；逐接口分页、字段和库存副作用待确认 |

## 运行证据和权限证据

- 有效企业账号/套餐：全部未提供，不能核实用户实际具备的权限。
- 真实第三方 API 调用数：0；真实订单推送、面单接收、库存回写、发货回传：0。
- 本地自动化：`python -m unittest tests.test_integrations -v` 验证 JSON 注册表、所有供应商禁用状态、失败边界和无秘密回显；不属于“模拟测试通过”或 ERP 验收。
- UpSeller 详情图片和飞书链接通过浏览工具读取失败；容器对公开页面的额外网络只读请求被出网代理拒绝（403）。没有绕过限制。
- 没有收集、保存或输出客户密钥。注册表是全局公开文档元数据，绝不包含跨货主凭证或订单。

## 后续启用条件

先获取完整官方协议和账户范围，再实现独立适配器、字段/状态映射、超时/限流/重试和错误分类。持久化 inbox/outbox、每货主连接配置、密钥安全存储、验签、防重放、增量游标、人工补偿及每日对账均是后续范围，**本期未实现**。签名失败或不支持的协议不得确认业务成功。

库存读取仅作为对账观测，不能直接覆盖 WMS 的实际库存。WMS 对收货、质检、库位、预占、实际出库负责；ERP 只对授权销售订单与平台状态负责。发货写回前必须核验 ERP 是否再次扣库存，避免重复扣减。
