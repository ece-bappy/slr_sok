"""E1-E3 benchmark on one training table (runs on A2).

Usage: python scripts/run_benchmark.py {raid,hikari} [--tables /data/tls-sok/tables]
       [--out /data/tls-sok/benchmark] [--seeds 5] [--boot 200] [--jobs 16] [--sets all,g1g2]

Experiments (plan §5.4, with the dataset limits the user accepted on 1 Nov 2026):
  E1  stratified random split, 70/15/15
  E2  grouped split: RAID = capture-grouped (no pcap in two parts; the C2 class is one host pair,
      so host grouping is impossible); HIKARI = client-host-grouped (no client IP in two parts)
  E3  temporal: HIKARI 2021 -> 2022; RAID infeasible (capture year equals class) and reported so
Protocol (§5.5): within-class duplicate feature vectors and vectors seen in both classes are removed
per feature set before splitting; the majority class is subsampled to 1:1 in training only;
thresholds come from validation data only (max-F1, and FPR = 1e-3); 5 seeds; bootstrap 95% CIs on
the test set; every result is also broken down by the observed TLS version.
Model: XGBoost with fixed hyperparameters and early stopping on validation (tuning comes later).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

FPR_TARGET = 1e-3
SETS = {"all": ("g1_", "g2_", "g3_", "g4_", "g5_"), "g1g2": ("g1_", "g2_"), "g1g2_notime": ("g1_", "g2_")}
TIMING = ("piat", "duration")  # dropped in *_notime sets: timing reflects the capture network (§5.2)


def set_columns(table: pd.DataFrame, fs: str) -> list[str]:
    cols = [c for c in table.columns if c.startswith(SETS[fs])]
    if fs.endswith("_notime"):
        cols = [c for c in cols if not any(t in c for t in TIMING)]
    return cols


# ---------------------------------------------------------------- data

def is_text(s: pd.Series) -> bool:
    return s.dtype == object or pd.api.types.is_string_dtype(s)  # pandas 3 uses a 'str' dtype


def feature_frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    x = df[cols].copy()
    for c in cols:
        if is_text(x[c]):
            x[c] = x[c].fillna("").astype(object).astype(str)
    return x


def dedup(df: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, dict]:
    key = pd.util.hash_pandas_object(feature_frame(df, cols), index=False)
    lab_per_key = df.groupby(key.values)["label"].nunique()
    both = key.map(lab_per_key) > 1
    keep = ~both & ~pd.Series(list(zip(key, df["label"])), index=df.index).duplicated()
    info = {"rows_in": len(df), "dropped_in_both_classes": int(both.sum()),
            "dropped_within_class_duplicates": int((~both).sum() - keep.sum()), "rows_out": int(keep.sum())}
    return df[keep].reset_index(drop=True), info


def to_model_matrix(x_tr, x_other: list):
    """Strings -> pandas categoricals with categories from training only (unseen -> missing)."""
    out_tr, outs = x_tr.copy(), [x.copy() for x in x_other]
    for c in x_tr.columns:
        if is_text(x_tr[c]):
            cats = pd.Index(x_tr[c].dropna().unique())
            out_tr[c] = pd.Categorical(x_tr[c], categories=cats)
            for o in outs:
                o[c] = pd.Categorical(o[c], categories=cats)
    return out_tr, outs


# ---------------------------------------------------------------- splits

def split(df: pd.DataFrame, exp: str, dataset: str, seed: int):
    """Return (train_idx, val_idx, test_idx) or a string saying why the split is infeasible."""
    idx = np.arange(len(df))
    y = df["label"].values
    if exp == "E1":
        tr, rest = train_test_split(idx, test_size=0.30, stratify=y, random_state=seed)
        va, te = train_test_split(rest, test_size=0.50, stratify=y[rest], random_state=seed)
        return tr, va, te
    if exp == "E2":
        # test groups are disjoint from training groups; validation (early stopping, thresholds)
        # is a stratified sample of the non-test rows, because HIKARI has only two attacker hosts
        groups = (df["k_pcap"] if dataset == "raid" else df["k_client_ip"]).values
        for attempt in range(20):
            sgk = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed * 100 + attempt)
            for _, te in sgk.split(idx, y, groups):
                rest = np.setdiff1d(idx, te)
                if len(np.unique(y[te])) == 2 and len(np.unique(y[rest])) == 2:
                    tr, va = train_test_split(rest, test_size=0.15, stratify=y[rest], random_state=seed)
                    return tr, va, te
        return "no grouping found with both classes in train and test"
    if exp == "E3":
        if dataset == "raid":
            return "infeasible: all C2 flows are from 2022 and all benign flows from 2024 (year = class)"
        old, new = idx[df["k_year"].values == "2021"], idx[df["k_year"].values == "2022"]
        if len(np.unique(y[new])) < 2 or len(np.unique(y[old])) < 2:
            return "infeasible: one year lacks a class"
        # validation = the latest 15% of 2021 by time, so it is also 'later than training'
        old = old[np.argsort(df["k_first_seen_ms"].values[old])]
        cut = int(len(old) * 0.85)
        tr, va = old[:cut], old[cut:]
        if len(np.unique(y[va])) < 2 or len(np.unique(y[tr])) < 2:
            tr, va = train_test_split(old, test_size=0.15, stratify=y[old], random_state=seed)
        return tr, va, new
    raise ValueError(exp)


def balance(tr: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pos, neg = tr[y[tr] == 1], tr[y[tr] == 0]
    n = min(len(pos), len(neg))
    return np.concatenate([rng.choice(pos, n, replace=False), rng.choice(neg, n, replace=False)])


# ---------------------------------------------------------------- metrics

def metrics(y, s, thr_f1, thr_fpr) -> dict:
    out = {"n": len(y), "n_pos": int(y.sum())}
    two = len(np.unique(y)) == 2
    p = (s >= thr_f1).astype(int)
    out["pr_auc"] = average_precision_score(y, s) if two else np.nan
    out["roc_auc"] = roc_auc_score(y, s) if two else np.nan
    out["macro_f1"] = f1_score(y, p, average="macro") if two else np.nan
    out["recall_malicious"] = p[y == 1].mean() if (y == 1).any() else np.nan
    out["recall_benign"] = 1 - p[y == 0].mean() if (y == 0).any() else np.nan
    q = s >= thr_fpr
    out["tpr_at_val_fpr1e-3"] = q[y == 1].mean() if (y == 1).any() else np.nan
    out["test_fpr_at_that_threshold"] = q[y == 0].mean() if (y == 0).any() else np.nan
    out["accuracy"] = (p == y).mean()
    return out


def bootstrap(y, s, thr_f1, thr_fpr, n_boot, seed) -> dict:
    rng = np.random.default_rng(seed)
    keys = ["pr_auc", "macro_f1", "recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3"]
    vals = {k: [] for k in keys}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        m = metrics(y[i], s[i], thr_f1, thr_fpr)
        for k in keys:
            vals[k].append(m[k])
    return {f"{k}_ci": (np.nanpercentile(v, 2.5), np.nanpercentile(v, 97.5)) for k, v in vals.items()}


def thresholds(y_va, s_va) -> tuple[float, float]:
    cand = np.unique(np.quantile(s_va, np.linspace(0, 1, 501)))
    f1 = [f1_score(y_va, (s_va >= t).astype(int), average="macro") for t in cand]
    thr_f1 = cand[int(np.argmax(f1))]
    neg = np.sort(s_va[y_va == 0])
    thr_fpr = neg[min(len(neg) - 1, int(np.ceil(len(neg) * (1 - FPR_TARGET))))] + 1e-12 if len(neg) else 1.0
    return thr_f1, thr_fpr


# ---------------------------------------------------------------- shortcut screen

def univariate_auc(x: pd.DataFrame, y: np.ndarray) -> pd.Series:
    """Train-set AUC of each feature alone (categoricals scored by their positive rate)."""
    res = {}
    for c in x.columns:
        v = x[c]
        if is_text(v) or str(v.dtype) == "category":
            v = v.astype(str).map(pd.Series(y, index=v.index).groupby(v.astype(str).values).mean())
        v = pd.to_numeric(v, errors="coerce").fillna(-1e18).values
        if np.unique(v).size < 2:
            continue
        a = roc_auc_score(y, v)
        res[c] = max(a, 1 - a)
    return pd.Series(res).sort_values(ascending=False)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=["raid", "hikari"])
    ap.add_argument("--tables", default="/data/tls-sok/tables")
    ap.add_argument("--out", default="/data/tls-sok/benchmark")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--sets", default=None)
    a = ap.parse_args()

    out = Path(a.out) / a.dataset
    out.mkdir(parents=True, exist_ok=True)
    table = pd.read_parquet(f"{a.tables}/{a.dataset}.parquet")
    sets = (a.sets or ("all,g1g2,g1g2_notime" if a.dataset == "raid" else "g1g2,g1g2_notime")).split(",")
    rows, ver_rows, dedup_info, shortcut_rows, imp_rows = [], [], {}, [], []

    for fs in sets:
        cols = set_columns(table, fs)
        df, dedup_info[fs] = dedup(table, cols)
        print(fs, dedup_info[fs], flush=True)
        y = df["label"].values
        for exp in ("E1", "E2", "E3"):
            for seed in range(a.seeds):
                sp = split(df, exp, a.dataset, seed)
                base = {"dataset": a.dataset, "feature_set": fs, "experiment": exp, "seed": seed}
                if isinstance(sp, str):
                    rows.append({**base, "status": sp})
                    break
                tr, va, te = sp
                trb = balance(tr, y, seed)
                x_tr, (x_va, x_te) = to_model_matrix(feature_frame(df.iloc[trb], cols),
                                                     [feature_frame(df.iloc[va], cols), feature_frame(df.iloc[te], cols)])
                model = xgb.XGBClassifier(n_estimators=1000, max_depth=8, learning_rate=0.1, subsample=0.8,
                                          colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
                                          max_cat_to_onehot=1, n_jobs=a.jobs, random_state=seed,
                                          early_stopping_rounds=30, eval_metric="logloss")
                model.fit(x_tr, y[trb], eval_set=[(x_va, y[va])], verbose=False)
                s_va, s_te = model.predict_proba(x_va)[:, 1], model.predict_proba(x_te)[:, 1]
                thr_f1, thr_fpr = thresholds(y[va], s_va)
                m = metrics(y[te], s_te, thr_f1, thr_fpr)
                ci = bootstrap(y[te], s_te, thr_f1, thr_fpr, a.boot, seed)
                rows.append({**base, "status": "ok", "n_train_balanced": len(trb), "n_val": len(va),
                             "best_iteration": model.best_iteration, "thr_f1": thr_f1, "thr_fpr": thr_fpr,
                             **m, **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                vers = df["k_tls_version"].values[te]
                for v in np.unique(vers):
                    i = vers == v
                    ver_rows.append({**base, "tls_version": v, **metrics(y[te][i], s_te[i], thr_f1, thr_fpr)})
                if seed == 0:
                    g = model.get_booster().get_score(importance_type="gain")
                    for k, val in sorted(g.items(), key=lambda kv: -kv[1])[:15]:
                        imp_rows.append({**base, "feature": k, "gain": val})
                    if exp == "E1":
                        ua = univariate_auc(feature_frame(df.iloc[tr], cols), y[tr])
                        for k, val in ua.head(25).items():
                            shortcut_rows.append({"dataset": a.dataset, "feature_set": fs, "feature": k,
                                                  "train_auc_alone": round(val, 4), "flag": val >= 0.99})
                print(exp, fs, seed, {k: round(m[k], 4) for k in ("pr_auc", "macro_f1", "recall_malicious",
                                                               "recall_benign", "tpr_at_val_fpr1e-3")}, flush=True)

    res = pd.DataFrame(rows)
    res.to_csv(out / "results_per_seed.csv", index=False)
    pd.DataFrame(ver_rows).to_csv(out / "results_per_tls_version.csv", index=False)
    pd.DataFrame(shortcut_rows).to_csv(out / "shortcut_screen.csv", index=False)
    pd.DataFrame(imp_rows).to_csv(out / "feature_importance_seed0.csv", index=False)
    ok = res[res["status"] == "ok"]
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3",
            "test_fpr_at_that_threshold", "accuracy"]
    summ = ok.groupby(["dataset", "feature_set", "experiment"])[keys].agg(["mean", "std"]) if len(ok) else pd.DataFrame()
    if len(summ):
        summ.columns = [f"{k}_{s}" for k, s in summ.columns]
        summ = summ.reset_index()
    infeasible = res[res["status"] != "ok"][["dataset", "feature_set", "experiment", "status"]].drop_duplicates()
    summ = pd.concat([summ, infeasible], ignore_index=True)
    summ.to_csv(out / "summary.csv", index=False)
    (out / "dedup.json").write_text(json.dumps(dedup_info, indent=2))
    print(summ.to_string())


if __name__ == "__main__":
    main()
