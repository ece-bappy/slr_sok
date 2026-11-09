#!/usr/bin/env bash
# Download CIRA-CIC-DoHBrw-2020 PCAP zips into /data/tls-sok/raw/dohbrw/ (user approval: they are fetching the
# dataset with their own CIC registration). The site needs the registration cookie, which the USER puts in
# ~/.cic_cookie (one line, the value of the browser's Cookie header; chmod 600). This script never prints it and
# passes it to curl through a private config file, not the command line.
# Several files in parallel; a connection slower than MIN_BPS for STALL_S seconds is dropped and resumed (-C -).
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/dohbrw_dl_$(date +%H%M).log bash scripts/dohbrw_fetch.sh [set]
#   set: start (2 benign + 3 malicious, default) | benign (all 8 benign) | all (start + the other 6 benign)
set -u
DEST=/data/tls-sok/raw/dohbrw
BASE='https://cicresearch.ca/CICDataset/DoHBrw-2020/download.php?file=PCAPs%2F'
# PAR=1: CIC's download.php serves one request per login session at a time (PHP session lock); parallel requests,
# and requests dropped by the stall guard, queue on the server and block every later request (seen 9 Nov 2026).
PAR=${PAR:-1} MIN_BPS=${MIN_BPS:-51200} STALL_S=${STALL_S:-300} MAX_TRIES=${MAX_TRIES:-50}
[ -s "$HOME/.cic_cookie" ] || { echo "missing ~/.cic_cookie (see header)"; echo "BATCH dohbrw_dl FAILED cookie"; exit 1; }
mkdir -p "$DEST"
CFG=$(mktemp); chmod 600 "$CFG"; trap 'rm -f "$CFG"' EXIT
printf 'header = "Cookie: %s"\n' "$(tr -d '\r\n' < "$HOME/.cic_cookie")" > "$CFG"
export DEST BASE MIN_BPS STALL_S MAX_TRIES CFG

B=DoHBenign-NonDoH M=DoHMalicious
START="$B/BenignDoH_NonDoH-Chrome-Cloudflare.zip $B/BenignDoH_NonDoH-Firefox-CloudFlare.zip
$M/MaliciousDoH-dns2tcp-Pcap-001_600.zip $M/MaliciousDoH-dnscat2-Pcap-001-600.zip $M/MaliciousDoH-iodine-pcap-001_600.zip"
REST="$B/BenignDoH_NonDoH-Chrome-AdGuard.zip $B/BenignDoH_NonDoH-Chrome-Google.zip $B/BenignDoH_NonDoH-Chrome-Quad9.zip
$B/BenignDoH_NonDoH-Firefox-AdGuard.zip $B/BenignDoH_NonDoH-Firefox-Google.zip $B/BenignDoH_NonDoH-Firefox-Quad9.zip"
case "${1:-start}" in
  start) LIST=$START ;;
  benign) LIST="$(echo "$START" | grep -o "$B/[^ ]*") $REST" ;;
  all) LIST="$START $REST" ;;
  *) echo "unknown set $1"; exit 1 ;;
esac

one() {
  rel=$1; name=$(basename "$rel"); out="$DEST/$name"
  [ -e "$out.done" ] && { echo "$(date +%F' '%T) SKIP $name"; return 0; }
  url="$BASE$(echo "$rel" | sed 's|/|%2F|g')"
  echo "$(date +%F' '%T) START $name"
  for ((t = 1; t <= MAX_TRIES; t++)); do
    curl -sS -L --fail -K "$CFG" -C - --speed-time "$STALL_S" --speed-limit "$MIN_BPS" -o "$out.part" "$url" 2>/dev/null
    rc=$?
    case $rc in
      0) break ;;
      22) echo "$(date +%F' '%T) $name: HTTP error (403 = cookie expired or not logged in); stopping"; return 1 ;;
      33) echo "$(date +%F' '%T) $name: server refuses resume; restarting from 0"; rm -f "$out.part" ;;
    esac
    sleep 5
  done
  if [ $rc -ne 0 ]; then echo "$(date +%F' '%T) FAILED $name after $t tries"; return 1; fi
  if [ "$(head -c 2 "$out.part")" != "PK" ]; then echo "$(date +%F' '%T) $name is not a zip (login page?)"; return 1; fi
  mv "$out.part" "$out" && touch "$out.done"
  echo "$(date +%F' '%T) DONE $name $(stat -c %s "$out") bytes after $t tries"
}
export -f one
echo "$LIST" | tr ' ' '\n' | grep . | xargs -P "$PAR" -I{} bash -c 'one "$1"' _ {}
bad=$(for f in $LIST; do [ -e "$DEST/$(basename "$f").done" ] || basename "$f"; done)
if [ -z "$bad" ]; then echo "$(date +%F' '%T) BATCH dohbrw_dl DONE"; else echo "$(date +%F' '%T) BATCH dohbrw_dl FAILED $(echo $bad)"; fi
