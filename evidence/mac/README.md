# Mac启动包检查

业务基线7dd0639，API/业务/迁移/requirements.lock没有改动。本次验证聚焦Mac源码启动包，不将Linux执行结果称为Mac实机结果。

- launcher-tests.txt：13项通过（Mac入口10+原本地试用3），0.835s。包含持久路径、源目录带空格/中文、凭证只送pbcopy stdin且不进argv/日志、缺失/符号链接/撤销/过期/摘要不符拒绝、跨进程实例锁、端口避让、锁定依赖校验、非Mac/旧Mac拒绝、缺轮子不创建环境、命令入口执行位和Bash语法。桌面API是明确stub。
- service-smoke.json：在Linux真实运行Mac入口的serve函数，桌面自动打开/复制关闭；真实loopback/HTTP/SQLite健康、100件、5账号、路径带空格和中文、SIGINT正常退出0、无令牌日志、核对正常。不是Darwin桌面执行。
- resolve-arm64.txt / resolve-x86_64.txt：各自13个锁定包的pip --no-index跨平台dry-run成功；未加载或运行Mac原生扩展。
- wheels.json：CPython3.12原生pydantic-core分别为匹配arm64/x86_64的64位Mach-O，读取文件头/标签验证，不代表Mac加载验收。
- Python编译、三个入口的bash -n、git diff --check通过；ZIP打包脚本检查依赖名/版本集合、两种原生标签、CRC和.command执行位。最终包SHA/大小记录在工作区分发报告，运行库、凭证、.venv及系统Python不进包。

初次服务烟测发现直接调用serve函数时Control+C会向调用者抛KeyboardInterrupt，已在serve内部收尾并复测正常退出。Mac本机未提供，因此Python安装器、Finder/Terminal、Gatekeeper、open/pbcopy及Safari/Chrome的实际体验仍待用户本机试用。包未签名/公证，不是免Python的.app/DMG。业务历史86项后端及4套浏览器证据在stage5，本次未改业务代码，不把它们重复算为新跑Mac测试。
