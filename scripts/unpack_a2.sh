#!/usr/bin/env bash
# Unpack the archived pcaps on A2 into /data/tls-sok/unpacked (resumable: existing files are kept).
# Only pcaps are extracted. RAID's sslkeylog_*.txt files are left out: they would allow decryption,
# which this study excludes.
# Usage: bash scripts/unpack_a2.sh [raid_tranco|raid_ms|hikari_benign|all]
set -euo pipefail
R=/data/tls-sok/raw
U=/data/tls-sok/unpacked
what=${1:-all}

if [[ $what == all || $what == raid_tranco ]]; then
  mkdir -p "$U/raid_tranco"
  for z in "$R"/raid_tranco/pcaps/*.zip; do
    echo "$(date +%F' '%T) unzip $z"
    unzip -n -q "$z" '*.pcap' -d "$U/raid_tranco"
  done
fi
if [[ $what == all || $what == raid_ms ]]; then
  mkdir -p "$U/raid_ms"
  echo "$(date +%F' '%T) untar raid_ms"
  tar -xzf "$R/raid_ms/captures.tar.gz" -C "$U/raid_ms" --skip-old-files --wildcards '*.pcap' '*.pcapng'
fi
if [[ $what == all || $what == hikari_benign ]]; then
  mkdir -p "$U/hikari_benign"
  echo "$(date +%F' '%T) unzip hikari ground-truth"
  unzip -n -q -j "$R/hikari/ground-truth.zip" '*.pcap' -d "$U/hikari_benign"
fi
echo "$(date +%F' '%T) UNPACK_FINISHED $what"
