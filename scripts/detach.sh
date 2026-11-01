#!/usr/bin/env bash
# Start a command on A2 fully detached from the SSH session (survives this PC disconnecting).
# Usage: bash scripts/detach.sh LOGFILE command [args...]   (run from ~/tls-sok)
log=$1; shift
cd "$(dirname "$0")/.."
setsid nohup "$@" > "$log" 2>&1 < /dev/null &
echo "started pid $! -> $log"
