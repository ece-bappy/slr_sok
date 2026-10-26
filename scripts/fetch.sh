#!/usr/bin/env bash
# Resumable parallel downloader. Usage: fetch.sh URLS.tsv DEST_DIR LOG [PARALLEL]
# URLS.tsv lines: <relative/path>\t<url>\t<expected_bytes>
# Connections slower than MIN_BPS for STALL_S seconds are dropped and resumed,
# since OSF/Zenodo speed varies a lot between connections.
set -u
list=$1; dest=$2; log=$3; par=${4:-1}
export dest log
export MIN_BPS=${MIN_BPS:-51200} STALL_S=${STALL_S:-45} MAX_TRIES=${MAX_TRIES:-500}

one() {
  IFS=$'\t' read -r rel url size <<< "$1"
  [ -z "$rel" ] && return
  out="$dest/$rel"; mkdir -p "$(dirname "$out")"
  have=$(stat -c %s "$out" 2>/dev/null || echo 0)
  if [ "$have" = "$size" ]; then echo "$(date +%F' '%T) SKIP $rel" >> "$log"; return; fi
  echo "$(date +%F' '%T) START $rel ($size bytes, have $have)" >> "$log"
  for ((t = 1; t <= MAX_TRIES; t++)); do
    curl -sSL --fail -C - --speed-time "$STALL_S" --speed-limit "$MIN_BPS" -o "$out" "$url" 2>/dev/null
    have=$(stat -c %s "$out" 2>/dev/null || echo 0)
    [ "$have" = "$size" ] && break
    [ "$have" -gt "$size" ] && { echo "$(date +%F' '%T) OVERSIZE $rel, restarting" >> "$log"; rm -f "$out"; }
    sleep 5
  done
  if [ "$have" = "$size" ]; then echo "$(date +%F' '%T) DONE $rel after $t tries" >> "$log"
  else echo "$(date +%F' '%T) FAIL $rel (have $have of $size)" >> "$log"; fi
}
export -f one

grep -v '^\s*$' "$list" | tr '\n' '\0' | xargs -0 -P "$par" -I{} bash -c 'one "$@"' _ {}
echo "$(date +%F' '%T) QUEUE_FINISHED" >> "$log"
