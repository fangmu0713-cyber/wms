# HANDOFF — 换号/中断续接入口

更新：2026-10-16（Asia/Shanghai）。仓库 `/workspace/wms`，分支 `work`，初始提交 `d9c2d5c`。完整任务书已保存、读取和执行至首个内部闭环。

## 下一个账号直接执行

> 继续当前仓库的海外仓WMS项目。先读 AGENTS.md、docs/PROJECT_STATUS.md、TASK_BOARD.md、DECISIONS.md、CONTRACT.md、HANDOFF.md 和任务书；核对 git log/status 与 evidence/VALIDATION.md。保留现有单体和业务链，不重新建项目。先回归已有测试，再按 TASK_BOARD 从 P2-02 等内部未完成项推进；ERP没有真实权限，不能宣称已对接。总控统一迁移，子任务不要并发改同一迁移。不要修改代理VPS/SSH/安全组/运行服务。

跨账号必须保证访问同一仓库或代码快照；旧聊天、子代理、临时环境、容器和凭证不保证迁移。无需旧代理存活。凭证不写交接记录，换账号重新初始化独立开发库，不要复用生产秘密。

## 已交付

- 总控 app/core 与 001 迁移：真实SQLite事务库、租户/货主/授权仓、8基础角色、凭证摘要/过期撤销、幂等/审计/只追加账本。
- 单SKU收货/QC/上架；多SKU订单/多库位分配→整单预占→拣货→复核→单包裹打包→交接→核对。质量分区与物理总量，预占/拣/包不减实物，交接一次扣。未拣取消、关联退货、BRL手工费用防重。
- 原创中葡 WMS/OMS/PDA 页面；真实API、token仅内存；未知响应锁定原提交/同幂等键重试。
- 5家ERP规范适配契约与公开事实/权限矩阵，全待接入，无HTTP业务连接；官方参考S01–S12重新核查。
- 容器/compose/离线构建、配置、OpenAPI、启动/权限/备份恢复/HTTPS/日志轮转/告警配置/回退/设备验收说明。

## 最后验证

详见 evidence/VALIDATION.md。21 API/ERP/恢复tests通过（2.645s）；浏览器业务链+响应丢失重试+BRL+中葡/手机通过；100单8并发小探针100成功0错误；容器构建、UID10001/无外网完整HTTP链、重启持久化通过；独立库恢复97且snapshot相等。证据JSON/截图/命令输出已入仓库，不含凭证。

```bash
python -m pip install -r requirements.lock
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
python -m tests.browser_flow -v
python -m tests.load_probe --orders 100 --concurrency 8
```

本环境测试命令需工具 network.enabled=true 支持本机socket，否则TestClient/Chromium可挂起。Docker默认配置目录只读，使用DOCKER_CONFIG=/tmp/wms-docker-config，不改HOME。Docker RUN pip DNS受限，先在可联网环境下载 `python -m pip download --only-binary=:all: --dest wheelhouse -r requirements.lock`，再 `docker build --build-arg WMS_OFFLINE=1 -t overseas-wms:0.1.0 .`，接 `python -m scripts.container_smoke`。wheels忽略、不依赖它在换号后存在。

## 准确续接顺序

1. 保持已通过的内部链，读任务板，新增迁移用002起；总控单一负责顺序，不改已经发布的001。
2. P2-02 波次与独立拣货任务优先；之后补货/移位、盘点截点、多仓在途调拨；加守恒/失败/权限/重试测试。
3. P2-05 实体回位撤销、多包裹和部分发货需先扩展包裹/行过账，不能按整单先扣再按包裹重复扣。
4. P2-03 完整OMS、ASN/部分收货/导入预检/异常/私有附件/导出；避免前端越权隐藏充当隔离。
5. 有正式协议/账号时才做P3真实ERP；先只读后沙箱，持久inbox/outbox/映射/验签/游标/退避/死信再启用。UpSeller读库存不等于服务商履约。
6. P4报价版本/仓租快照/账单/收款及高级业务；不硬编码用户税号或未经确认的收费/税务规则。
7. P5生产前补强身份MFA/SSO/审批/管理审计、分页/长期负载/故障监控和初始库存切换；仅获授权新服务器部署。

## 外部阻塞及限制

全部ERP无账号/商务/正式接口权限，部分头/响应图与动态文档不可读取；详情见 ERP_CAPABILITIES。无生产服务器/域名授权，无上线地址。实物PDA/相机/打印机/秤待验收。当前单节点SQLite/整单单包裹/无离线持久队列；库存快照无分页。密码/MFA/在线换密与CLI管理完整审计未完成。未改任何代理VPS、SSH、安全组或其他外部运行服务。

代码已准备为本地 Git 提交；导出的 `/workspace/wms-stage1.bundle` 是 Git 源码/证据快照，可复制到新环境后 `git clone /path/wms-stage1.bundle wms`。bundle 不含依赖wheels、运行数据库和凭证；首次初始化测试环境参考 README。未推送远程仓库，跨账号务必保留bundle或同步获授权代码仓库。
