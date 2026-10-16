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
