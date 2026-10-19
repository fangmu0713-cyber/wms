# HANDOFF — 0.4盘点续接

持久分支`codex/wms-warehouse-movements`，草稿PR：https://github.com/fangmu0713-cyber/wms/pull/1 。本轮从63fb8df同步继续；准确最新SHA见git log及远程。不要仅检出main初始README或旧源码包重新开发。

## 当前交付

0.4.0 = 真实履约 + 002波次/独立拣货 + 003同仓人工补货/移位 + 004截点盘点/盲盘/独立复盘/差异审批。001/002/003未改，下一迁移005。

盘点为单货主/单仓/单SKU明确库位集合。测量开始要求无订单/已拣/搬运占用，同事务记录当前on_hand与ledger rowid，持久锁定所选库存；其他库存可继续。读数提交释放测量锁，短少数量另锁count_reserved。最近两次不同账号的差额一致才接受非零差异；复盘重新取当前截点，不能直接比较不同时间的总读数。审批只增减差额，不覆盖当前余额。

专用count_only凭证只能是CLI明确签发的picker，旧用户默认0。认证、GET、snapshot和幂等响应均执行限制，不给账面/截点/差额或他人读数。admin/staff建单、分配复盘、取消；只有admin可审批，需原因。服务器只证明不同账号，现实人员独立性由现场管理保证。

测量锁期间inventory.count_locked=true/available=0；否则available=on_hand−reserved−move_reserved−count_reserved。所有库存写经service.stock检查测量锁，COUNT_HOLD/CANCEL仅内部可针对本行放行。取消释放锁并保留证据，不解决实物差异。读数和截点不能改删。

## 启动与可复验命令

```bash
python -m pip install -r requirements.lock
python -m pip install -r requirements-test.txt
python -m app.cli migrate
python -m app.cli bootstrap --tenant '测试公司' --name '管理员'
python -m app.cli user --tenant-id TENANT_ID --name '初盘员' --role picker --count-only --warehouse-id WAREHOUSE_ID --output var/counter-a.token
python -m app.cli user --tenant-id TENANT_ID --name '复盘员' --role picker --count-only --warehouse-id WAREHOUSE_ID --output var/counter-b.token
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
python -m unittest discover -s tests -v
python -m tests.browser_counts -v
WMS_WAREHOUSE_EVIDENCE_DIR=evidence/stage4/warehouse python -m tests.browser_warehouse -v
WMS_EVIDENCE_DIR=evidence/stage4/legacy python -m tests.browser_flow -v
```

签发凭证只写0600文件，不能发聊天/截图/进包。当前云环境TestClient/Chromium需要工具network.enabled=true支持本机socket。测试均独立临时库，命令无需ERP凭证。无新依赖。

64项后端+3套真实浏览器通过；结果/截图见evidence/stage4和VALIDATION。覆盖盘点期间出库/上架/搬运、并发预占/审批、盲盘API与缓存响应隔离、独立复盘、差异锁防超占、多行失败回滚、003升级、持久锁/读数/短少锁的独立恢复和错误元数据拒绝。典型100→实盘98→发3→复盘95（账97）→再发5→审批差额−2→90，核对通过。

## 继续顺序

1. 先读AGENTS/PROJECT_STATUS/TASK_BOARD/DECISIONS/CONTRACT及总任务书，核对git、远程和证据；从005迁移继续，不改001–004。
2. 做跨仓调拨的发出/在途/部分接收/丢损，先明确同一货主与两仓授权、库存口径、唯一事件和守恒。不能把同仓IN_TRANSIT当作跨仓已完成。
3. 作业异常/实体回位/换人交接，多包裹与部分履约先扩行过账；随后完整OMS/ASN/异常/私有附件/导出、报价/账单等。
4. 全仓多SKU自动盘点、未知商品认领、货主盘点门户、自动补货、部分搬运/损耗/回位等未实现，当前不能计入完成。
5. 真实ERP需正式协议/账号/接口权限，先只读再沙箱；P5仍需认证加强、CLI管理审计、分页、长期负载、监控、实机和库存切换。

## 运维限制

0.4镜像标签已更新，本轮未重新构建容器或生产部署；旧0.1容器/探针为历史证据。缺004健康与认证503。新旧版本安全边界不同：0.3不认识count_only，会把专用盘点账号当普通picker；也不检查测量锁/短少锁，禁止直接回退。停写并保留所有新流水，撤销专用凭证、人工对账或前向修复，无破坏性down。

备份恢复工具检查所有库存锁的ledger投影、count_lines短少锁和ACTIVE任务测量锁，不能只恢复inventory而丢掉盘点元数据。未知响应保留原请求/键；刷新页面丢失客户端内存待确认队列，不能声称持久离线。

无ERP真实授权、生产服务器/域名授权、实物设备验收或上线地址；未操作VPS/SSH/安全组/外部运行服务。继续更新原草稿PR，未获指示不合并或部署。源码包只含受控源码、证据和可用Git历史，不含运行数据库、凭证或依赖wheels。
