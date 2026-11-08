#!/usr/bin/env bash
# Run the UCNet notebook step only when batch 6 and 6b have finished: the RAID 2024 notebooks load the full
# UCNet table (11M flows) next to their own data and were OOM-killed (exit 137, 8 Nov 13:59) while batch 6 ran.
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/ucnet_after_b6.log bash scripts/launch_after_batch6.sh
cd "$(dirname "$0")/.."
until grep -qh "^.* BATCH batch6 " /data/tls-sok/out/batch6_*.log 2>/dev/null && \
      grep -qh "^.* BATCH batch6b " /data/tls-sok/out/batch6b_*.log 2>/dev/null; do sleep 120; done
echo "$(date +%F' '%T) batch 6 lanes finished; starting launch_ucnet.sh"
exec bash scripts/launch_ucnet.sh
