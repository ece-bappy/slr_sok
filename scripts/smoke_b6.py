"""Smoke test for run_b6.py: every item on a reduced scope, outputs under /data/tls-sok/smoke6 (not results)."""
import sys
import time
from argparse import Namespace
from pathlib import Path

import run_b6 as b

S = Path("/data/tls-sok/smoke6")
b.BENCH, b.PRED = S, S / "pred"
b.BENCH.mkdir(parents=True, exist_ok=True)
(S / "r24_protocol").symlink_to("/data/tls-sok/benchmark/r24_protocol") if not (S / "r24_protocol").exists() else None
b.SEED_RUNS = [("mta_e3", "all", "xgb"), ("mta_e3", "loo_g5", "xgb"), ("mcfp>mta", "all_notime", "xgb"),
               ("e9:mcfp>mta_new", "no_fp", "xgb"), ("e9:mcfp>mta_new", "fp_ja3", "xgb")]
b.CONTRASTS = [("mta_e3", "all", "loo_g5", "xgb"), ("e9:mcfp>mta_new", "fp_ja3", "no_fp", "xgb")]
items = sys.argv[1:] or ["seeds", "baserate", "family", "ech", "evasion", "encoding", "rolling", "training"]
for it in items:
    t0 = time.time()
    a = Namespace(seeds=2 if it in ("seeds", "baserate") else 1, jobs=24, min_posts=10_000 if it == "family" else 8)
    if it == "rolling":
        orig = b.item_rolling.__code__
    getattr(b, f"item_{it}")(a)
    print(f"=== {it} OK in {time.time() - t0:.0f}s", flush=True)
