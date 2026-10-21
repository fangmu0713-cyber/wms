#!/bin/bash
# Start local WMS, copy the administrator token, and open the browser.
TASK_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/bash "$TASK_ROOT/scripts/mac_launcher.sh" start
