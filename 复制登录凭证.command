#!/bin/bash
# Explicitly choose one local role credential and copy it to the clipboard.
TASK_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/bash "$TASK_ROOT/scripts/mac_launcher.sh" copy
