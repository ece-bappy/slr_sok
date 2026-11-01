"""E1-E3 benchmark on one training table (runs on A2).

Usage: python scripts/run_benchmark.py {raid,hikari} [--tables /data/tls-sok/tables]
       [--out /data/tls-sok/benchmark] [--seeds 5] [--boot 200] [--jobs 16] [--sets all,g1g2]

Experiments (plan §5.4, with the dataset limits the user accepted on 1 Nov 2026):
  E1  stratified random split, 70/15/15
  E2  grouped split: RAID = capture-grouped (no pcap in two parts; the C2 class is one host pair,
      so host grouping is impossible); HIKARI = client-host-grouped (no client IP in two parts)
  E3  temporal: HIKARI 2021 -> 2022, MTA 2019-22 -> 2023-26, MCFP 2013-15 -> 2016-18;
      RAID infeasible (capture year equals class) and reported so
  (E2 for MTA groups by infection case/post, for MCFP by capture)
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
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

FPR_TARGET = 1e-3
SETS = {"all": ("g1_", "g2_", "g3_", "g4_", "g5_"), "g1g2": ("g1_", "g2_"), "g1g2_notime": ("g1_", "g2_"),
        "all_notime": ("g1_", "g2_", "g3_", "g4_", "g5_"),
        # E8 visibility tiers (plan §5.2 table): TLS 1.2 = everything; TLS 1.3 = no certificate fields;
        # TLS 1.3 + ECH = no SNI/ClientHello extensions/fingerprints either, i.e. sizes, directions, timing
        "tier_tls12_full": ("g1_", "g2_", "g3_", "g4_", "g5_"), "tier_tls13": ("g1_", "g2_", "g3_", "g5_"),
        "tier_tls13_ech": ("g1_", "g2_")}
TIMING = ("piat", "duration")  # dropped in *_notime sets: timing reflects the capture network (§5.2)
EARLY_N = (3, 5, 10, 20)  # E6: sets early_<N> and early_<N>_notime, built by early_features()
# E6 visibility tags: features observable once the ClientHello / ServerHello / Certificate packet is seen
CH_FEATS = ("g3_ch_", "g3_n_ciphers", "g3_n_extensions", "g3_n_groups", "g3_n_sigalgs", "g3_n_ec_formats",
            "g3_ext_", "g3_has_alpn", "g3_alpn_first", "g3_sni_", "g3_has_ech", "g5_ja3", "g5_ja4")
SH_FEATS = ("g3_has_server_hello", "g3_sh_", "g3_n_sh_extensions", "g5_ja3s", "g5_ja4s")


def base_name(dataset: str) -> str:
    """'mta_sslbl' -> 'mta': variants of a table share its grouping and temporal rules."""
    return dataset.split("_")[0]
# E2 grouping: RAID per capture, HIKARI per client host, MTA per infection case (post), MCFP per capture
GROUP_KEY = {"raid": "k_pcap", "hikari": "k_client_ip", "mta": "k_post", "mcfp": "k_capture"}
E3_LAST_OLD_YEAR = {"hikari": "2021", "mta": "2022", "mcfp": "2015"}  # train on <= this year, test on later


def set_columns(table: pd.DataFrame, fs: str) -> list[str]:
    if fs.startswith("early_"):
        cols = [c for c in table.columns if c.startswith(f"e{fs.split('_')[1]}_")]
    else:
        cols = [c for c in table.columns if c.startswith(SETS[fs])]
    if fs.endswith("_notime"):
        cols = [c for c in cols if not any(t in c for t in TIMING)]
    return cols


def early_features(table: pd.DataFrame, n: int) -> pd.DataFrame:
    """Columns e<n>_* = what a detector has seen after the first n packets of a flow (E6).

    Packet features come from the first-20-packet sequences (never from full-flow G1 statistics):
    the first n sizes/directions/inter-arrival times plus per-direction counts and size/IAT statistics
    over those n packets. TLS fields are kept only for flows whose ClientHello (or ServerHello, or
    Certificate) packet index is <= n, and are missing otherwise, as for a live detector.
    """
    ps = table[[f"g2_ps_{i:02d}" for i in range(n)]].to_numpy(float)
    dr = table[[f"g2_dir_{i:02d}" for i in range(n)]].to_numpy(float)
    iat = table[[f"g2_piat_{i:02d}" for i in range(n)]].to_numpy(float)
    seen = ps >= 0  # -1 = flow had fewer packets
    out = {}
    for i in range(n):
        out[f"e{n}_ps_{i:02d}"], out[f"e{n}_dir_{i:02d}"], out[f"e{n}_piat_{i:02d}"] = ps[:, i], dr[:, i], iat[:, i]
    out[f"e{n}_packets"] = seen.sum(1)
    for name, m in (("up", seen & (dr == 0)), ("down", seen & (dr == 1)), ("bi", seen)):
        v = np.where(m, ps, np.nan)
        out[f"e{n}_{name}_packets"] = m.sum(1)
        out[f"e{n}_{name}_bytes"] = np.nansum(v, 1)
        with np.errstate(all="ignore"):
            for s, fn in (("mean_ps", np.nanmean), ("std_ps", np.nanstd), ("max_ps", np.nanmax), ("min_ps", np.nanmin)):
                out[f"e{n}_{name}_{s}"] = fn(v, 1)
    with np.errstate(all="ignore"):
        it = np.where(seen, iat, np.nan)
        out[f"e{n}_mean_piat"], out[f"e{n}_std_piat"], out[f"e{n}_max_piat"] = (
            np.nanmean(it, 1), np.nanstd(it, 1), np.nanmax(it, 1))
    out = pd.DataFrame(out, index=table.index)
    for tag, prefixes in (("k_pkt_ch", CH_FEATS), ("k_pkt_sh", SH_FEATS), ("k_pkt_cert", ("g4_",))):
        if tag not in table:
            continue
        vis = (table[tag] <= n).to_numpy()
        for c in [c for c in table.columns if c.startswith(prefixes)]:
            col = table[c].where(vis, "" if is_text(table[c]) else np.nan)
            out[f"e{n}_{c}"] = col
        if tag == "k_pkt_sh" and "g3_has_server_hello" in table:  # 'not yet seen' is itself observable
            out[f"e{n}_g3_has_server_hello"] = vis.astype(float)
    return out


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
    dataset = base_name(dataset)
    if exp == "E1":
        tr, rest = train_test_split(idx, test_size=0.30, stratify=y, random_state=seed)
        va, te = train_test_split(rest, test_size=0.50, stratify=y[rest], random_state=seed)
        return tr, va, te
    if exp == "E2":
        # test groups are disjoint from training groups; validation (early stopping, thresholds)
        # is a stratified sample of the non-test rows, because HIKARI has only two attacker hosts
        groups = df[GROUP_KEY[dataset]].values
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
        if dataset == "mcfp":  # also covers the mcfp_sslbl audit table, whose negatives are the same
            return ("infeasible: benign (CTU-Normal) flows are 93 from 2013, 78 from 2016 and 72,801 from 2017, "
                    "so no year split leaves a usable benign training set")
        cut_year = E3_LAST_OLD_YEAR[dataset]
        known = df["k_year"].values != "unknown"
        old = idx[known & (df["k_year"].values <= cut_year)]
        new = idx[known & (df["k_year"].values > cut_year)]
        if len(np.unique(y[new])) < 2 or len(np.unique(y[old])) < 2:
            have = df.groupby(["k_year", "label"]).size().to_dict()
            return f"infeasible: a period lacks a class (<= {cut_year} vs later); year:label counts {have}"
        # validation = the latest 15% of the old period by time, so it is also 'later than training'
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


# ---------------------------------------------------------------- models

MODELS = ("xgb", "lgbm", "rf", "lr")


def _numeric(x: pd.DataFrame) -> pd.DataFrame:
    """Categoricals -> training-category codes (missing/unseen = NaN), for random forest."""
    x = x.copy()
    for c in x.columns:
        if str(x[c].dtype) == "category":
            x[c] = x[c].cat.codes.astype(float).replace(-1, np.nan)
    return x.astype(float)


class LinearPrep:
    """Logistic-regression input: signed log1p, train-median imputation with missing flags, z-scaling;
    categoricals one-hot over their 30 most frequent training values."""

    def fit(self, x: pd.DataFrame):
        self.cats = {c: x[c].value_counts().index[:30].tolist() for c in x if str(x[c].dtype) == "category"}
        num = self._num(x)
        self.med = num.median()
        self.flag = [c for c in num if num[c].isna().any()]
        z = self._fill(num)
        self.mu, self.sd = z.mean(), z.std().replace(0, 1)
        return self

    def _num(self, x):
        num = x[[c for c in x if c not in self.cats]].astype(float)
        return np.sign(num) * np.log1p(num.abs())

    def _fill(self, num):
        flags = num[self.flag].isna().astype(float).add_suffix("__missing")
        return pd.concat([num.fillna(self.med).fillna(0), flags], axis=1)

    def transform(self, x: pd.DataFrame) -> np.ndarray:
        z = (self._fill(self._num(x)) - self.mu) / self.sd
        hots = [(x[c].astype(object) == v).astype(float).rename(f"{c}={v}") for c, vs in self.cats.items() for v in vs]
        return pd.concat([z] + hots, axis=1).to_numpy(float)


def fit_predict(kind: str, x_tr, y_tr, x_va, y_va, x_others: list, seed: int, jobs: int):
    """Fit one model; return (validation scores, [scores for x_others], best iteration, {feature: importance})."""
    if kind == "xgb":
        import xgboost as xgb  # imported here so the torch venv (run_deep.py) can use this module without it
        m = xgb.XGBClassifier(n_estimators=1000, max_depth=8, learning_rate=0.1, subsample=0.8,
                              colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
                              max_cat_to_onehot=1, n_jobs=jobs, random_state=seed,
                              early_stopping_rounds=30, eval_metric="logloss")
        m.fit(x_tr, y_tr, eval_set=[(x_va, y_va)], verbose=False)
        imp, best = m.get_booster().get_score(importance_type="gain"), m.best_iteration
        score = lambda x: m.predict_proba(x)[:, 1]
    elif kind == "lgbm":
        import lightgbm as lgb
        m = lgb.LGBMClassifier(n_estimators=1000, num_leaves=63, learning_rate=0.05, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.8, n_jobs=jobs, random_state=seed, verbose=-1)
        m.fit(x_tr, y_tr, eval_set=[(x_va, y_va)], callbacks=[lgb.early_stopping(30, verbose=False)])
        imp = dict(zip(x_tr.columns, m.booster_.feature_importance("gain")))
        best, score = m.best_iteration_, lambda x: m.predict_proba(x)[:, 1]
    elif kind == "rf":
        from sklearn.ensemble import RandomForestClassifier
        m = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, max_features="sqrt", n_jobs=jobs,
                                   random_state=seed)
        m.fit(_numeric(x_tr), y_tr)
        imp, best = dict(zip(x_tr.columns, m.feature_importances_)), None
        score = lambda x: m.predict_proba(_numeric(x))[:, 1]
    elif kind == "lr":
        from sklearn.linear_model import LogisticRegression
        prep = LinearPrep().fit(x_tr)
        m = LogisticRegression(C=1.0, max_iter=2000)
        m.fit(prep.transform(x_tr), y_tr)
        imp, best = {}, None
        score = lambda x: m.predict_proba(prep.transform(x))[:, 1]
    else:
        raise ValueError(kind)
    return score(x_va), [score(x) for x in x_others], best, imp


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
    ap.add_argument("dataset", help="table name: raid, hikari, mta, mcfp, or a variant such as mta_sslbl")
    ap.add_argument("--tables", default="/data/tls-sok/tables")
    ap.add_argument("--out", default="/data/tls-sok/benchmark")
    ap.add_argument("--name", default=None, help="output folder name (default: dataset, plus _<model> if not xgb)")
    ap.add_argument("--model", default="xgb", choices=MODELS)
    ap.add_argument("--exps", default="E1,E2,E3")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--sets", default=None)
    a = ap.parse_args()

    out = Path(a.out) / (a.name or a.dataset + ("" if a.model == "xgb" else f"_{a.model}"))
    out.mkdir(parents=True, exist_ok=True)
    table = pd.read_parquet(f"{a.tables}/{a.dataset}.parquet")
    sets = (a.sets or ("g1g2,g1g2_notime" if a.dataset == "hikari" else "all,g1g2,g1g2_notime")).split(",")
    early = sorted({int(fs.split("_")[1]) for fs in sets if fs.startswith("early_")})
    table = pd.concat([table] + [early_features(table, n) for n in early], axis=1)
    rows, ver_rows, dedup_info, shortcut_rows, imp_rows = [], [], {}, [], []

    for fs in sets:
        cols = set_columns(table, fs)
        df, dedup_info[fs] = dedup(table, cols)
        print(fs, dedup_info[fs], flush=True)
        y = df["label"].values
        for exp in a.exps.split(","):
            for seed in range(a.seeds):
                sp = split(df, exp, a.dataset, seed)
                base = {"dataset": a.dataset, "model": a.model, "feature_set": fs, "experiment": exp, "seed": seed}
                if isinstance(sp, str):
                    rows.append({**base, "status": sp})
                    break
                tr, va, te = sp
                trb = balance(tr, y, seed)
                x_tr, (x_va, x_te) = to_model_matrix(feature_frame(df.iloc[trb], cols),
                                                     [feature_frame(df.iloc[va], cols), feature_frame(df.iloc[te], cols)])
                s_va, (s_te,), best, g = fit_predict(a.model, x_tr, y[trb], x_va, y[va], [x_te], seed, a.jobs)
                thr_f1, thr_fpr = thresholds(y[va], s_va)
                m = metrics(y[te], s_te, thr_f1, thr_fpr)
                ci = bootstrap(y[te], s_te, thr_f1, thr_fpr, a.boot, seed)
                rows.append({**base, "status": "ok", "n_features": len(cols), "n_train_balanced": len(trb),
                             "n_val": len(va), "best_iteration": best, "thr_f1": thr_f1, "thr_fpr": thr_fpr,
                             **m, **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                vers = df["k_tls_version"].values[te]
                for v in np.unique(vers):
                    i = vers == v
                    ver_rows.append({**base, "tls_version": v, **metrics(y[te][i], s_te[i], thr_f1, thr_fpr)})
                if seed == 0:
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
    by = ["dataset", "model", "feature_set", "experiment"]
    summ = ok.groupby(by, sort=False)[keys].agg(["mean", "std"]) if len(ok) else pd.DataFrame()
    if len(summ):
        summ.columns = [f"{k}_{s}" for k, s in summ.columns]
        summ = summ.reset_index()
    infeasible = res[res["status"] != "ok"][by + ["status"]].drop_duplicates()
    summ = pd.concat([summ, infeasible], ignore_index=True)
    summ.to_csv(out / "summary.csv", index=False)
    (out / "dedup.json").write_text(json.dumps(dedup_info, indent=2))
    print(summ.to_string())


if __name__ == "__main__":
    main()
