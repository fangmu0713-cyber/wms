# Overseas WMS / OMS

可独立部署的海外仓系统，当前0.5.0交付阶段1真实内部履约闭环、波次/独立拣货任务、同仓人工补货/移位、盲盘/独立复盘/差异审批与跨仓调拨。中文/巴西葡语 WMS、货主 OMS、移动 PDA 页面使用同一认证后端和持久数据库。**未正式接通任何 ERP，未部署生产。**

实际流程：货主/仓库/SKU → 实际收货 → 质检 → 上架 → 手工或本系统 API 订单 → 预占 → 扫码拣货/复核 → 打包 → 交接出库 → 库存流水/余额核对。附关联退货和 BRL 手工费用防重。

```bash
python -m pip install -r requirements.lock
python -m app.cli migrate
python -m app.cli bootstrap --tenant '测试公司' --name '管理员'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

本机页面 `http://127.0.0.1:8000`。首次凭证保存在受保护的 `var/admin.token`，不输出到日志，使用后按操作规范管理。默认无客户/库存/订单种子，无预设业务数字。开发建议 `umask 077`。

```bash
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
python -m tests.browser_flow -v
python -m tests.browser_warehouse -v
python -m tests.browser_counts -v
python -m tests.browser_transfers -v
python -m tests.load_probe
```

真实 SQLite 临时测试库与生产隔离；浏览器使用系统 Chromium 或已安装 Playwright 浏览器。受限环境须允许本机 socket，不需第三方 ERP 凭证。

容器：`docker compose build && docker compose up -d`。若构建环境无 DNS，先在允许联网的同架构环境执行 `python -m pip download --only-binary=:all: --dest wheelhouse -r requirements.lock`，然后 `docker compose build --build-arg WMS_OFFLINE=1`。wheels 不入版本库，无第三方密钥。首次启动自动迁移，管理员需手工初始化，详见操作手册。

- [准确进度](docs/PROJECT_STATUS.md)、[任务看板](docs/TASK_BOARD.md)、[换号/中断续接](docs/HANDOFF.md)
- [启动部署/权限/备份/回退/设备](docs/OPERATIONS.md)、[接口契约](docs/CONTRACT.md)、[API 使用](docs/API.md)
- [ERP 权限与能力](docs/ERP_CAPABILITIES.md)、[官方参考矩阵](docs/reference-matrix.md)
- [验收证据](evidence/VALIDATION.md)、[完整任务书](docs/Codex_Overseas_WMS_Master_Task.md)

单节点模块化单体：FastAPI + SQLite WAL，事务更新余额/只追加账本/幂等记录/审计。高吞吐多节点、自动补货、正式账单、物流面单、设备、持久同步队列等不在本次已完成范围；按任务板续接，不能用空页面计入完成。

库内作业：创建补货/移位任务锁定可用库存 → 领取 → 来源扫码搬出 → 库内搬运中 → 目标扫码到位。待搬和搬运中均不可再次预占；搬运中仍属于本仓保管实物。当前仅同仓、整任务数量、人工发起；不含自动补货、部分接收、损耗处理或跨仓调拨。波次完成仅代表拣货完成，仍需逐单复核/打包/交接。

本轮云环境重置后恢复了阶段1并重建上轮波次，重新运行验收；具体来源、限制和后续在HANDOFF。不要只依赖临时下载路径保存项目，应保留源码包或使用已确认推送的分支。

盘点：主管选择单SKU和库位范围 → 专用账号盲盘 → 非零差额由另一账号复盘 → 管理员审批差额。测量期间库存暂停，提交后允许合法作业继续；短少单独锁定，审批不会覆盖新出库。专用账号签发与现场程序见OPERATIONS，完整权限与截点契约见CONTRACT。

本地试用：安装requirements.lock后执行`python -m scripts.local_trial`，浏览器打开http://127.0.0.1:8000。仅此显式入口生成独立示例库和五个本机保护凭证，不覆盖已有业务库。Windows/macOS/Linux步骤、账号切换与逐步验收见[本地试用指南](docs/LOCAL_TRIAL.md)。

跨仓调拨：主管建单锁定源仓库存 → 源仓实际发出转在途 → 目标仓按唯一签收批次分批确认合格到货。源仓发出/目标仓接收按各自仓权限执行；管理员可填写依据将全部剩余在途确认为丢失并结案。两类在途分开核算；已确认丢失不再计入保管实物，未查明异常继续在途。迁移005；不可直接降级忽略调拨锁/在途的旧代码。

Mac专用启动包：完整包包含两种芯片的离线依赖，安装Python3.12后双击根目录“启动仓储.command”，自动打开本地页面并复制管理员令牌；岗位切换使用“复制登录凭证.command”。数据位于用户Library/Application Support/AtlasWMS/Trial-0.5，详情见[Mac试用指南](docs/MAC_TRIAL.md)。这是源码启动包，尚无Mac实机验收，不是免Python的签名.app。
