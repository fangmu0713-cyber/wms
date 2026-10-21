#!/bin/sh
set -eu
umask 077
python -m app.cli migrate
exec "$@"
