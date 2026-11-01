"""E4 cross-dataset benchmark (runs on A2). Train on one source, test on another; no target data is
used for training, early stopping or thresholds.

Usage: python scripts/run_e4.py [--tables /data/tls-sok/tables] [--out /data/tls-sok/benchmark/e4]
       [--seeds 5] [--boot 200] [--jobs 16] [--sets all,g1g2,g1g2_notime] [--pairs mcfp>mta,...]

Pairings (proposed in review/benchmark/SUMMARY_mta_mcfp.md):
  mcfp>mta, mta>mcfp      whole source -> whole target (MCFP 2013-18 sandbox vs MTA 2019-26)
  raid>mta, raid>mcfp     single-tool Metasploit C2 + scripted benign -> real malware traffic
  Negative swap on MTA, with MTA infection cases (posts) split 70/30 per seed so no post is in both parts:
  mtaN_ctu>mtaN_bg        train MTA malicious + CTU-Normal, test MTA malicious + MTA background
  mtaN_bg>mtaN_ctu        train MTA malicious + MTA background, test MTA malicious + CTU-Normal
  mtaN_bg>mtaN_bg         control: same post split, MTA background on both sides
Same protocol as run_benchmark.py: per-table dedup per feature set, 1:1 training balance, validation =
15% stratified sample of the training source, thresholds from validation (max-F1, FPR 1e-3), XGBoost
with fixed hyperparameters, bootstrap CIs, per-TLS-version breakdown. Test rows whose feature vector
also occurs in the training rows are counted (overlap) but kept.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from run_benchmark import (balance, bootstrap, dedup, feature_frame, metrics, set_columns, thresholds,
                           to_model_matrix)

PAIRS = ["mcfp>mta", "mta>mcfp", "raid>mta", "raid>mcfp", "mtaN_ctu>mtaN_bg", "mtaN_bg>mtaN_ctu",
         "mtaN_bg>mtaN_bg"]
MAX_BOOT_ROWS = 200_000  # larger test sets get fewer bootstrap resamples (recorded in n_boot)


def build(pair: str, d: dict, seed: int):
    """(train_df, test_df) for one pairing; d holds the deduplicated tables for this feature set."""
    src, dst = pair.split(">")
    if not src.startswith("mtaN"):
        return d[src], d[dst]
    mta, ctu = d["mta"], d["mcfp"][d["mcfp"]["label"] == 0]
    tr_i, te_i = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=seed)
                      .split(mta, groups=mta["k_post"].values))
    mta_tr, mta_te = mta.iloc[tr_i], mta.iloc[te_i]
    side = lambda part, neg: pd.concat([part[part["label"] == 1], part[part["label"] == 0] if neg == "bg" else ctu])
    return (side(mta_tr, src.split("_")[1]).reset_index(drop=True),
            side(mta_te, dst.split("_")[1]).reset_index(drop=True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="/data/tls-sok/tables")
    ap.add_argument("--out", default="/data/tls-sok/benchmark/e4")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--sets", default="all,g1g2,g1g2_notime")
    ap.add_argument("--pairs", default=",".join(PAIRS))
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pairs = a.pairs.split(",")
    names = sorted({n.replace("mtaN", "mta").split("_")[0] for p in pairs for n in p.split(">")} | {"mta"}
                   | ({"mcfp"} if any("ctu" in p for p in pairs) else set()))
    tables = {n: pd.read_parquet(f"{a.tables}/{n}.parquet") for n in names}
    rows, ver_rows, imp_rows, dedup_info = [], [], [], {}

    for fs in a.sets.split(","):
        cols = sorted(set.intersection(*(set(set_columns(t, fs)) for t in tables.values())))
        d = {}
        for n, t in tables.items():
            d[n], dedup_info[f"{fs}:{n}"] = dedup(t, cols)
        print(fs, len(cols), "features", {k: v["rows_out"] for k, v in dedup_info.items() if k.startswith(fs)},
              flush=True)
        for pair in pairs:
            for seed in range(a.seeds):
                train, test = build(pair, d, seed)
                y, y_te = train["label"].values, test["label"].values
                tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=y, random_state=seed)
                trb = balance(tr, y, seed)
                f_tr = feature_frame(train.iloc[trb], cols)
                f_te = feature_frame(test, cols)
                overlap = int(pd.util.hash_pandas_object(f_te, index=False)
                              .isin(set(pd.util.hash_pandas_object(feature_frame(train, cols), index=False))).sum())
                x_tr, (x_va, x_te) = to_model_matrix(f_tr, [feature_frame(train.iloc[va], cols), f_te])
                model = xgb.XGBClassifier(n_estimators=1000, max_depth=8, learning_rate=0.1, subsample=0.8,
                                          colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
                                          max_cat_to_onehot=1, n_jobs=a.jobs, random_state=seed,
                                          early_stopping_rounds=30, eval_metric="logloss")
                model.fit(x_tr, y[trb], eval_set=[(x_va, y[va])], verbose=False)
                s_va, s_te = model.predict_proba(x_va)[:, 1], model.predict_proba(x_te)[:, 1]
                thr_f1, thr_fpr = thresholds(y[va], s_va)
                m = metrics(y_te, s_te, thr_f1, thr_fpr)
                n_boot = a.boot if len(y_te) <= MAX_BOOT_ROWS else max(20, a.boot // 4)
                ci = bootstrap(y_te, s_te, thr_f1, thr_fpr, n_boot, seed)
                base = {"pair": pair, "feature_set": fs, "seed": seed}
                rows.append({**base, "n_features": len(cols), "n_train_balanced": len(trb), "n_val": len(va),
                             "test_rows_seen_in_train": overlap, "n_boot": n_boot,
                             "best_iteration": model.best_iteration, "thr_f1": thr_f1, "thr_fpr": thr_fpr,
                             **m, **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                vers = test["k_tls_version"].values
                for v in np.unique(vers):
                    i = vers == v
                    ver_rows.append({**base, "tls_version": v, **metrics(y_te[i], s_te[i], thr_f1, thr_fpr)})
                if seed == 0:
                    g = model.get_booster().get_score(importance_type="gain")
                    for k, val in sorted(g.items(), key=lambda kv: -kv[1])[:15]:
                        imp_rows.append({**base, "feature": k, "gain": val})
                print(pair, fs, seed, {k: round(m[k], 4) for k in ("pr_auc", "macro_f1", "recall_malicious",
                                                                  "recall_benign", "tpr_at_val_fpr1e-3")}, flush=True)

    res = pd.DataFrame(rows)
    res.to_csv(out / "results_per_seed.csv", index=False)
    pd.DataFrame(ver_rows).to_csv(out / "results_per_tls_version.csv", index=False)
    pd.DataFrame(imp_rows).to_csv(out / "feature_importance_seed0.csv", index=False)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3",
            "test_fpr_at_that_threshold", "accuracy"]
    summ = res.groupby(["pair", "feature_set"])[keys + ["n", "n_pos"]].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ = summ.reset_index()
    summ.to_csv(out / "summary.csv", index=False)
    (out / "dedup.json").write_text(json.dumps(dedup_info, indent=2))
    print(summ.to_string())


if __name__ == "__main__":
    main()
