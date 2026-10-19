# 0.5 跨仓调拨与隔离本地试用验收

当前结果来自独立临时SQLite/真实HTTP/Chromium/虚构货物，不代表生产上线、真实ERP连接或实物设备验收。

|检查|结果|证据|
|---|---|---|
|0.4原64项基线|64通过|stage5/baseline-api-tests.txt|
|全量后端：原64+调拨19+试用入口3|86通过，12.573s|stage5/api-tests.txt|
|跨仓真实浏览器|1通过，最终5.120s|stage5/browser-tests.txt、browser-transfers.json、transfer-*.png|
|盲盘/复盘/期间出库回归|1通过，11.436s|stage5/count-browser-tests.txt、counts/|
|波次/同仓搬运回归|1通过，14.179s|stage5/warehouse-browser-tests.txt、warehouse/|
|旧履约/退货/费用回归|1通过，6.409s|stage5/legacy-browser-tests.txt、legacy/|
|实际本地启动脚本：prepare-only、同目录启动、HTTP健康/余额、SIGINT停止|通过，Linux；不输出令牌|stage5/local-trial-smoke.json|
|Python编译、4个JS语法、diff空白、旧001–004未改|通过|本轮命令检查与Git差异|

调拨18项初始定向验证后，追加权限变化后的缓存重放检查，最终为19项。覆盖两端权限、租户/货主/盘点账号隔离、不同仓校验、唯一参考号、错误扫描/阶段/严格整数、订单/搬运/盘点锁、源/目标测量锁交互、末件并发、并发超收及收货/丢失结案竞争、原键重放、跨人员批次防重、先写余额再故障整笔回滚、不可改删事件、重启/恢复后继续分批收货、损坏元数据拒绝，以及004真实旧格式余额/流水升级005保留。

浏览器新流程使用与用户相同的本地试用准备入口：100件→源仓专用账号发20（源80/在途20）→目标仓专用账号收7+8（目标15/在途5）→admin依据确认丢失剩5结案（保管95/历史丢失5/在途0）。两次提交成功但响应丢失，原键只入账一次；同批新键被拒绝。切专用counter后调拨入口/表格/快照为空，中葡桌面1440和手机390，页面不横向溢出，0JS错误/空业务存储。退出清空前账号库存/订单/流水/下拉选项的DOM，再切盲盘账号无残留；辅助跳转链接仅键盘聚焦时显示，最后重新验证Tab可达/失焦隐藏，避免遮挡表单。

新增本地入口3项检查：显式新建虚构业务/五岗权限/100件余额/保护文件及重启不重置；已有非试用目录和符号链接拒绝；凭证撤销后拒绝静默续接/重发。手工烟测真实启动模块与正常退出，通过health及100件余额检查。普通应用启动不自动生成示例数据。

历史stage3/stage4及根recovery证据保留。stage5/recovery.json来自本轮旧履约恢复检查；调拨部分接收的独立恢复由后端测试验证，不能仅依靠旧履约恢复报告声称跨仓验收。

本轮未构建0.5容器、未验收Windows/macOS/PDA/打印/相机、未跑长期负载或安全验收；版本标签不等于容器通过，阶段1容量/容器证据仍属历史。无生产部署/公网试用网址。新schema不能降级旧代码继续业务写入。

---

# 0.4 截点盘点、盲盘、独立复盘与差异审批

从远程63fb8df同步继续，先回归原44项（5.045s，stage4/baseline-tests.txt）；新增004，001–003保持原字节。所有货主/账号/盘数为独立临时SQLite合成数据，无真实ERP/生产或实物盘点验收。

|命令|最终结果|证据（evidence/stage4）|
|---|---|---|
|`python -m unittest discover -s tests -v`|64项通过，18.096s|api-tests.txt|
|`python -m tests.browser_counts -v`|盲盘/复盘/审批与截点后出库通过，10.555s|count-browser-tests.txt、browser-counts.json、count-*.png|
|`WMS_WAREHOUSE_EVIDENCE_DIR=evidence/stage4/warehouse python -m tests.browser_warehouse -v`|原波次/搬运浏览器回归通过，11.778s|warehouse-browser-tests.txt、warehouse目录|
|`WMS_EVIDENCE_DIR=evidence/stage4/legacy python -m tests.browser_flow -v`|原收100→发3→97/BRL/中葡手机回归通过，12.131s|legacy-browser-tests.txt、legacy目录|
|Python compileall、3个JS语法、git diff --check、001–003无差异|通过|本轮工具exit0|

64项=原44+盘点20；浏览器3项全通过。部分命令并行，时长仅当前环境测试数据，不代表生产性能。TestClient/Chromium需工具network.enabled=true支持本机socket；无新依赖。

## 关键验证

- 100账面初盘98，短少锁2；合法发3后账面97，另一专用账号复盘95（差额仍−2），再发5后账面92，审批只过账−2到90。后续同仓移位10件仍保留，不能覆盖成95或98。
- 截点后新收3件保留：10初盘8，复盘8后收3，审批后11。已知短少锁阻止订单/搬运超占，审批与锁释放同事务可保留合法预占。
- 实盘暂停时阻止上架、搬运入位和数量变更；订单可用别的库位。measurement available=0，count_locked明确显示。开盘与末件预占并发最多一个先成功；同库存重叠盘点由唯一约束阻断。
- 专用count_only只能查/提交自己任务。snapshot、GET和幂等响应不含账面/截点/差额；其他读数ID404，业务API403，普通picker无盘点权限。CLI0600凭证不输出，旧用户升级后不自动变为专用账号。
- 非零差额需连续两次不同账号一致，复盘不一致继续暂停确认；原始读数/截点SQL改删被拒。零实盘、已知SKU空库位盘盈、多库位范围均验证。
- 并发审批最多一次调整；同键初盘与审批重复不重复计数。浏览器真实提交/审批已落库但响应丢失，原键重试仅一个COUNT_ADJUST事件。
- 审批第二行注入真实写失败后整单库存/流水/状态/幂等回滚，解除故障后原键恢复成功。取消释放锁、保留证据，不直接调整物理库存。
- 003真实旧schema带库内搬运中升级004不丢库存/账本/权限，缺004健康和认证503，重复迁移通过。
- 备份恢复保留复盘测量锁/短少锁/分配，恢复库可独立完成审批，源不变；损坏count_lines短少元数据时恢复拒绝。旧恢复结果另存stage4/recovery.json，历史证据不覆盖。
- 中葡桌面1440和手机390，无横向页面溢出（表格内滚动）、JS错误0、localStorage/sessionStorage无业务数据。专用账号只有盲盘作业页，管理员看得到审批依据。

当前范围是单SKU明确库位，不是全仓多SKU计划；系统保证账号不同，不保证现实人员身份。实盘暂停与物理现场程序需仓库执行。0.4容器未重建、无长期负载/设备/生产/ERP新验收。跨仓调拨、自动补货及实体回位仍未实现；旧0.3不执行count_only边界，禁止直接降级。

以下是0.3及阶段1历史记录，不作为0.4容器/负载验收。

---

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
