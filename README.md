# Overseas WMS / OMS

可独立部署的海外仓系统，当前交付阶段 1 的真实内部履约闭环。中文/巴西葡语 WMS、货主 OMS、移动 PDA 页面使用同一认证后端和持久数据库。**未正式接通任何 ERP，未部署生产。**

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
python -m tests.load_probe
```

真实 SQLite 临时测试库与生产隔离；浏览器使用系统 Chromium 或已安装 Playwright 浏览器。受限环境须允许本机 socket，不需第三方 ERP 凭证。

容器：`docker compose build && docker compose up -d`。若构建环境无 DNS，先在允许联网的同架构环境执行 `python -m pip download --only-binary=:all: --dest wheelhouse -r requirements.lock`，然后 `docker compose build --build-arg WMS_OFFLINE=1`。wheels 不入版本库，无第三方密钥。首次启动自动迁移，管理员需手工初始化，详见操作手册。

- [准确进度](docs/PROJECT_STATUS.md)、[任务看板](docs/TASK_BOARD.md)、[换号/中断续接](docs/HANDOFF.md)
- [启动部署/权限/备份/回退/设备](docs/OPERATIONS.md)、[接口契约](docs/CONTRACT.md)、[API 使用](docs/API.md)
- [ERP 权限与能力](docs/ERP_CAPABILITIES.md)、[官方参考矩阵](docs/reference-matrix.md)
- [验收证据](evidence/VALIDATION.md)、[完整任务书](docs/Codex_Overseas_WMS_Master_Task.md)

单节点模块化单体：FastAPI + SQLite WAL，事务更新余额/只追加账本/幂等记录/审计。高吞吐多节点、波次盘点调拨、正式账单、物流面单、设备、持久同步队列等不在本次已完成范围；按任务板续接，不能用空页面计入完成。
