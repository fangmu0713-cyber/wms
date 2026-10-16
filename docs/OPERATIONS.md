# 启动、部署和操作手册

本阶段仅内部闭环，版本 0.1.0。单节点 SQLite 本地持久卷，禁止 NFS 共享库或多个应用副本独立扩容。尚未通过生产负载/安全验收。数据库是唯一库存真相；无 Redis、无外部服务依赖。无 ERP worker，本阶段没有对外待发送承诺；inbox/outbox 与持久 worker 将随正式适配器实现。

## 本地启动

```bash
python -m pip install -r requirements.lock
python -m app.cli migrate
python -m app.cli bootstrap --tenant '测试公司' --name '管理员'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

浏览器访问本机 `http://127.0.0.1:8000`，在本机受控工具中查看 `var/admin.token` 的 token 字段，粘贴到登录框。不要发到聊天或截图。文件模式 0600，不得提交 git。浏览器仅内存保存凭证，刷新/退出后清空。当前是 API 凭证登录，30 天过期；密码、MFA、企业 SSO、自助重置未实现，正式上线前需要加强认证。

先建货主、仓库、库位、SKU、店铺；收货 100 → 质检合格 100 → 上架 → 创建订单 3 → 预占 → 在 PDA 扫正确商品条码/来源库位 3 → 复核 3 → 打包 → 输入承运商与运单、确认实物交接 → 出库。库存应从 100/可用100 变为预占阶段 100/可用97，交接后 97/可用97。这里只登记已有运单，不购买物流或生成假面单。

一次扫码提交的重试使用同一幂等键；同码非序列化商品逐件扫描无法仅凭条码判断是否同一实物，系统用任务余量防超量，实机操作仍需一件一扫。页面不提供离线成功；未知响应时保持原键重试，不新建业务。

## 账号与范围

```bash
python -m app.cli user --tenant-id TENANT_ID --name '收货员' --role receiver --warehouse-id WAREHOUSE_ID --output var/receiver.token
python -m app.cli user --tenant-id TENANT_ID --name '货主' --role owner --owner-id OWNER_ID --warehouse-id WAREHOUSE_ID --output var/owner.token
python -m app.cli revoke --user-id USER_ID
```

admin 管理本租户所有仓；staff 有授予仓内运营权；receiver 收货/质检/上架；picker 拣货；packer 复核/打包/出库；finance 登记出库费用；owner 管理自身商品/店铺/订单申请/退货申请；owner_readonly 只读。非 admin 必须逐仓授权，默认无仓权限。货主创建 owner_id 即便由客户端传入也必须与认证范围匹配。客服、主管细分权限、审批与 MFA 是后续项。换发凭证：创建同范围新账号后撤销旧账号；暂不提供在线自助换密。

## 容器交付

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose exec wms python -m app.cli bootstrap --tenant '测试公司' --name '管理员' --output /data/admin.token
```

仅绑定主机 loopback 8000；生产 HTTPS 由获授权新环境中的反向代理终结，TLS 1.2+、请求体上限 256KiB、认证限流。参考 `deploy/nginx.conf.example`，证书和域名由部署管理员提供。容器非 root、只读根、drop ALL capabilities、无额外公开管理/数据库端口。不要复制或改动现有代理 VPS/SSH/安全组。不得将此开发端口视为生产上线地址。

数据库迁移按编号启动时依次执行，迁移失败不启动服务。正式升级前先停写和备份，再由一个维护实例执行迁移，禁止同时部署多副本执行迁移。配置/凭证通过受控卷和环境注入；目前无第三方密钥字段，不要把 ERP 凭证加入映像。容器 umask 077；宿主本地运行也应设置 `umask 077`。

## 备份与恢复

```bash
python -m app.cli backup --output /tmp/wms-backup.sqlite3
python -m scripts.restore_check /tmp/wms-backup.sqlite3 /tmp/wms-restore.sqlite3
WMS_DB_PATH=/tmp/wms-restore.sqlite3 uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log
```

使用 SQLite online backup API 取得一致快照，不能直接 cp 活跃 WAL 库。恢复目标必须是不存在的新文件；检查 integrity、外键、余额/流水，恢复后用测试账号确认订单/库存/权限。备份含凭证摘要、客户业务资料，需要加密到私有备份库，控制访问和保留策略。当前无附件功能，附件备份不适用。

建议运维安排每日全量、保留 7 日/每周保留 4 周；这些尚未在外部环境排程，实际 RPO 取决于最后成功备份，不能据此承诺 24h SLA。演练耗时和样本见 evidence/VALIDATION.md，不能外推为生产 RTO。

## 日志、告警与升级回退

- API 日志只记状态和耗时，不记 token、请求体、用户地址或完整 URL；uvicorn 禁用 access log。Compose 日志轮转 10MiB×3。按环境为 wms logger 配置 INFO 收集。
- `/health` DB readiness 供容器健康检查；`/api/snapshot.reconciliation` 供授权操作员查库存余额/流水/预占差异。生产监控应对连续 health 失败、5xx/429、磁盘空间、备份失败、对账 issues 建立告警；外部通知未配置，不能声称已发送告警。
- 升级前记录镜像标签/迁移版本，停写、备份、在恢复副本跑迁移和回归，再启动新版本。仅兼容 schema 时直接回退旧镜像；不兼容时先停写并保留新产生的流水，经人工对账/前向修复后切换，不能丢弃真实交接事件。
- 当前只有 001 初始建库迁移，无破坏性 down 脚本；开发试验可丢弃独立测试库，正式环境绝不自动删表。容器回退不等于数据回退。

## 设备与人工验收

PDA/手机 390px 页面和键盘扫描输入有自动化浏览器验收；条码枪、相机、蓝牙/网络打印机、电子秤均待实机。步骤：选测试仓/货主，扫描错误条码被拒→正确条码计入→连续提交同幂等键不重复→断网提示未知/失败不报成功→恢复网络以原请求重试→数据库和流水核对。打印/相机/秤当前未实现，不把键盘输入测试称为设备对接。

容器离线构建：在同 Python/系统架构的可联网环境运行 `python -m pip download --only-binary=:all: --dest wheelhouse -r requirements.lock`，再执行 `docker compose build --build-arg WMS_OFFLINE=1`。目录中的 wheels 被 gitignore 排除；跨机使用时重新下载匹配架构 wheel。容器备份可用 `docker compose exec wms python -m app.cli backup --output /data/backup.sqlite3`，然后 `docker compose cp wms:/data/backup.sqlite3 ./var/backup.sqlite3`；在受控独立本机以 restore_check 演练。备份文件不要公开或提交版本库。
