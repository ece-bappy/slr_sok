"""E9 fingerprint drift (runs on A2): JA3 vs JA4 vs no fingerprint, trained on old traffic, tested on
MTA 2023-26.

Usage: python scripts/run_e9.py [--seeds 5] [--boot 200] [--jobs 16] [--out /data/tls-sok/benchmark/e9]

Feature sets (the non-fingerprint features are fixed to G1-G4):
  no_fp        G1-G4
  fp_ja3       G1-G4 + JA3 + JA3S          fp_ja4      G1-G4 + JA4 + JA4S
  fp_both      G1-G4 + all four fingerprints (= the `all` set)
  only_ja3     JA3 + JA3S                  only_ja4    JA4 + JA4S
  only_ja3c    JA3 (client only)           only_ja4c   JA4 (client only)
Scenarios:
  mta_old>mta_new   MTA E3 split (train <= 2022, validation = latest 15% of that period, test 2023-26)
  mcfp>mta_new      train MCFP 2013-18 (validation 15% stratified), test MTA 2023-26
Same protocol as run_benchmark.py (per-table dedup per set, 1:1 balance, validation-only thresholds,
fixed XGBoost, bootstrap CIs). For every fingerprint column the script also counts how many test
values (distinct, and rows per class) never occur in the training rows before balancing.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from run_benchmark import (MODELS, balance, bootstrap, dedup, feature_frame, fit_predict, metrics, split,
                           thresholds, to_model_matrix)

FP = ("g5_ja3", "g5_ja3s", "g5_ja4", "g5_ja4s")


def sets_for(table: pd.DataFrame) -> dict:
    base = [c for c in table.columns if c.startswith(("g1_", "g2_", "g3_", "g4_"))]
    return {"no_fp": base, "fp_ja3": base + ["g5_ja3", "g5_ja3s"], "fp_ja4": base + ["g5_ja4", "g5_ja4s"],
            "fp_both": base + list(FP), "only_ja3": ["g5_ja3", "g5_ja3s"], "only_ja4": ["g5_ja4", "g5_ja4s"],
            "only_ja3c": ["g5_ja3"], "only_ja4c": ["g5_ja4"]}


def unseen(train: pd.DataFrame, test: pd.DataFrame, cols: list) -> list[dict]:
    out = []
    for c in [c for c in cols if c in FP]:
        known = set(train[c].fillna("").astype(str))
        v = test[c].fillna("").astype(str)
        new = ~v.isin(known)
        out.append({"fingerprint": c, "test_distinct": int(v.nunique()), "test_distinct_unseen": int(v[new].nunique()),
                    "test_rows": len(v), "test_rows_unseen": int(new.sum()),
                    "test_rows_unseen_malicious": int((new & (test["label"] == 1)).sum()),
                    "test_rows_malicious": int((test["label"] == 1).sum()),
                    "test_rows_unseen_benign": int((new & (test["label"] == 0)).sum()),
                    "test_rows_benign": int((test["label"] == 0).sum())})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="/data/tls-sok/tables")
    ap.add_argument("--out", default="/data/tls-sok/benchmark/e9")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--scenarios", default="mta_old>mta_new,mcfp>mta_new")
    ap.add_argument("--model", default="xgb", choices=MODELS)
    ap.add_argument("--sets", default=None, help="comma-separated subset of the feature sets (default: all)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    mta, mcfp = (pd.read_parquet(f"{a.tables}/{n}.parquet") for n in ("mta", "mcfp"))
    rows, ver_rows, unseen_rows, dedup_info = [], [], [], {}

    for fs, cols in sets_for(mta).items():
        if a.sets and fs not in a.sets.split(","):
            continue
        cols = [c for c in cols if c in mcfp.columns]
        d_mta, dedup_info[f"{fs}:mta"] = dedup(mta, cols)
        d_mcfp, dedup_info[f"{fs}:mcfp"] = dedup(mcfp, cols)
        print(fs, len(cols), dedup_info[f"{fs}:mta"]["rows_out"], dedup_info[f"{fs}:mcfp"]["rows_out"], flush=True)
        for sc in a.scenarios.split(","):
            for seed in range(a.seeds):
                if sc == "mta_old>mta_new":
                    sp = split(d_mta, "E3", "mta", seed)
                    train, test = d_mta.iloc[np.concatenate([sp[0], sp[1]])], d_mta.iloc[sp[2]]
                    tr, va = np.arange(len(sp[0])), np.arange(len(sp[0]), len(sp[0]) + len(sp[1]))
                else:
                    train, test = d_mcfp, d_mta[d_mta["k_year"].astype(str) > "2022"]
                    tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=train["label"].values,
                                              random_state=seed)
                train, test = train.reset_index(drop=True), test.reset_index(drop=True)
                y, y_te = train["label"].values, test["label"].values
                trb = balance(tr, y, seed)
                x_tr, (x_va, x_te) = to_model_matrix(feature_frame(train.iloc[trb], cols),
                                                     [feature_frame(train.iloc[va], cols), feature_frame(test, cols)])
                s_va, (s_te,), best, _ = fit_predict(a.model, x_tr, y[trb], x_va, y[va], [x_te], seed, a.jobs)
                thr_f1, thr_fpr = thresholds(y[va], s_va)
                m = metrics(y_te, s_te, thr_f1, thr_fpr)
                ci = bootstrap(y_te, s_te, thr_f1, thr_fpr, a.boot, seed)
                base = {"scenario": sc, "model": a.model, "feature_set": fs, "seed": seed}
                rows.append({**base, "n_features": len(cols), "n_train_balanced": len(trb), "best_iteration": best,
                             **m, **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                vers = test["k_tls_version"].values
                for v in np.unique(vers):
                    i = vers == v
                    ver_rows.append({**base, "tls_version": v, **metrics(y_te[i], s_te[i], thr_f1, thr_fpr)})
                if seed == 0:
                    unseen_rows += [{**base, **u} for u in unseen(train.iloc[tr], test, cols)]
                print(sc, fs, seed, {k: round(m[k], 4) for k in ("pr_auc", "macro_f1", "recall_malicious",
                                                                 "recall_benign")}, flush=True)

    res = pd.DataFrame(rows)
    res.to_csv(out / "results_per_seed.csv", index=False)
    pd.DataFrame(ver_rows).to_csv(out / "results_per_tls_version.csv", index=False)
    pd.DataFrame(unseen_rows).to_csv(out / "unseen_fingerprints.csv", index=False)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3",
            "test_fpr_at_that_threshold"]
    summ = res.groupby(["scenario", "feature_set"], sort=False)[keys + ["n", "n_pos"]].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    (out / "dedup.json").write_text(json.dumps(dedup_info, indent=2))
    print(summ.to_string())


if __name__ == "__main__":
    main()
