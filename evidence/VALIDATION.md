# 0.3：波次恢复与同仓人工补货/移位验收

本轮从原上传的阶段1bundle恢复a2681d4；上轮a0a955d和生成包不在当前云环境，波次按聊天记录重建并复验，不能声称找回旧提交。先通过阶段1原21项（1.742s）、重建波次后31项（3.433s），再实现003。对应baseline-tests.txt和restored-wave-tests.txt在stage3目录。

|命令|本轮最终结果|证据（evidence/stage3）|
|---|---|---|
|`python -m unittest discover -s tests -v`|44项全通过，5.643s|api-tests.txt|
|`python -m tests.browser_warehouse -v`|1项真实浏览器流程通过，7.014s|warehouse-browser-tests.txt、browser-warehouse.json、movement-*.png、waves-pt-mobile.png|
|`WMS_EVIDENCE_DIR=evidence/stage3/legacy python -m tests.browser_flow -v`|原履约闭环/响应丢失/BRL/中葡桌面手机回归通过，5.690s|legacy-browser-tests.txt、legacy目录截图与JSON|
|`node --check app/static/app.js`、`node --check app/static/warehouse-config.js`|通过|最终工具exit0|
|`python -m compileall -q app tests scripts`、`git diff --check`|通过|最终工具exit0|

44项=原21项+重建波次10项+本轮搬运13项。测试均独立临时SQLite真实API；无mock ERP/假成功。部分命令并行，时长不是生产性能。socket测试需工具network.enabled=true支持本机套接字。

## 本轮关键证据

- 100件、订单波次预占3件，再锁搬运40：on_hand100/reserved3/move_reserved40/available57；搬出后库位60+搬运中40，仍保管100。波次任务可拣原预占3，不受空闲数量搬运影响。接收后库位100，实际交接3后97，账本一致。
- 浏览器40件补货：锁后可用60，搬出后库位60+搬运中40=100，到位后库存100；再两单波次发5件后95。手工MOVE任务5件未搬出取消释放锁。
- 订单预占与搬运锁并发抢最后1件最多一个成功；两个搬运锁抢末件、两个接收请求也最多一个新键成功。
- 创建/搬出/接收各同键重复10次仍只有一次业务记录；实物流水一对−40/+40，待搬锁和搬运中变化各自守恒。浏览器目标已入账但响应被丢弃，原键重试不再增加目标库存。
- 错码、错源/目标、非整任务数量、越序、他人领取操作被拒；已搬出不可取消/释放/重新领取；未搬出取消才释放数量，release仅释放领取。
- 目标接收阶段注入真实数据库写失败，目标库存新行、流水、状态、幂等均回滚；去掉故障后相同key恢复成功。
- 跨租户/未授权仓访问、货主/只读/打包/财务角色读写任务被拒；货主自己库存汇总仍显示搬运中数量。不同货主同SKU字符串不串账。
- 真正只含001/002的旧库（有部分已拣波次）升级003，snapshot、已有流水与任务保持，新增字段默认0；缺003健康503，迁移后200，重复迁移和外键/integrity通过。
- IN_TRANSIT时SQLite独立备份恢复，完整snapshot相等；恢复库接收完成不改变源库的搬运中状态。原恢复测试本轮输出另存recovery.json，根目录阶段1文件保持历史版本。
- 中文1440×1000、pt-BR手机390×844、无页面横向溢出（明细表独立滚动）、JS错误0、浏览器业务/令牌不写localStorage/sessionStorage、货主无仓内任务导航。
- 登录后早期导航时序回归曾发现页面被切回总览，已修复并重跑两套浏览器；最后表格仅列通过的最终运行。

本轮未重建0.3容器、运行长期负载、真实ERP、实物设备或生产部署。自动补货规则、盘点、跨仓调拨、部分搬运/损耗/回位等未完成。001字节保持原a2681d4版本；002按上轮契约重建，003增量迁移，无down。

