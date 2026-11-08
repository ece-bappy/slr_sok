"""Batch 7 (runs on A2): the closest prior work's protocol on our data (Wang, Fok & Thing, Computers & Security
113 (2022) 102542). They pool roughly balanced flows sampled at random from several public datasets and report
stratified 5-fold CV on the pool. Here the same pool is scored three ways, so the paper can put the numbers side
by side:
  random   stratified 5-fold CV, flows split at random (their protocol);
  grouped  the same pool, 5 folds grouped by capture / post / pcap / host (our protocol's grouping);
  held-out the matching leave-one-dataset-out rows of batch 6 (SUMMARY_b6_lodo.md; not rerun here).

Usage: python scripts/run_b7.py [--seeds 5] [--jobs 24] [--cap 50000] [--out DIR]
Pool, per seed: every source contributes the same number of flows per class (min over sources and classes of the
deduplicated counts, capped at --cap), so the pool is equal per source and 1:1 overall. Feature sets:
  g1g2_notime  G1+G2 without timing, over MTA, MCFP, RAID, HIKARI (clean-label subset);
  loo_g5       G1-G4 (no hashes), over MTA, MCFP, RAID (HIKARI has no TLS fields).
Models: XGBoost defaults and RF (Wang's best family), fixed hyperparameters as in run_benchmark.py. Per fold:
15% stratified validation split of the training folds for thresholds (max-F1, FPR 1e-3), 1:1 training sample,
test on the held-out fold. Folds are stratified on source x label, so every fold keeps the pool's mix.
Outputs (/data/tls-sok/benchmark/b7_wang/):
  results_per_fold.csv   per-fold metrics (threshold metrics are per fold, at that fold's validated thresholds)
  oof_per_seed.csv       out-of-fold ROC / PR-AUC per seed, pooled and per source, with 200-sample bootstrap CIs
  summary.csv            means / SDs over seeds
  pool.json              pool sizes per feature set
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, train_test_split

sys.path.insert(0, str(Path(__file__).parent))
from run_b6 import LODO_KEY, cols_for, fit_eval, table  # noqa: E402
from run_benchmark import dedup  # noqa: E402

FEATURE_SETS = {"g1g2_notime": ["mta", "mcfp", "raid", "hikari"], "loo_g5": ["mta", "mcfp", "raid"]}


def boot_auc(y, s, seed, n=200):
    rng = np.random.default_rng(seed)
    roc, pr = [], []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) == 2:
            roc.append(roc_auc_score(y[i], s[i]))
            pr.append(average_precision_score(y[i], s[i]))
    q = lambda v: f"{np.percentile(v, 2.5):.4f}-{np.percentile(v, 97.5):.4f}"
    return q(roc), q(pr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--cap", type=int, default=50_000)
    ap.add_argument("--models", default="xgb,rf")
    ap.add_argument("--out", default="/data/tls-sok/benchmark/b7_wang")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    folds, oof, pools = [], [], {}
    for fs, names in FEATURE_SETS.items():
        cols = cols_for(names, fs)
        d = {n: dedup(table(n), cols)[0].assign(_src=n) for n in names}
        counts = {n: {int(k): int(v) for k, v in d[n]["label"].value_counts().items()} for n in names}
        per = min(a.cap, *(c.get(k, 0) for c in counts.values() for k in (0, 1)))
        pools[fs] = {"sources": names, "dedup_counts": counts, "flows_per_class_per_source": per,
                     "pool_size": per * 2 * len(names), "n_features": len(cols)}
        print(fs, json.dumps(pools[fs]), flush=True)
        (out / "pool.json").write_text(json.dumps(pools, indent=2))
        for seed in range(a.seeds):
            rng = np.random.default_rng(seed)
            parts = []
            for n in names:
                lab = d[n]["label"].to_numpy()
                for k in (0, 1):
                    parts.append(d[n].iloc[rng.choice(np.where(lab == k)[0], per, replace=False)])
            pool = pd.concat(parts, ignore_index=True)
            y = pool["label"].to_numpy()
            strat = (pool["_src"] + "|" + pool["label"].astype(str)).to_numpy()
            groups = (pool["_src"] + "|" + pool.apply(lambda r: str(r[LODO_KEY[r["_src"]]]), axis=1)).to_numpy()
            splitters = {"random": StratifiedKFold(5, shuffle=True, random_state=seed).split(pool, strat),
                         "grouped": StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(pool, strat, groups)}
            for split_kind, it in splitters.items():
                fold_ix = list(it)
                for model in a.models.split(","):
                    s_oof = np.full(len(pool), np.nan)
                    for f, (trv, te) in enumerate(fold_ix):
                        tr, va = train_test_split(trv, test_size=0.15, stratify=strat[trv], random_state=seed)
                        test = pool.iloc[te].reset_index(drop=True)
                        r, s_te, _ = fit_eval(pool, test, tr, va, cols, seed, a.jobs, model=model, boot=0)
                        s_oof[te] = s_te
                        src_te = test["_src"].to_numpy()
                        per_src = {}
                        for n in names:
                            m_ = src_te == n
                            yy = test["label"].to_numpy()[m_]
                            per_src[f"roc_{n}"] = roc_auc_score(yy, s_te[m_]) if len(np.unique(yy)) == 2 else np.nan
                        folds.append({"feature_set": fs, "split": split_kind, "model": model, "seed": seed, "fold": f,
                                      "n_train_sampled": r["n_train"], **{k: r[k] for k in (
                                          "n", "n_pos", "pr_auc", "roc_auc", "macro_f1", "recall_malicious",
                                          "recall_benign", "tpr_at_val_fpr1e-3", "test_fpr_at_that_threshold")},
                                      **per_src})
                    roc_ci, pr_ci = boot_auc(y, s_oof, seed)
                    row = {"feature_set": fs, "split": split_kind, "model": model, "seed": seed, "n_pool": len(pool),
                           "oof_roc": roc_auc_score(y, s_oof), "oof_roc_ci": roc_ci,
                           "oof_pr_auc": average_precision_score(y, s_oof), "oof_pr_auc_ci": pr_ci}
                    src = pool["_src"].to_numpy()
                    for n in names:
                        m_ = src == n
                        row[f"oof_roc_{n}"] = roc_auc_score(y[m_], s_oof[m_])
                        row[f"oof_roc_{n}_ci"] = boot_auc(y[m_], s_oof[m_], seed)[0]
                    oof.append(row)
                    print(fs, split_kind, model, seed, round(row["oof_roc"], 4),
                          {n: round(row[f"oof_roc_{n}"], 3) for n in names}, flush=True)
                    pd.DataFrame(folds).to_csv(out / "results_per_fold.csv", index=False)
                    pd.DataFrame(oof).to_csv(out / "oof_per_seed.csv", index=False)
    o = pd.DataFrame(oof)
    num = [c for c in o.columns if c.startswith("oof_") and not c.endswith("_ci")]
    fm = pd.DataFrame(folds).groupby(["feature_set", "split", "model", "seed"])[
        ["macro_f1", "tpr_at_val_fpr1e-3", "test_fpr_at_that_threshold", "recall_malicious", "recall_benign"]].mean()
    o = o.merge(fm.reset_index(), on=["feature_set", "split", "model", "seed"])
    keys = num + list(fm.columns)
    s = o.groupby(["feature_set", "split", "model"], sort=False)[keys].agg(["mean", "std"])
    s.columns = [f"{k}_{t}" for k, t in s.columns]
    s.reset_index().to_csv(out / "summary.csv", index=False)
    print(s.round(4).to_string())


if __name__ == "__main__":
    main()
