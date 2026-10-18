# HANDOFF — 库内补货/移位续接

仓库的交付分支为codex/wms-warehouse-movements，保留阶段1a2681d4历史。本轮云环境已重置；原上传zip可恢复阶段1，上轮a0a955d和生成包不在当前环境，波次按本聊天代码重建并重新验证。不要声称旧a0对象已找回。

## 当前实现

0.3.0 = 阶段1真实履约链 + 002波次/独立拣货任务 + 003同仓人工补货/移位。001未改；002保持上轮表/字段/约束契约。库存口径、状态和API见CONTRACT，最新证据见evidence/stage3与VALIDATION。

补货/移位：建任务锁move_reserved，订单预占必须扣除此锁定；领取后来源扫描整任务搬出，源库位减少/任务进入IN_TRANSIT，再目标扫描整任务接收，目标库位增加。同仓实物总量包含搬运中。搬出前可取消；释放领取保留待搬锁，只有取消才释放数量。搬出后不允许直接取消、换人或部分接收，未确认目标实物时不能假装到位。

所有写入BEGIN IMMEDIATE，投影/账本/任务/幂等/审计同事务。新任务角色：admin/staff创建取消；admin/staff/picker/receiver执行本人领取任务。货主库存汇总含自身搬运中数量，但仓内任务/领取人数据不可读。波次仍限admin/staff/picker。

## 启动与测试

```bash
python -m pip install -r requirements.lock
python -m pip install -r requirements-test.txt
python -m app.cli migrate
python -m app.cli bootstrap --tenant '测试公司' --name '管理员'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
python -m unittest discover -s tests -v
python -m tests.browser_warehouse -v
WMS_EVIDENCE_DIR=evidence/stage3/legacy python -m tests.browser_flow -v
```

测试使用隔离临时库。当前云环境TestClient/Chromium需工具network.enabled=true支持本机socket，否则可挂起。无新增依赖，不需ERP凭证。令牌只写受保护文件，不发聊天、不进包。

44项后端测试和2项浏览器流程已验收，最终结果以VALIDATION为准。浏览器实测同仓40件搬运、错误扫描、接收已落库但丢响应后原键重试、取消未搬出任务、货主权限、中葡桌面/手机、波次两单发5件后95和核对通过。

0.3镜像标签已更新，但本轮未构建或运行容器；0.1容器/负载证据是历史记录。升级先备份并在恢复副本演练迁移。003无down；存在搬运锁/搬运中时不可直接回退不理解此口径的旧代码。停写后保留所有新流水，前向修复或经人工对账恢复，不能丢弃真实物理事件。

## 准确下一步

1. 先读AGENTS、PROJECT_STATUS、TASK_BOARD、DECISIONS、CONTRACT和总任务书，核对git和证据。后续迁移从004起，不改001/002/003。
2. P2-02：盘点范围和截点、盲盘/复盘、审批与差异过账。盘点期间合法收发/搬运必须被截点规则处理，不能直接覆盖余额。
3. 跨仓调拨须独立发出/在途/部分接收/丢损模型，不能把同仓搬运当作跨仓已经完成。
4. 搬运异常与实体回位、已拣任务换人、汇总后分拣、多包裹/部分履约要先扩状态/逐行过账，严禁双扣。自动补货需真实可配置阈值，当前仅人工发起任务。
5. P2-03完整OMS/ASN/导入预检/异常/私有附件/导出；P4正式报价和计费需要用户业务规则。P3仅拿到正式协议/权限才实现真实ERP，先只读再沙箱。
6. P5加强认证、审计、分页、长期负载、监控、实机和库存切换；只在获授权新服务器部署。

## 交付与外部限制

本轮准备独立GitHub分支/草稿PR作持久审阅入口，实际推送/PR结果以最终交付和链接记录为准；未合并主分支、未部署生产。若远程不可用，保留源码包/bundle并明确未推送，不能以本地commit冒称远程已保存。

环境会重置，不依赖临时路径或旧聊天进程存活。源码包只包含受控源码、测试证据与可用Git历史，不含运行库、令牌、依赖wheels。ERP、服务器/域名、生产部署和设备均仍未授权/验收，不改任何代理VPS、SSH、安全组或外部运行服务。
