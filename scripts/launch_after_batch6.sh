#!/usr/bin/env bash
# Run the UCNet notebook step only when batch 6 and 6b have finished: the RAID 2024 notebooks load the full
# UCNet table (11M flows) next to their own data and were OOM-killed (exit 137, 8 Nov 13:59) while batch 6 ran.
#   cd ~/tls-sok && bash scripts/detach.sh /data/tls-sok/out/ucnet_after_b6.log bash scripts/launch_after_batch6.sh
cd "$(dirname "$0")/.."
# start once batch 6 lane A (seeds -> baserate -> training) and batch 6e (items 11/12, which load all four
# datasets) have ended
until grep -qh -e "END b6_training" -e " BATCH batch6 " /data/tls-sok/out/batch6_*.log 2>/dev/null && \
      grep -qh " BATCH batch6e " /data/tls-sok/out/batch6e_*.log 2>/dev/null; do sleep 120; done
echo "$(date +%F' '%T) batch 6 lane A and batch 6e finished; starting launch_ucnet.sh"
exec bash scripts/launch_ucnet.sh
