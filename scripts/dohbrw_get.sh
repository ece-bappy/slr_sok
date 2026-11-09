#!/usr/bin/env bash
# One command for the whole CIRA-CIC-DoHBrw-2020 fetch, run by the user on A2:
#   bash ~/tls-sok/scripts/dohbrw_get.sh [start|benign|all]
# 1. If ~/.cic_cookie is missing, asks for the CIC Cookie header value (hidden input) and saves it (chmod 600).
#    The cookie is the only manual step: the site needs the user's own registration.
# 2. Starts, detached on A2, download -> check -> extract:
#    - dohbrw_fetch.sh: parallel, resumable download into /data/tls-sok/raw/dohbrw/;
#    - every zip: must be a valid zip; SHA-256 into SHA256SUMS; contents listed in <zip>.list.txt;
#    - extracted into /data/tls-sok/raw/dohbrw/x/<zip name>/ with Python's zipfile (no absolute or ../ paths,
#      no symlinks). Pcaps are data only: nothing in them is executed.
# Log: /data/tls-sok/out/dohbrw_<HHMM>.log, ending "BATCH dohbrw DONE|FAILED <step>". Rerunning resumes.
set -u
SET=${1:-start}
if [ "${DOHBRW_STAGE:-}" != run ]; then
  if [ ! -s "$HOME/.cic_cookie" ]; then
    echo "Paste the value of the 'Cookie:' request header from a CIC download in your browser, then Enter."
    echo "(Input is hidden. Only the part after 'Cookie: '.)"
    read -rs c; echo
    [ -n "$c" ] || { echo "empty; nothing saved"; exit 1; }
    umask 077; printf '%s\n' "$c" > "$HOME/.cic_cookie"; unset c
    echo "saved to ~/.cic_cookie (mode 600)"
  fi
  cd "$HOME/tls-sok" || exit 1
  LOG=/data/tls-sok/out/dohbrw_$(date +%H%M).log
  DOHBRW_STAGE=run bash scripts/detach.sh "$LOG" env DOHBRW_STAGE=run bash scripts/dohbrw_get.sh "$SET"
  echo "running detached; follow with:  tail -f $LOG"
  exit 0
fi

# ---------------------------------------------------------------- detached stage
cd "$HOME/tls-sok" || exit 1
exec 9> /data/tls-sok/out/.dohbrw.lock
flock -n 9 || { echo "$(date +%F' '%T) dohbrw already running; exiting"; exit 1; }
D=/data/tls-sok/raw/dohbrw
fail() { echo "$(date +%F' '%T) BATCH dohbrw FAILED $1"; exit 1; }
echo "$(date +%F' '%T) START download ($SET)"
mkdir -p "$D/x"
bash scripts/dohbrw_fetch.sh "$SET" | tee "$D/.fetch_last.log"
grep -q "BATCH dohbrw_dl DONE" "$D/.fetch_last.log" || fail download
for z in "$D"/*.zip; do
  n=$(basename "$z" .zip)
  [ -e "$D/x/$n.done" ] && { echo "$(date +%F' '%T) SKIP extract $n"; continue; }
  echo "$(date +%F' '%T) CHECK $n"
  .venv/bin/python -I - "$z" "$D/x/$n" <<'EOF' || fail "extract $n"
import os, stat, sys, zipfile
z, dest = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(z) as f:
    bad = f.testzip()
    if bad:
        sys.exit(f"corrupt member {bad}")
    infos = f.infolist()
    with open(z + ".list.txt", "w") as out:
        for i in infos:
            out.write(f"{i.file_size}\t{i.filename}\n")
    for i in infos:
        p = os.path.normpath(i.filename)
        if os.path.isabs(p) or p.startswith(".."):
            sys.exit(f"unsafe path {i.filename}")
        if stat.S_ISLNK(i.external_attr >> 16):
            sys.exit(f"symlink member {i.filename}")
    os.makedirs(dest, exist_ok=True)
    f.extractall(dest)
print(f"{len(infos)} members, {sum(i.file_size for i in infos)} bytes extracted to {dest}")
EOF
  (cd "$D" && sha256sum "$n.zip") >> "$D/SHA256SUMS"
  touch "$D/x/$n.done"
  echo "$(date +%F' '%T) EXTRACTED $n"
done
echo "$(date +%F' '%T) pcaps: $(find "$D/x" -type f \( -iname '*.pcap' -o -iname '*.pcapng' \) | wc -l), $(du -sh "$D/x" | cut -f1)"
echo "$(date +%F' '%T) BATCH dohbrw DONE"
