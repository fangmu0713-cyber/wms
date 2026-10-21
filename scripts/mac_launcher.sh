#!/bin/bash
# Compatible with the system Bash 3.2 shipped by macOS.
set -e
umask 077
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$TASK_ROOT"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "此入口用于 Mac；其他系统请参考 docs/LOCAL_TRIAL.md。"
  exit 1
fi
TASK_PYTHON=""
for candidate in "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12" "/opt/homebrew/bin/python3.12" "/usr/local/bin/python3.12" "python3.12" "python3"; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' >/dev/null 2>&1; then
    TASK_PYTHON="$candidate"
    break
  fi
done
if [ -z "$TASK_PYTHON" ]; then
  echo "请先安装 Python 3.12 的 macOS universal2 安装器（Apple 芯片/Intel 通用）。"
  echo "官方下载：https://www.python.org/downloads/macos/"
  echo "安装后重新双击“启动仓储.command”。"
  if [ -t 0 ]; then read -r -p "按回车关闭此窗口……" reply; fi
  exit 1
fi
exec "$TASK_PYTHON" -m scripts.mac_launcher "${1:-start}"