下方保留阶段1历史验收；这些容器/探针结果不代表0.3已完成相同验收。

---

# 阶段 1 验收证据

执行日 2026-10-16（Asia/Shanghai）；所有客户、货主、SKU、运单、订单均为独立测试库内的合成数据。真实 HTTP/数据库操作，未使用 ERP 模拟成功接口。

## 可复现命令与本轮结果

|命令|结果|证据|
|---|---|---|
|`python -m unittest discover -s tests -v`|21 tests 全通过，2.645s|api-tests.txt|
|`python -m tests.browser_flow -v`|1 个完整浏览器验收通过；15 个业务动作，含费用；中葡桌面/手机，响应丢失后原键重试|browser-tests.txt、browser-flow.json、browser-*.png|
|`python -m tests.load_probe --orders 100 --concurrency 8`|100订单/8并发预占，100成功0错误；p50 15.483ms/p95 191.603ms/max746.561ms|load-probe.json|
|`docker compose config --quiet`|配置校验通过|本次shell exit0|
|`DOCKER_CONFIG=/tmp/wms-docker-config docker build --build-arg WMS_OFFLINE=1 -t overseas-wms:0.1.0 .`|固定依赖/基础镜像构建成功|container-build.txt|
|`DOCKER_CONFIG=/tmp/wms-docker-config python -m scripts.container_smoke`|非root UID10001、无外网/无发布端口、容器内完整HTTP链97、重启持久化通过|container-smoke.json|
|`node --check app/static/app.js`|语法通过|本次shell exit0|

本环境默认沙箱阻止本机 socket，会使 TestClient/Chromium 挂起。工具调用需 network.enabled=true 支持本机套接字；不是跳过测试。普通 Docker 构建拉基础镜像成功，但构建 RUN pip 无法解析网络源；未更改代理/DNS，改为授权环境下载固定版本 wheels 后离线安装。构建脚本支持重新下载，可复现，不把网络失败隐藏为默认构建已成功。

## 验收实测

- 收100、质检合格100、上架100；预占/拣货/复核/打包3时库位在库100/可用97；交接后在库97/预占0/已拣0/可用97，账本核对ok。
- 实收待检、合格未上架、残次与可售分区，实物总量守恒。退2先待收不加，签收待检、质检合格未上架不加可售，上架后99且重试不重复。
- 两个订单并发抢最后一件最多一个成功；多行缺货整笔回滚；相同key十次并发收货仅一记录；收货/上架/拣货/交接/计费十次重试不重复。
- 错条码/错库位/超量/乱序被拒；未拣取消释放而不增实物，已拣/已出库直接取消被拒。
- 不同货主同SKU字符串不串账；跨tenant/owner/warehouse及URL ID访问被拒；只读/拣货角色、过期/撤销token检查。
- SQLite online backup恢复到独立新库，完整授权snapshot与源相等、源未改变、库存97、账本一致、外键/integrity通过；restore耗时0.0026s（极小样本，非生产RTO）；凭证文件0600且stdout不含token。
- 反复迁移不丢数据，ledger/audit update/delete被拒；服务与容器重启数据仍在。
- 5家ERP注册表全禁用，未实现方法明确报错，不将协议契约测试记作第三方验收。

浏览器截图已脱敏，不包含token。首次截图视觉检查后修复了葡语身份/刷新时间/动作结果文案；证据截图为修正后复验。已测试屏幕1440×1000与390×844，无横向页面溢出，JS错误0；费用显示 R$ 1,50。实际扫码枪/打印机/秤不在本次验收。

性能探针是单进程 TestClient+真实SQLite，仅测100笔预占；5逻辑CPU可见、进程峰值RSS54480KiB、Python3.12.14/SQLite3.53.1/x86_64。BEGIN IMMEDIATE串行写是已知瓶颈；未分离锁等待与线程开销，未包含真实网络、多进程、长期大数据或ERP，不能推断日单量、生产容量或SLA。生产RPO/RTO与持续告警尚无证据。
