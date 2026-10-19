# HANDOFF — 0.5跨仓与本地试用

持久分支`codex/wms-warehouse-movements`，草稿PR：https://github.com/fangmu0713-cyber/wms/pull/1 。本轮从远程/本地8238f17的0.4续接；准确最新SHA见git log和远程。不要仅检出main初始README或旧包重新开发。用户要进一步完善后晚些本地试用，已准备隔离入口，不立即部署公网。

## 当前交付与守恒

0.5.0包含已有履约/波次/同仓搬运/盲盘和005跨仓调拨。001–005发布后不改，下一迁移006。

调拨单单货主/单SKU/单源库位。主管两仓授权建单，来源move_reserved+qty，不能与订单/其他搬运/盘点锁抢同一数量。源仓picker/staff整单扫码发出，源on_hand/hold−qty、transfer_transit+qty。目标仓receiver/staff凭唯一receipt_reference分批合格接收，可不同库位，目标on_hand+qty、transfer_transit−qty。只需各自作业端仓授权，不能因此读另一仓余额。只有admin可根据确认丢失依据/原因以全部剩余量结案，transfer_lost+qty，不伪造目标库存。

TRANSFER_PLANNED→DISPATCHED→PART_RECEIVED→COMPLETED，或途中CLOSED_WITH_LOSS；仅发出前可CANCELLED。不可改删transfer_events；每单/RECEIVE/reference唯一。重试原body/path/key，缓存重放也重查当前角色/端仓授权，不能换人/键重复登记同批。找回/退回/残次接收/丢失撤销/赔付待后续，不要直接取消已发出单。

原in_transit仅同仓，跨仓transfer_in_transit按源仓归集一次；physical_total=库位on_hand+两类在途+待检/合格未上架/残次，确认丢失不在实物内。内部核对读取可见调拨两端流水，不给调用者未授权仓账本。move_reserved核对包含同仓待搬+跨仓待发；恢复检查所有事件和锁，不能只迁目标余额。

盘点每轮锁测量并记当前账面/ledger rowid；提交后放测量锁，短少按最大值另锁count_reserved。不同账号相同差额才接受非零差异；admin批准增减当前余额的delta，不覆盖历史总数。count_only仅可读取/提交自身盲盘任务，API/snapshot/幂等响应不给账面/截点/差额/他人读数。跨仓收货仍遵守目标测量锁，源测量不阻断其他库位接收；丢失结案账本锚源库存，须等待源测量结束。不同账号不验证现实不同人员。

## 本地试用与复验

安装与逐步演练见docs/LOCAL_TRIAL.md。执行`python -m scripts.local_trial`只在127.0.0.1:8000运行，显式建立独立var/local-trial示例库和五个岗位，原业务WMS_DB_PATH不读取，不覆盖未知目录。凭证只存本机0600 accounts.token，不打印/截图/进源码包；Windows另管ACL。重启保留数据，另用--directory开始一轮；不会静默重发过期凭证。

```bash
python -m pip install -r requirements.lock
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
python -m tests.browser_transfers -v
WMS_COUNT_EVIDENCE_DIR=evidence/stage5/counts python -m tests.browser_counts -v
WMS_WAREHOUSE_EVIDENCE_DIR=evidence/stage5/warehouse python -m tests.browser_warehouse -v
WMS_EVIDENCE_DIR=evidence/stage5/legacy python -m tests.browser_flow -v
```

云环境本机socket需工具network.enabled=true。86项后端+4套真实浏览器通过，测试使用独立临时SQLite/示例账号，无新依赖，无ERP密钥。原64项先作基线再继续。包括19项调拨、3项本地入口、权限撤回后缓存防泄露、超收/末件/收货与丢失并发、失败回滚、旧004真实流水增量升级、恢复后继续收货和元数据破坏拒绝。

典型浏览器：100，调出20（源80/在途20），目标收7+8，再确认剩余5丢失，最后源80/目标15/在途0/历史丢失5；实际收货与丢失结案响应丢失后原键只过一次。0JS错误、中葡桌面/手机、空localStorage/sessionStorage。截图/日志在stage5，历史stage3/4证据保留；旧测试会写根evidence/recovery.json，本轮归档到stage5再恢复根历史文件。

## 接下来

1. 用户晚些本地试用后收集岗位/页面/实际步骤/预期与实得/截图（不含令牌），优先改真实反馈，不强迫先完成所有高级模块。
2. 实体回位/作业换人、调拨退回/找回/残次区域、多SKU调拨和部分发出。多包裹/部分销售出库先扩行模型，不破坏旧整单链。
3. 完整OMS/ASN/导入导出/异常/私有附件/正式计费；自动补货/全仓多SKU盘点计划/箱托组合装尚未实现。
4. 真实ERP须正式账号/接口协议/权限，从只读和沙箱开始；五家目前disabled/pending，没有HTTP业务对接。
5. 正式生产前需认证加强、CLI审计、分页、负载/监控、实机及库存切换验收；持久离线队列也未实现。

## 运维边界

0.5镜像标签更新，本轮未构建验收容器/长期压测；旧0.1容器/容量探针仅历史证据。Windows/macOS步骤未在这些实机上验收。无生产服务器/域名授权或公网网址，未动VPS/SSH/安全组/外部运行服务。只更新原草稿PR，不合并或部署。

先备份再迁移005，无down。旧0.3不执行count_only及盘点锁，旧0.4也不理解调拨在途/待发锁，禁止直接降级继续写。异常停写、保留全部新流水、隔离备份和人工对账/前向修复，不删除元数据或覆盖库存。源码包只含受控源码/证据/Git可用历史，不含业务库、令牌或wheels。
