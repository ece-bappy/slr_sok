"""Batch 6 (runs on A2): robustness checks of the headline results, one subcommand per item.

Usage: python scripts/run_b6.py ITEM [--seeds N] [--jobs 24]
  seeds     (2) 20-seed reruns of the headline rows, predictions saved; paired Wilcoxon per G5 contrast
  baserate  (1) realistic base rates from the saved predictions (+ C-Cert, run here) at prevalence 1e-2..1e-4
  rolling   (3) rolling-origin MTA: train <= Y -> test Y+1, and 1- / 2-year training windows; with / without G5
  encoding  (4) fingerprint mechanism: hash categorical / train frequency / seen-in-train flag / decomposed
                handshake lists (multi-hot, no hash) / none
  ech       (5) ECH-padding tier: ClientHello-completing packet padded to a multiple of 32 (and 256)
  training  (6) dedup on/off x training class ratio 1:1 / natural / 1:10 benign-heavy
  family    (7) leave-one-family-out on MTA, families from pcap titles (single-family posts only)
  evasion   (8) test-time padding (+16/64/256 B per packet) and IAT jitter (x0.5-2) on malicious test flows
Protocol as in run_benchmark.py unless an item changes it on purpose: XGBoost defaults, per-feature-set dedup,
1:1 training balance, validation-only thresholds (max-F1, FPR 1e-3), bootstrap CIs. Outputs:
/data/tls-sok/benchmark/b6_<item>/ (CSVs) and /data/tls-sok/b6pred/ (saved test predictions, item 2).
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

from run_benchmark import (bootstrap, dedup, feature_frame, fit_predict, metrics, set_columns, split, thresholds,
                           to_model_matrix)

TABLES = "/data/tls-sok/tables"
BENCH = Path("/data/tls-sok/benchmark")
PRED = Path("/data/tls-sok/b6pred")
G5 = ["g5_ja3", "g5_ja3s", "g5_ja4", "g5_ja4s"]
_T = {}


def table(name: str) -> pd.DataFrame:
    if name not in _T:
        _T[name] = pd.read_parquet(f"{TABLES}/{name}.parquet")
    return _T[name]


def cols_for(names, fs):
    return sorted(set.intersection(*(set(set_columns(table(n), fs)) for n in names)))


_D = {}


def dd(name: str, cols: list) -> pd.DataFrame:
    """dedup() memoised per (table, feature columns): the same table is reused across seeds."""
    key = (name, tuple(cols))
    if key not in _D:
        if len(_D) > 6:
            _D.clear()
        _D[key] = dedup(table(name), cols)[0]
    return _D[key]


def sample(tr, y, seed, ratio="1:1"):
    """Training rows: 1:1 balance (protocol), natural, or 1:10 benign-heavy."""
    rng = np.random.default_rng(seed)
    pos, neg = tr[y[tr] == 1], tr[y[tr] == 0]
    if ratio == "natural":
        return tr
    if ratio == "1:1":
        n = min(len(pos), len(neg))
        return np.concatenate([rng.choice(pos, n, replace=False), rng.choice(neg, n, replace=False)])
    n_pos = min(len(pos), len(neg) // 10)  # 1:10 benign-heavy
    return np.concatenate([rng.choice(pos, n_pos, replace=False), rng.choice(neg, 10 * n_pos, replace=False)])


def fit_eval(train, test, tr, va, cols, seed, jobs, model="xgb", ratio="1:1", boot=200, extra=None, perturb=None):
    """Fit on train[tr] (sampled), thresholds on train[va], score test. Returns (row dict, s_te, thresholds)."""
    y = train["label"].to_numpy()
    trs = sample(tr, y, seed, ratio)
    xf = lambda d: feature_frame(d, cols)
    te = test if perturb is None else perturb(test)
    x_tr, (x_va, x_te) = to_model_matrix(xf(train.iloc[trs]), [xf(train.iloc[va]), xf(te)])
    if extra is not None:  # extra numeric columns computed from the training rows only
        x_tr, x_va, x_te = extra(train.iloc[tr], train.iloc[trs], x_tr), extra(train.iloc[tr], train.iloc[va], x_va), \
            extra(train.iloc[tr], te, x_te)
    s_va, (s_te,), it, _ = fit_predict(model, x_tr, y[trs], x_va, y[va], [x_te], seed, jobs)
    thr_f1, thr_fpr = thresholds(y[va], s_va)
    y_te = te["label"].to_numpy()
    m = metrics(y_te, s_te, thr_f1, thr_fpr)
    ci = bootstrap(y_te, s_te, thr_f1, thr_fpr, boot if len(y_te) <= 200_000 else 20, seed) if boot else {}
    return ({**m, "n_train": len(trs), **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}},
            s_te, (thr_f1, thr_fpr))


def scenario(name, fs, seed):
    """(train, test, tr, va, cols) for the headline settings, each deduplicated on its own feature set."""
    if name == "mta_e3":
        cols = set_columns(table("mta"), fs)
        d = dd("mta", cols)
        tr, va, te = split(d, "E3", "mta", seed)
        return d, d.iloc[te].reset_index(drop=True), tr, va, cols
    if name in ("mcfp>mta", "mcfp>mta_new"):
        cols = cols_for(["mcfp", "mta"], fs)
        src, dst = dd("mcfp", cols), dd("mta", cols)
        if name == "mcfp>mta_new":
            dst = dst[dst["k_year"].astype(str) > "2022"]
        tr, va = train_test_split(np.arange(len(src)), test_size=0.15, stratify=src["label"], random_state=seed)
        return src, dst.reset_index(drop=True), tr, va, cols
    raise ValueError(name)


def e9_cols(fs):
    """run_e9 feature sets (restricted to columns present in both MTA and MCFP)."""
    base = [c for c in cols_for(["mta", "mcfp"], "all") if not c.startswith("g5_")]
    return {"no_fp": base, "fp_ja3": base + ["g5_ja3", "g5_ja3s"], "fp_ja4": base + ["g5_ja4", "g5_ja4s"],
            "fp_both": base + G5}[fs]


def e9_scenario(name, fs, seed):
    cols = e9_cols(fs)
    mta = dd("mta", cols)
    if name == "mta_old>mta_new":
        tr, va, te = split(mta, "E3", "mta", seed)
        return mta, mta.iloc[te].reset_index(drop=True), tr, va, cols
    src = dd("mcfp", cols)
    tr, va = train_test_split(np.arange(len(src)), test_size=0.15, stratify=src["label"], random_state=seed)
    return src, mta[mta["k_year"].astype(str) > "2022"].reset_index(drop=True), tr, va, cols


# ------------------------------------------------------------------ item 2: seeds
SEED_RUNS = ([("mta_e3", fs, m) for fs in ("all", "loo_g5") for m in ("xgb", "lgbm", "rf")] +
             [("mta_e3", "g1g2g3", "xgb")] +
             [("mcfp>mta", fs, m) for fs in ("all_notime", "loo_g5_notime", "all", "loo_g5") for m in ("xgb", "lgbm", "rf")] +
             [(sc, fs, "xgb") for sc in ("e9:mta_old>mta_new", "e9:mcfp>mta_new") for fs in ("no_fp", "fp_ja3", "fp_ja4", "fp_both")])
CONTRASTS = ([("mta_e3", "all", "loo_g5", m) for m in ("xgb", "lgbm", "rf")] +
             [("mcfp>mta", a, b, m) for a, b in (("all_notime", "loo_g5_notime"), ("all", "loo_g5")) for m in ("xgb", "lgbm", "rf")] +
             [(sc, f, "no_fp", "xgb") for sc in ("e9:mta_old>mta_new", "e9:mcfp>mta_new") for f in ("fp_ja3", "fp_ja4", "fp_both")])


def item_seeds(a):
    from scipy.stats import wilcoxon
    out = BENCH / "b6_seeds"
    out.mkdir(parents=True, exist_ok=True)
    PRED.mkdir(parents=True, exist_ok=True)
    path = out / "results_per_seed.csv"
    rows = pd.read_csv(path).to_dict("records") if path.exists() else []
    done = {(r["setting"], r["feature_set"], r["model"], r["seed"]) for r in rows}
    for sc, fs, model in SEED_RUNS:
        for seed in range(a.seeds):
            if (sc, fs, model, seed) in done:
                continue
            train, test, tr, va, cols = (e9_scenario(sc[3:], fs, seed) if sc.startswith("e9:") else scenario(sc, fs, seed))
            r, s_te, thr = fit_eval(train, test, tr, va, cols, seed, a.jobs, model, boot=50)
            rows.append({"setting": sc, "feature_set": fs, "model": model, "seed": seed, **r})
            np.savez_compressed(PRED / f"{sc.replace(':', '_').replace('>', '-')}__{fs}__{model}__{seed}.npz",
                                y=test["label"].to_numpy().astype(np.int8), s=s_te.astype(np.float32),
                                thr=np.array(thr), tls=test["k_tls_version"].astype(str).to_numpy())
            print(sc, fs, model, seed, round(r["pr_auc"], 4), flush=True)
            pd.DataFrame(rows).to_csv(path, index=False)
    res = pd.DataFrame(rows)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "test_fpr_at_that_threshold"]
    summ = res.groupby(["setting", "feature_set", "model"], sort=False)[keys].agg(["mean", "std", "count"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    tests = []
    for sc, f_with, f_without, model in CONTRASTS:
        g = res[(res.setting == sc) & (res.model == model)].set_index(["feature_set", "seed"])
        for metric in ("pr_auc", "macro_f1"):
            a_, b_ = g.loc[f_with][metric], g.loc[f_without][metric]
            idx = a_.index.intersection(b_.index)
            d = (b_.loc[idx] - a_.loc[idx]).to_numpy()
            p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
            tests.append({"setting": sc, "model": model, "with": f_with, "without": f_without, "metric": metric,
                          "n_seeds": len(d), "mean_with": a_.loc[idx].mean(), "mean_without": b_.loc[idx].mean(),
                          "mean_diff_without_minus_with": d.mean(), "sd_diff": d.std(ddof=1),
                          "wins_without": int((d > 0).sum()), "wilcoxon_p": p})
    pd.DataFrame(tests).to_csv(out / "paired_tests.csv", index=False)
    print(pd.DataFrame(tests).to_string())


# ------------------------------------------------------------------ item 1: base rates
def reweighted(y, s, thr, pi):
    """Metrics with the benign class reweighted so that the malicious share is pi (malicious weight 1)."""
    n1, n0 = (y == 1).sum(), (y == 0).sum()
    w0 = n1 * (1 - pi) / (pi * n0)
    w = np.where(y == 1, 1.0, w0)
    out = {"pr_auc": average_precision_score(y, s, sample_weight=w), "roc_auc": roc_auc_score(y, s)}
    for name, t in (("valF1", thr[0]), ("valFPR1e-3", thr[1])):
        p = s >= t
        tp, fp = (p & (y == 1)).sum(), (p & (y == 0)).sum()
        out[f"recall@{name}"] = tp / n1
        out[f"precision@{name}"] = tp / (tp + w0 * fp) if tp + fp else np.nan
        out[f"false_alarms_per_10k_benign@{name}"] = 1e4 * fp / n0
    return out


def c_cert_predictions(seeds, jobs):
    """C-Cert RF/DT on MTA E3 and MCFP -> MTA with saved predictions (r24_benchmark's setup, 20 seeds)."""
    import r24_benchmark as rb
    diffs = rb.diff_list()
    j = {ds: pd.read_parquet(BENCH / "r24_protocol" / f"joined_{ds}.parquet") for ds in ("mta", "mcfp")}
    for kind in ("c_cert_rf", "c_cert_dt"):
        for sc in ("mta_e3", "mcfp>mta"):
            for seed in range(seeds):
                f = PRED / f"{sc.replace('>', '-')}__c_cert__{kind}__{seed}.npz"
                if f.exists():
                    continue
                mta = j["mta"][j["mta"]["r24_cert_ok"]].reset_index(drop=True)
                if sc == "mta_e3":
                    train = mta
                    tr, va, te = split(train, "E3", "mta", seed)
                    test = train.iloc[te]
                else:
                    train, test = j["mcfp"][j["mcfp"]["r24_cert_ok"]].reset_index(drop=True), mta
                    tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=train["label"],
                                              random_state=seed)
                y = train["label"].to_numpy()
                trb = sample(tr, y, seed)
                xa, ya = rb.augment(kind, train.iloc[trb][["r24_cert_len"]].to_numpy(float), y[trb],
                                    np.random.default_rng(seed), diffs)
                m = rb.model(kind, seed).fit(xa, ya)
                s_va = m.predict_proba(train.iloc[va][["r24_cert_len"]].to_numpy(float))[:, 1]
                s_te = m.predict_proba(test[["r24_cert_len"]].to_numpy(float))[:, 1]
                np.savez_compressed(f, y=test["label"].to_numpy().astype(np.int8), s=s_te.astype(np.float32),
                                    thr=np.array(thresholds(y[va], s_va)),
                                    tls=test["k_tls_version"].astype(str).to_numpy())


def item_baserate(a):
    out = BENCH / "b6_baserate"
    out.mkdir(parents=True, exist_ok=True)
    c_cert_predictions(a.seeds, a.jobs)
    want = [("mta_e3", fs, "xgb") for fs in ("all", "loo_g5", "g1g2g3")] + \
           [("mcfp-mta", fs, "xgb") for fs in ("all_notime", "loo_g5_notime")] + \
           [(sc, "c_cert", k) for sc in ("mta_e3", "mcfp-mta") for k in ("c_cert_rf", "c_cert_dt")]
    rows = []
    for sc, fs, model in want:
        for f in sorted(glob.glob(str(PRED / f"{sc}__{fs}__{model}__*.npz"))):
            z = np.load(f, allow_pickle=True)
            y, s, thr = z["y"], z["s"].astype(float), z["thr"]
            seed = int(Path(f).stem.split("__")[-1])
            base = {"setting": sc, "feature_set": fs, "model": model, "seed": seed,
                    "test_prevalence": y.mean(), "n_test": len(y)}
            rows.append({**base, "prevalence": "as tested", **reweighted(y, s, thr, y.mean())})
            for pi in (1e-2, 1e-3, 1e-4):
                rows.append({**base, "prevalence": pi, **reweighted(y, s, thr, pi)})
    res = pd.DataFrame(rows)
    res.to_csv(out / "results_per_seed.csv", index=False)
    keys = [c for c in res.columns if c.startswith(("pr_auc", "roc_auc", "recall@", "precision@", "false_alarms"))]
    summ = res.groupby(["setting", "feature_set", "model", "prevalence"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


# ------------------------------------------------------------------ item 3: rolling origin
def item_rolling(a):
    out = BENCH / "b6_rolling"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for fs in ("all", "loo_g5"):
        cols = set_columns(table("mta"), fs)
        d = dedup(table("mta"), cols)[0]
        yr = d["k_year"].astype(str).to_numpy()
        idx = np.arange(len(d))
        for test_year in range(2020, 2027):
            for window in ("expanding", "1y", "2y"):
                lo = {"expanding": 0, "1y": test_year - 1, "2y": test_year - 2}[window]
                old = idx[(yr >= str(lo)) & (yr <= str(test_year - 1)) & (yr != "unknown")]
                new = idx[yr == str(test_year)]
                y = d["label"].to_numpy()
                if min(len(np.unique(y[old])), len(np.unique(y[new]))) < 2:
                    continue
                old = old[np.argsort(d["k_first_seen_ms"].to_numpy()[old])]
                cut = int(len(old) * 0.85)
                tr, va = old[:cut], old[cut:]
                if len(np.unique(y[va])) < 2 or len(np.unique(y[tr])) < 2:
                    tr, va = train_test_split(old, test_size=0.15, stratify=y[old], random_state=0)
                for seed in range(a.seeds):
                    r, _, _ = fit_eval(d, d.iloc[new].reset_index(drop=True), tr, va, cols, seed, a.jobs, boot=100)
                    rows.append({"feature_set": fs, "window": window, "test_year": test_year,
                                 "train_years": f"{max(lo, 2019)}-{test_year - 1}", "n_train_rows": len(tr),
                                 "seed": seed, **r})
                    print(fs, window, test_year, seed, round(r["pr_auc"], 4), flush=True)
                pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    res = pd.DataFrame(rows)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "test_fpr_at_that_threshold", "n", "n_pos"]
    summ = res.groupby(["feature_set", "window", "test_year"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


def rolling_splits(d, windows=("expanding", "2y")):
    """(test_year, window, train_years, tr, va, test_idx) for the rolling-origin setup of item 3."""
    yr = d["k_year"].astype(str).to_numpy()
    y = d["label"].to_numpy()
    idx = np.arange(len(d))
    for test_year in range(2020, 2027):
        for window in windows:
            lo = {"expanding": 0, "1y": test_year - 1, "2y": test_year - 2}[window]
            old = idx[(yr >= str(lo)) & (yr <= str(test_year - 1)) & (yr != "unknown")]
            new = idx[yr == str(test_year)]
            if min(len(np.unique(y[old])), len(np.unique(y[new]))) < 2:
                continue
            old = old[np.argsort(d["k_first_seen_ms"].to_numpy()[old])]
            cut = int(len(old) * 0.85)
            tr, va = old[:cut], old[cut:]
            if len(np.unique(y[va])) < 2 or len(np.unique(y[tr])) < 2:
                tr, va = train_test_split(old, test_size=0.15, stratify=y[old], random_state=0)
            yield test_year, window, f"{max(lo, 2019)}-{test_year - 1}", tr, va, new


def summarise(rows, out, by, keys=("pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign",
                                    "test_fpr_at_that_threshold", "n", "n_pos")):
    res = pd.DataFrame(rows)
    res.to_csv(out / "results_per_seed.csv", index=False)
    summ = res.groupby(by, sort=False)[list(keys)].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    return summ


def item_rolling_models(a):
    """3b: the rolling-origin curve for LightGBM and RF (all past years and last 2 years, with / without G5)."""
    out = BENCH / "b6_rolling_models"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for fs in ("all", "loo_g5"):
        cols = set_columns(table("mta"), fs)
        d = dd("mta", cols)
        for test_year, window, years, tr, va, new in rolling_splits(d):
            for model in ("lgbm", "rf"):
                for seed in range(a.seeds):
                    r, _, _ = fit_eval(d, d.iloc[new].reset_index(drop=True), tr, va, cols, seed, a.jobs, model, boot=100)
                    rows.append({"model": model, "feature_set": fs, "window": window, "test_year": test_year,
                                 "train_years": years, "seed": seed, **r})
                    print(model, fs, window, test_year, seed, round(r["pr_auc"], 4), flush=True)
            summarise(rows, out, ["model", "feature_set", "window", "test_year"])
    print(summarise(rows, out, ["model", "feature_set", "window", "test_year"]).to_string())


def item_rolling_enc(a):
    """3c: the rolling-origin curve with the fingerprint encodings of item 4 (XGBoost): (a) hash categorical,
    (b) training frequency, (c) seen-in-training flag, (e) none. Same rows for every encoding (dedup on G1-G5)."""
    out = BENCH / "b6_rolling_enc"
    out.mkdir(parents=True, exist_ok=True)
    cols = set_columns(table("mta"), "all")
    d = dd("mta", cols)
    nog5 = [c for c in cols if c not in G5]
    enc = {"a_hash_categorical": (cols, None), "b_frequency": (cols, enc_extra("freq")),
           "c_seen_flag": (cols, enc_extra("seen")), "e_none": (nog5, None)}
    rows = []
    for test_year, window, years, tr, va, new in rolling_splits(d):
        for name, (use, ex) in enc.items():
            for seed in range(a.seeds):
                r, _, _ = fit_eval(d, d.iloc[new].reset_index(drop=True), tr, va, use, seed, a.jobs, extra=ex, boot=100)
                rows.append({"encoding": name, "window": window, "test_year": test_year, "train_years": years,
                             "seed": seed, **r})
                print(name, window, test_year, seed, round(r["pr_auc"], 4), flush=True)
        summarise(rows, out, ["encoding", "window", "test_year"])
    print(summarise(rows, out, ["encoding", "window", "test_year"]).to_string())


def item_post2026(a):
    """Which 2026 posts / families drive the G5 model's below-chance ROC (all past years, XGBoost)? Scores are
    averaged over seeds; per post: size, malicious share, mean score per class, and the overall ROC-AUC when
    that post is left out of the test set (its influence)."""
    out = BENCH / "b6_post2026"
    out.mkdir(parents=True, exist_ok=True)
    fam = pd.read_csv(BENCH / "b6_family" / "pcap_family.csv").set_index("k_pcap")["family"] \
        if (BENCH / "b6_family" / "pcap_family.csv").exists() else pd.Series(dtype=str)
    if fam.empty:  # item 7 not run yet: derive the title families here
        t = table("mta")
        fam = pd.Series({p: family_of(Path(p).name) for p in t["k_pcap"].unique()})
    summ = []
    for fs in ("all", "loo_g5"):
        cols = set_columns(table("mta"), fs)
        d = dd("mta", cols)
        sp = [s for s in rolling_splits(d, ("expanding",)) if s[0] == 2026][0]
        _, _, _, tr, va, new = sp
        test = d.iloc[new].reset_index(drop=True)
        s = np.mean([fit_eval(d, test, tr, va, cols, seed, a.jobs, boot=0)[1] for seed in range(a.seeds)], axis=0)
        y = test["label"].to_numpy()
        test = test.assign(score=s, family=test["k_pcap"].map(fam).fillna("unknown"))
        overall = roc_auc_score(y, s)
        for key in ("k_post", "family"):
            for g, part in test.groupby(key):
                rest = test[test[key] != g]
                summ.append({"feature_set": fs, "group_by": key, "group": g, "n": len(part), "n_malicious": int(part.label.sum()),
                             "mean_score_malicious": part.loc[part.label == 1, "score"].mean(),
                             "mean_score_benign": part.loc[part.label == 0, "score"].mean(),
                             "roc_auc_within": roc_auc_score(part.label, part.score) if part.label.nunique() == 2 else np.nan,
                             "roc_auc_all": overall,
                             "roc_auc_without_this_group": roc_auc_score(rest.label, rest.score) if rest.label.nunique() == 2 else np.nan})
        test[["k_post", "k_pcap", "family", "label", "k_tls_version", "score"]].to_csv(out / f"scores_{fs}.csv", index=False)
    res = pd.DataFrame(summ)
    res["influence"] = res["roc_auc_without_this_group"] - res["roc_auc_all"]
    res.sort_values(["feature_set", "group_by", "influence"], ascending=[True, True, False]).to_csv(out / "breakdown.csv", index=False)
    print(res.sort_values("influence", ascending=False).head(30).to_string())


# ------------------------------------------------------------------ item 4: fingerprint encodings
LISTS = ["tls_ch_cipher_suites", "tls_ch_extension_types", "tls_ch_supported_groups", "tls_ch_signature_algorithms",
         "tls_ch_ec_point_formats", "tls_sh_extension_types"]


def raw_lists(ds: str) -> pd.DataFrame:
    """Raw ClientHello/ServerHello lists from the per-pcap flows.parquet, aligned to the table rows."""
    cache = Path(f"/data/tls-sok/b6/lists_{ds}.parquet")
    if cache.exists():
        return pd.read_parquet(cache)
    t = table(ds)
    parts = []
    for p in t["k_pcap"].unique():
        f = Path(f"/data/tls-sok/out/{ds}/{p}/flows.parquet")
        if not f.exists():
            continue
        x = pd.read_parquet(f, columns=["src_ip", "src_port", "dst_ip", "dst_port", "bidirectional_first_seen_ms",
                                        "tls_ja3"] + LISTS)
        x = x[x["tls_ja3"].notna()].drop(columns="tls_ja3")
        x["k_pcap"] = p
        parts.append(x)
    r = pd.concat(parts, ignore_index=True).rename(columns={
        "src_ip": "k_client_ip", "src_port": "k_client_port", "dst_ip": "k_server_ip", "dst_port": "k_server_port",
        "bidirectional_first_seen_ms": "k_first_seen_ms"})
    for c in ("k_client_port", "k_server_port", "k_first_seen_ms"):
        r[c] = r[c].astype("int64")
    r["k_client_ip"], r["k_server_ip"] = r["k_client_ip"].astype(str), r["k_server_ip"].astype(str)
    key = ["k_pcap", "k_client_ip", "k_client_port", "k_server_ip", "k_server_port", "k_first_seen_ms"]
    m = t[key].reset_index().merge(r.drop_duplicates(key), on=key, how="left").set_index("index").sort_index()
    m = m[LISTS]
    for c in LISTS:  # lists as ' '-joined strings (GREASE removed), so parquet round-trips simply
        m[c] = m[c].map(lambda v: " ".join(str(int(x)) for x in v if (int(x) & 0x0F0F) != 0x0A0A)
                        if v is not None and not (isinstance(v, float)) else "")
    cache.parent.mkdir(parents=True, exist_ok=True)
    m.to_parquet(cache)
    return m


def enc_extra(kind):
    """Extra numeric columns built from the training rows only (frequency, seen flag, multi-hot)."""
    def f(train_rows, rows, x):
        x = x.drop(columns=[c for c in x.columns if c in G5])
        if kind in ("freq", "seen"):
            for c in G5:
                vc = train_rows[c].fillna("").astype(str).value_counts(normalize=True)
                v = rows[c].fillna("").astype(str).map(vc).fillna(0.0).to_numpy()
                x[f"{c}_{kind}"] = v if kind == "freq" else (v > 0).astype(float)
        if kind == "decomposed":  # multi-hot over the 64 most frequent training values of each list, plus length
            import warnings
            from sklearn.preprocessing import MultiLabelBinarizer
            for c in LISTS:
                vocab = list(train_rows[c].fillna("").str.split().explode().dropna().value_counts().index[:64])
                tok = rows[c].fillna("").str.split()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")  # values outside the vocabulary are dropped on purpose
                    mh = MultiLabelBinarizer(classes=vocab).fit([vocab]).transform(tok).astype(np.float32)
                x = pd.concat([x, pd.DataFrame(mh, columns=[f"{c}={v}" for v in vocab], index=x.index)], axis=1)
                x[f"{c}_n"] = tok.str.len().to_numpy(float)
        return x
    return f


def item_encoding(a):
    out = BENCH / "b6_encoding"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for sc in ("mta_e3", "mcfp>mta"):
        fs = "all" if sc == "mta_e3" else "all_notime"
        names = ["mta"] if sc == "mta_e3" else ["mcfp", "mta"]
        cols = cols_for(names, fs)
        d = {}
        for n in names:  # same rows for every encoding: lists attached, then dedup on the full `all` vector
            lst = raw_lists(n)
            d[n] = dedup(table(n).assign(**{c: lst[c].to_numpy() for c in LISTS}), cols)[0]
        for seed in range(a.seeds):
            if sc == "mta_e3":
                tr, va, te = split(d["mta"], "E3", "mta", seed)
                train, test = d["mta"], d["mta"].iloc[te].reset_index(drop=True)
            else:
                train, test = d["mcfp"], d["mta"]
                tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=train["label"], random_state=seed)
            for enc in ("a_hash_categorical", "b_frequency", "c_seen_flag", "d_decomposed_lists", "e_none"):
                use = cols if enc == "a_hash_categorical" else [c for c in cols if c not in G5]
                if enc in ("b_frequency", "c_seen_flag"):
                    use = use + G5  # raw hashes are passed in and replaced by enc_extra
                ex = {"b_frequency": enc_extra("freq"), "c_seen_flag": enc_extra("seen"),
                      "d_decomposed_lists": enc_extra("decomposed")}.get(enc)
                if enc == "d_decomposed_lists":
                    use = use + LISTS
                    ex0 = ex
                    ex = lambda trr, rr, x, ex0=ex0: ex0(trr, rr, x.drop(columns=[c for c in LISTS if c in x.columns]))
                r, _, _ = fit_eval(train, test, tr, va, use, seed, a.jobs, extra=ex)
                rows.append({"setting": sc, "encoding": enc, "seed": seed, **r})
                print(sc, enc, seed, round(r["pr_auc"], 4), flush=True)
                pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    res = pd.DataFrame(rows)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "test_fpr_at_that_threshold"]
    summ = res.groupby(["setting", "encoding"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


# ------------------------------------------------------------------ item 5: ECH padding
SIZE_G1 = re.compile(r"_(bytes|min_ps|mean_ps|stddev_ps|max_ps)$")


def pad_ch(df, q):
    """Round the ClientHello-completing packet's size up to a multiple of q (G2 column g2_ps_{k_pkt_ch-1})."""
    df = df.copy()
    k = df["k_pkt_ch"].fillna(0).astype(int).to_numpy() - 1
    for i in range(20):
        c = f"g2_ps_{i:02d}"
        hit = (k == i) & (df[c].to_numpy() > 0)
        v = df[c].to_numpy(float)
        df[c] = np.where(hit, np.ceil(v / q) * q, v)
    return df


def item_ech(a):
    out = BENCH / "b6_ech"
    out.mkdir(parents=True, exist_ok=True)
    t = table("mta")
    g12 = set_columns(t, "tier_tls13_ech")
    nosize = [c for c in g12 if not (c.startswith("g1_") and SIZE_G1.search(c))]
    variants = {"ech_G1G2": (g12, None), "ech_nosizeG1": (nosize, None), "ech_nosizeG1_pad32": (nosize, 32),
                "ech_nosizeG1_pad256": (nosize, 256)}
    rows, ver = [], []
    for name, (cols, q) in variants.items():
        d = t if q is None else pad_ch(t, q)
        d = dedup(d, cols)[0]  # padding can merge vectors, so dedup after padding
        for seed in range(a.seeds):
            tr, va, te = split(d, "E3", "mta", seed)
            test = d.iloc[te].reset_index(drop=True)
            r, s_te, thr = fit_eval(d, test, tr, va, cols, seed, a.jobs)
            rows.append({"variant": name, "pad_to": q or 0, "seed": seed, **r})
            v = test["k_tls_version"].astype(str).to_numpy()
            y = test["label"].to_numpy()
            for tv in ("1.2", "1.3"):
                i = v == tv
                ver.append({"variant": name, "seed": seed, "tls_version": tv, **metrics(y[i], s_te[i], *thr)})
            print(name, seed, round(r["pr_auc"], 4), flush=True)
    pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    pd.DataFrame(ver).to_csv(out / "results_per_tls_version.csv", index=False)
    for nm, res, by in (("summary.csv", pd.DataFrame(rows), ["variant"]),
                        ("summary_per_tls_version.csv", pd.DataFrame(ver), ["variant", "tls_version"])):
        k = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "n", "n_pos"]
        s = res.groupby(by, sort=False)[k].agg(["mean", "std"])
        s.columns = [f"{a_}_{b_}" for a_, b_ in s.columns]
        s.reset_index().to_csv(out / nm, index=False)
        print(s.to_string())


# ------------------------------------------------------------------ item 6: training-set sensitivity
def item_training(a):
    out = BENCH / "b6_training"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for sc, fs in (("mta_e3", "all"), ("mta_e3", "loo_g5"), ("mcfp>mta", "all_notime"), ("mcfp>mta", "loo_g5_notime")):
        for dd in ("dedup", "no_dedup"):
            for seed in range(a.seeds):
                names = ["mta"] if sc == "mta_e3" else ["mcfp", "mta"]
                cols = cols_for(names, fs)
                dt = {n: (dedup(table(n), cols)[0] if dd == "dedup" else table(n).reset_index(drop=True)) for n in names}
                if sc == "mta_e3":
                    tr, va, te = split(dt["mta"], "E3", "mta", seed)
                    train, test = dt["mta"], dt["mta"].iloc[te].reset_index(drop=True)
                else:
                    train, test = dt["mcfp"], dt["mta"]
                    tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=train["label"], random_state=seed)
                for ratio in ("1:1", "natural", "1:10"):
                    r, _, _ = fit_eval(train, test, tr, va, cols, seed, a.jobs, ratio=ratio)
                    rows.append({"setting": sc, "feature_set": fs, "dedup": dd, "ratio": ratio, "seed": seed, **r})
                    print(sc, fs, dd, ratio, seed, round(r["pr_auc"], 4), flush=True)
                pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    res = pd.DataFrame(rows)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "test_fpr_at_that_threshold", "n_train", "n"]
    summ = res.groupby(["setting", "feature_set", "dedup", "ratio"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


# ------------------------------------------------------------------ item 7: leave-one-family-out
FAMILIES = {  # canonical name: title tokens (case-insensitive, matched on word boundaries in the pcap title)
    "Emotet": ["emotet"], "Trickbot": ["trickbot"], "Qakbot": ["qakbot", "qbot", "quakbot"], "IcedID": ["icedid", "bokbot"],
    "Dridex": ["dridex"], "AgentTesla": ["agenttesla", "agent-tesla"], "Formbook": ["formbook", "xloader"],
    "Lokibot": ["lokibot"], "Hancitor": ["hancitor", "chanitor"], "Ursnif": ["ursnif", "gozi", "isfb"],
    "NetSupport": ["netsupport"], "AsyncRAT": ["asyncrat"], "Remcos": ["remcos"], "BazarLoader": ["bazarloader", "bazar", "bazarbackdoor"],
    "Bumblebee": ["bumblebee"], "CobaltStrike": ["cobalt-strike", "cobaltstrike"], "SocGholish": ["socgholish", "fakeupdates", "fake-updates"],
    "NanoCore": ["nanocore"], "njRAT": ["njrat"], "Raccoon": ["raccoon"], "RedLine": ["redline"], "Vidar": ["vidar"],
    "StealC": ["stealc"], "Lumma": ["lumma", "lummastealer", "lummac"], "Pikabot": ["pikabot"], "DarkGate": ["darkgate"],
    "SmokeLoader": ["smokeloader", "smoke-loader"], "ZLoader": ["zloader"], "GuLoader": ["guloader"],
    "Gootloader": ["gootloader"], "Koi": ["koi-loader", "koiloader", "koi"], "Latrodectus": ["latrodectus"],
    "WarmCookie": ["warmcookie"], "Matanbuchus": ["matanbuchus"], "Rhadamanthys": ["rhadamanthys"], "SSLoad": ["ssload"],
    "AZORult": ["azorult"], "Valak": ["valak"], "Snake": ["snake-keylogger", "snakekeylogger"], "Oski": ["oski"],
    "STRRAT": ["strrat"], "Kongtuke": ["kongtuke"], "ClickFix": ["clickfix"],
}


def family_of(title: str):
    t = title.lower()
    hits = {f for f, toks in FAMILIES.items() if any(re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", t) for k in toks)}
    return hits.pop() if len(hits) == 1 else ("ambiguous" if hits else "unknown")


def item_family_models(a):
    """7b: leave-one-family-out for LightGBM and RF (same labels, held-out families and splits as item 7)."""
    item_family(a, models=("lgbm", "rf"), out_name="b6_family_models")


def item_tls13(a):
    """9: is MTA E3 detection on TLS 1.3 flows near chance whatever the features? (a) per-version ROC/PR/prevalence
    for every reported feature set; (b) TLS 1.3 share by split, class and year; (c) train on one TLS version only,
    test on it; (d) per-post / per-family breakdown within each version; (e) TLS 1.2 as the contrast."""
    out = BENCH / "b6_tls13"
    out.mkdir(parents=True, exist_ok=True)
    t = table("mta")
    fam = pd.Series({p: family_of(Path(p).name) for p in t["k_pcap"].unique()})
    # (b) shares, on the `all`-deduplicated table that E3 uses
    d_all = dd("mta", set_columns(t, "all"))
    ver = d_all["k_tls_version"].astype(str)
    period = np.where(d_all["k_year"].astype(str) <= "2022", "train (<=2022)", "test (2023-26)")
    share = (pd.crosstab([period, d_all["k_year"], d_all["label"]], ver, normalize="index").round(4)
             .join(pd.crosstab([period, d_all["k_year"], d_all["label"]], ver).sum(axis=1).rename("n")))
    share.to_csv(out / "tls_share_by_year_class.csv")
    pd.crosstab([period, d_all["label"]], ver, normalize="index").round(4).to_csv(out / "tls_share_by_split_class.csv")
    rows, brk = [], []
    for fs in ("all", "loo_g5", "g1g2", "g1g2_notime", "g1g2g3"):
        cols = set_columns(t, fs)
        d = dd("mta", cols)
        v = d["k_tls_version"].astype(str).to_numpy()
        for train_on in ("all versions", "1.3 only", "1.2 only"):
            for seed in range(a.seeds):
                tr, va, te = split(d, "E3", "mta", seed)
                if train_on != "all versions":
                    keep = train_on.split()[0]
                    tr, va = tr[v[tr] == keep], va[v[va] == keep]
                    lab = d["label"].to_numpy()
                    if min(len(np.unique(lab[tr])), len(np.unique(lab[va]))) < 2:
                        print("skip", fs, train_on, "(one class in train or validation)", flush=True)
                        break
                test = d.iloc[te].reset_index(drop=True)
                _, s_te, thr = fit_eval(d, test, tr, va, cols, seed, a.jobs, boot=0)
                y, tv = test["label"].to_numpy(), test["k_tls_version"].astype(str).to_numpy()
                for sub in ("1.2", "1.3", "all"):
                    i = np.ones(len(y), bool) if sub == "all" else tv == sub
                    if train_on != "all versions" and sub not in (train_on.split()[0], "all"):
                        continue
                    m = metrics(y[i], s_te[i], *thr)
                    rows.append({"feature_set": fs, "train_on": train_on, "test_subset": sub, "seed": seed,
                                 "prevalence": y[i].mean(), **m})
                if train_on == "all versions" and fs in ("all", "loo_g5") and seed == 0:
                    tt = test.assign(score=s_te, family=test["k_pcap"].map(fam).fillna("unknown"))
                    for sub in ("1.2", "1.3"):
                        part = tt[tv == sub]
                        for key in ("k_post", "family"):
                            for g, p in part.groupby(key):
                                rest = part[part[key] != g]
                                brk.append({"feature_set": fs, "tls_version": sub, "group_by": key, "group": g,
                                            "n": len(p), "n_malicious": int(p.label.sum()),
                                            "roc_within": roc_auc_score(p.label, p.score) if p.label.nunique() == 2 else np.nan,
                                            "roc_subset": roc_auc_score(part.label, part.score),
                                            "roc_subset_without_group": roc_auc_score(rest.label, rest.score)
                                            if rest.label.nunique() == 2 else np.nan})
                print(fs, train_on, seed, flush=True)
        summarise(rows, out, ["feature_set", "train_on", "test_subset"],
                  ("roc_auc", "pr_auc", "prevalence", "macro_f1", "recall_malicious", "recall_benign", "n", "n_pos"))
    b = pd.DataFrame(brk)
    b["influence"] = b["roc_subset_without_group"] - b["roc_subset"]
    b.sort_values(["feature_set", "tls_version", "group_by", "influence"]).to_csv(out / "breakdown.csv", index=False)
    print(pd.read_csv(out / "summary.csv").to_string())


def item_family(a, models=("xgb",), out_name="b6_family"):
    out = BENCH / out_name
    out.mkdir(parents=True, exist_ok=True)
    t = table("mta")
    # one label per pcap (a post folder can hold several infections); titles naming 2+ families are ambiguous
    mal_pcaps = t.loc[t["label"] == 1, "k_pcap"].unique()
    pc = t.loc[t["k_pcap"].isin(mal_pcaps), ["k_post", "k_pcap"]].drop_duplicates()
    pc["family"] = pc["k_pcap"].map(lambda p: family_of(Path(p).name))
    pc.to_csv(out / "pcap_family.csv", index=False)
    known = pc[~pc["family"].isin(["unknown", "ambiguous"])]
    counts = known.groupby("family")["k_post"].nunique().sort_values(ascending=False)
    (out / "family_labels.json").write_text(json.dumps({
        "pcaps_with_malicious_flows": int(len(pc)), "by_status": pc["family"].where(
            pc["family"].isin(["unknown", "ambiguous"]), "single family").value_counts().to_dict(),
        "posts_per_family": counts.to_dict()}, indent=2))
    print(pc["family"].value_counts().head(40).to_string())
    fams = [f for f, n in counts.items() if n >= a.min_posts]
    print("held-out families (>= %d posts):" % a.min_posts, fams, flush=True)
    fam_of_pcap = known.set_index("k_pcap")["family"]
    rows = []
    for fs in ("all", "loo_g5"):
        cols = set_columns(t, fs)
        d = dedup(t, cols)[0]
        fam = d["k_pcap"].map(fam_of_pcap)  # NaN: unknown / ambiguous / benign-only pcaps -> not used
        for f_out in fams:
            f_posts = known.loc[known["family"] == f_out, "k_post"].unique()
            test = d[fam == f_out].reset_index(drop=True)
            rest = d[fam.notna() & (fam != f_out) & ~d["k_post"].isin(f_posts)].reset_index(drop=True)
            fam_name = f_out
            if len(test) == 0 or test["label"].nunique() < 2 or rest["label"].nunique() < 2:
                print("skip", f_out, "(one class only)", flush=True)
                continue
            for model in models:
                for seed in range(a.seeds):
                    tr, va = train_test_split(np.arange(len(rest)), test_size=0.15, stratify=rest["label"], random_state=seed)
                    r, s_te, thr = fit_eval(rest, test, tr, va, cols, seed, a.jobs, model, boot=100)
                    rows.append({"model": model, "feature_set": fs, "family": fam_name, "n_posts": int(counts[fam_name]),
                                 "seed": seed, **r})
                    print(model, fs, fam_name, seed, round(r["recall_malicious"], 3), flush=True)
            pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    if not rows:
        return
    res = pd.DataFrame(rows)
    keys = ["recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3", "test_fpr_at_that_threshold", "pr_auc", "roc_auc", "n", "n_pos"]
    summ = res.groupby(["model", "feature_set", "family"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


# ------------------------------------------------------------------ item 8: evasion
def perturb(kind, k, seed, classes="malicious"):
    """Test-time (or training-augmentation) perturbation of malicious flows, or of every flow if classes='both'."""
    def f(df):
        df = df.copy()
        mal = np.ones(len(df), bool) if classes == "both" else df["label"].to_numpy() == 1
        if kind == "pad":
            # record padding on malicious flows: only data-carrying packets grow (G2 frame size > 66 B; 54/60/66 B
            # are pure ACKs), capped at a full 1,514-B frame. G1: bytes += k per PSH packet (~ data segments) per
            # direction, max size += k (capped), mean size recomputed; min size (an ACK) unchanged.
            kk = np.rint(np.broadcast_to(np.asarray(k, float), (len(df),)))
            for i in range(20):
                c = f"g2_ps_{i:02d}"
                if c in df:
                    v = df[c].to_numpy(float)
                    df[c] = np.where(mal & (v > 66), np.minimum(v + kk, 1514), v)
            for side in ("bidirectional", "src2dst", "dst2src"):
                b, p, h = f"g1_{side}_bytes", f"g1_{side}_packets", f"g1_{side}_psh_packets"
                if b in df and h in df:
                    nb = df[b].to_numpy(float) + kk * df[h].to_numpy(float)
                    df[b] = np.where(mal, nb, df[b])
                    if f"g1_{side}_mean_ps" in df:
                        df[f"g1_{side}_mean_ps"] = np.where(mal, nb / np.maximum(df[p].to_numpy(float), 1),
                                                            df[f"g1_{side}_mean_ps"])
                if f"g1_{side}_max_ps" in df:
                    c = f"g1_{side}_max_ps"
                    df[c] = np.where(mal, np.minimum(df[c].to_numpy(float) + kk, 1514), df[c])
        else:  # IAT jitter: every timing feature of a malicious flow scaled by one factor in [0.5, 2] (log-uniform)
            rng = np.random.default_rng(seed)
            fac = np.exp(rng.uniform(np.log(0.5), np.log(2.0), len(df)))
            for c in [c for c in df.columns if c.startswith(("g1_", "g2_")) and ("piat" in c or "duration" in c)]:
                df[c] = np.where(mal, df[c] * fac, df[c])
        return df
    return f


def item_padech(a):
    """10: padding against the ECH tier (G1+G2, with / without timing) on the MTA E3 TLS 1.3 test subset.
    Models trained on all versions or on TLS 1.3 only; plain training vs padding augmentation (training flows
    padded by a random 0-256 B per data packet, same rule as item 8): both classes (the defender result) or
    malicious only (a contrast that teaches "large = malicious"). Tested clean and with every malicious test
    data packet padded by 32 or 256 B. Thresholds from the clean validation set."""
    out = BENCH / "b6_padech"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for fs in ("g1g2", "g1g2_notime"):
        cols = set_columns(table("mta"), fs)
        d = dd("mta", cols)
        v = d["k_tls_version"].astype(str).to_numpy()
        lab = d["label"].to_numpy()
        for train_on in ("all versions", "1.3 only"):
            # defender result: both classes padded with the same random 0-256 B distribution, so size inflation
            # carries no class information; malicious-only is kept as a contrast (it teaches "large = malicious")
            for aug in ("none", "pad 0-256 B both classes", "pad 0-256 B malicious only (contrast)"):
                for seed in range(a.seeds):
                    tr, va, te = split(d, "E3", "mta", seed)
                    if train_on == "1.3 only":
                        tr, va = tr[v[tr] == "1.3"], va[v[va] == "1.3"]
                    train = d
                    if aug != "none":  # pad training rows, a random amount per flow
                        rng = np.random.default_rng(1000 + seed)
                        both = aug.endswith("both classes")
                        rows_m = tr if both else tr[lab[tr] == 1]
                        ks = rng.uniform(0, 256, len(rows_m))  # perturb() broadcasts a per-row padding array
                        part = perturb("pad", ks, seed, "both" if both else "malicious")(d.iloc[rows_m])
                        train = d.copy()
                        for c in cols:
                            if pd.api.types.is_numeric_dtype(train[c]):
                                train[c] = train[c].astype(float)
                            train.loc[train.index[rows_m], c] = part[c].to_numpy()
                    trs = sample(tr, lab, seed)
                    test13 = d.iloc[te][v[te] == "1.3"].reset_index(drop=True)
                    tests = {k: (test13 if k == 0 else perturb("pad", k, seed)(test13)) for k in (0, 32, 256)}
                    xf = lambda df: feature_frame(df, cols)
                    x_tr, others = to_model_matrix(xf(train.iloc[trs]), [xf(train.iloc[va])] + [xf(t) for t in tests.values()])
                    s_va, s_te, _, _ = fit_predict("xgb", x_tr, lab[trs], others[0], lab[va], others[1:], seed, a.jobs)
                    thr = thresholds(lab[va], s_va)
                    y13 = test13["label"].to_numpy()
                    for (k, _), s in zip(tests.items(), s_te):
                        m = metrics(y13, s, *thr)
                        rows.append({"feature_set": fs, "train_on": train_on, "train_augmentation": aug,
                                     "test_padding_B": k, "seed": seed, "prevalence": y13.mean(), **m})
                    print(fs, train_on, aug, seed, [round(r["roc_auc"], 3) for r in rows[-3:]], flush=True)
        summarise(rows, out, ["feature_set", "train_on", "train_augmentation", "test_padding_B"],
                  ("roc_auc", "pr_auc", "prevalence", "macro_f1", "recall_malicious", "recall_benign", "n", "n_pos"))
    print(pd.read_csv(out / "summary.csv").to_string())


LODO_KEY = {"raid": "k_pcap", "hikari": "k_client_ip", "mta": "k_post", "mcfp": "k_capture"}


def item_lodo(a):
    """11: leave-one-dataset-out. Train on the other sources pooled (balanced per source: up to 50k flows per
    class per source, so no source dominates), validate on a 15% stratified sample of the pool, test on the
    held-out dataset. HIKARI has G1/G2 only, so it is in the pool / held out for g1g2_notime only. Also an
    origin probe on each pool: XGBoost predicting the source dataset of the pool's *benign* flows,
    with a split grouped by capture/post/host."""
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import StratifiedGroupKFold
    import xgboost as xgb
    out = BENCH / "b6_lodo"
    out.mkdir(parents=True, exist_ok=True)
    rows, probe = [], []
    for fs in ("g1g2_notime", "loo_g5", "all"):
        names = ["mta", "mcfp", "raid", "hikari"] if fs == "g1g2_notime" else ["mta", "mcfp", "raid"]
        cols = cols_for(names, fs)
        d = {n: dedup(table(n), cols)[0].assign(_src=n) for n in names}
        for held in names:
            pool_names = [n for n in names if n != held]
            for seed in range(a.seeds):
                rng = np.random.default_rng(seed)
                parts = []
                for n in pool_names:
                    t = d[n]
                    for lab_ in (0, 1):
                        idx = np.where(t["label"].to_numpy() == lab_)[0]
                        parts.append(t.iloc[rng.choice(idx, min(len(idx), 50_000), replace=False)])
                pool = pd.concat(parts, ignore_index=True)
                tr, va = train_test_split(np.arange(len(pool)), test_size=0.15, stratify=pool["label"], random_state=seed)
                test = d[held].reset_index(drop=True)
                r, _, _ = fit_eval(pool, test, tr, va, cols, seed, a.jobs, boot=50)
                rows.append({"feature_set": fs, "held_out": held, "pool": "+".join(pool_names), "seed": seed,
                             "n_pool": len(pool), **r})
                print(fs, held, seed, round(r["pr_auc"], 4), round(r["test_fpr_at_that_threshold"], 4), flush=True)
                if seed == 0:  # origin probe on the pool's benign flows
                    ben = pool[pool["label"] == 0].reset_index(drop=True)
                    pcols = cols_for(pool_names, "g1g2_notime")
                    x = to_model_matrix(feature_frame(ben, pcols), [])[0]
                    y = pd.Categorical(ben["_src"]).codes
                    groups = ben["_src"] + "|" + ben.apply(lambda r_: str(r_[LODO_KEY[r_["_src"]]]), axis=1)
                    tr_i, te_i = next(StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=0).split(x, y, groups))
                    m = xgb.XGBClassifier(n_estimators=300, max_depth=8, learning_rate=0.1, tree_method="hist",
                                          n_jobs=a.jobs, random_state=0).fit(x.iloc[tr_i], y[tr_i])
                    probe.append({"feature_set_of_detector": fs, "held_out": held, "pool": "+".join(pool_names),
                                  "probe_features": "g1g2_notime", "n_sources": len(pool_names),
                                  "balanced_accuracy": balanced_accuracy_score(y[te_i], m.predict(x.iloc[te_i])),
                                  "chance": 1 / len(pool_names)})
            summarise(rows, out, ["feature_set", "held_out"],
                      ("pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3",
                       "test_fpr_at_that_threshold", "n", "n_pos"))
            pd.DataFrame(probe).to_csv(out / "origin_probe_pooled.csv", index=False)
    print(pd.read_csv(out / "summary.csv").to_string())
    print(pd.DataFrame(probe).to_string())


def item_dohbrw(a):
    """DoHBrw as a fifth source. (a) Origin probe: XGBoost predicting the source dataset of benign flows
    (up to 50k per source, split grouped by capture/post/host as in item 11); five sources on G1/G2 (HIKARI has
    no G3-G5), four sources (no HIKARI) on loo_g5. (b) Benign browser variety in DoHBrw: flows, categories,
    distinct client/server fingerprints per browser, and a Chrome-vs-Firefox probe on benign flows (G1/G2 and
    loo_g5). Only one Firefox capture is distinct (1/dump is a prefix of 2/dump), so the browser probe uses a
    stratified 75/25 split, not a grouped one; its accuracy is an upper bound on how easily the browser shows."""
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import StratifiedGroupKFold
    import xgboost as xgb
    out = BENCH / "b6_dohbrw"
    out.mkdir(parents=True, exist_ok=True)
    key = {**LODO_KEY, "dohbrw": "k_pcap"}

    def xgbm():
        return xgb.XGBClassifier(n_estimators=300, max_depth=8, learning_rate=0.1, tree_method="hist",
                                 n_jobs=a.jobs, random_state=0)

    probe = []
    for fs, names in (("g1g2_notime", ["mta", "mcfp", "raid", "hikari", "dohbrw"]),
                      ("loo_g5", ["mta", "mcfp", "raid", "dohbrw"])):
        cols = cols_for(names, fs)
        rng = np.random.default_rng(0)
        parts = []
        for n in names:
            t = dedup(table(n), cols)[0]
            t = t[t["label"] == 0]
            parts.append(t.iloc[rng.choice(len(t), min(len(t), 50_000), replace=False)].assign(_src=n))
        ben = pd.concat(parts, ignore_index=True)
        x = to_model_matrix(feature_frame(ben, cols), [])[0]
        cat = pd.Categorical(ben["_src"])
        y = cat.codes
        groups = ben["_src"] + "|" + ben.apply(lambda r_: str(r_[key[r_["_src"]]]), axis=1)
        tr_i, te_i = next(StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=0).split(x, y, groups))
        pred = xgbm().fit(x.iloc[tr_i], y[tr_i]).predict(x.iloc[te_i])
        rec = {c: float((pred[y[te_i] == k] == k).mean()) for k, c in enumerate(cat.categories) if (y[te_i] == k).any()}
        probe.append({"probe_features": fs, "sources": "+".join(names), "n_sources": len(names),
                      "n_train": len(tr_i), "n_test": len(te_i),
                      "balanced_accuracy": balanced_accuracy_score(y[te_i], pred), "chance": 1 / len(names),
                      **{f"recall_{c}": v for c, v in rec.items()}})
        print(probe[-1], flush=True)
    pd.DataFrame(probe).to_csv(out / "origin_probe_5src.csv", index=False)

    d = table("dohbrw")
    ben = d[d["label"] == 0]
    var = ben.groupby(["k_browser", "k_category"]).size().unstack(fill_value=0)
    for c in G5:
        if c in ben:
            var[f"distinct_{c}"] = ben.groupby("k_browser")[c].nunique()
    var["captures"] = ben.groupby("k_browser")["k_pcap"].nunique()
    var["servers"] = ben.groupby("k_browser")["k_server_ip"].nunique()
    var.to_csv(out / "browser_variety.csv")
    print(var.to_string(), flush=True)

    bprobe = []
    for fs in ("g1g2_notime", "loo_g5"):
        cols = cols_for(["dohbrw"], fs)
        b = dedup(ben, cols)[0].reset_index(drop=True)
        for subset, bb in (("all benign", b), ("benign DoH only", b[b["k_category"] == "benign DoH"])):
            bb = bb.reset_index(drop=True)
            y = (bb["k_browser"] == "Firefox").astype(int).to_numpy()
            x = to_model_matrix(feature_frame(bb, cols), [])[0]
            tr_i, te_i = train_test_split(np.arange(len(bb)), test_size=0.25, stratify=y, random_state=0)
            pred = xgbm().fit(x.iloc[tr_i], y[tr_i]).predict(x.iloc[te_i])
            bprobe.append({"probe_features": fs, "subset": subset, "n_chrome": int((y == 0).sum()),
                           "n_firefox": int((y == 1).sum()),
                           "balanced_accuracy": balanced_accuracy_score(y[te_i], pred), "chance": 0.5})
            print(bprobe[-1], flush=True)
    pd.DataFrame(bprobe).to_csv(out / "browser_probe.csv", index=False)


def item_browser(a):
    """Chrome-vs-Firefox probe on DoHBrw benign flows without capture leakage. Firefox is one capture session
    (1/dump.pcap is a prefix of 2/dump.pcap), so no split can hold out a Firefox capture. Reported instead:
    (a) leave-one-Chrome-capture-out (5 folds): train on 4 Chrome captures + the first 75% of Firefox in time,
        test on the held-out Chrome capture + the last 25% of Firefox; per-class recall and balanced accuracy;
    (b) permutation importance (balanced accuracy drop, 5 repeats) of the G1/G2 model on fold (a) test rows."""
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import balanced_accuracy_score, make_scorer
    import xgboost as xgb
    out = BENCH / "b6_dohbrw"
    out.mkdir(parents=True, exist_ok=True)
    rows, imps = [], []
    for fs in ("g1g2_notime", "loo_g5"):
        cols = cols_for(["dohbrw"], fs)
        d = table("dohbrw")
        b = dedup(d[d["label"] == 0], cols)[0].reset_index(drop=True)
        ff = b["k_browser"] == "Firefox"
        cut = b.loc[ff, "k_first_seen_ms"].quantile(0.75)
        ff_late = ff & (b["k_first_seen_ms"] > cut)
        x = to_model_matrix(feature_frame(b, cols), [])[0]
        y = ff.astype(int).to_numpy()
        for held in sorted(b.loc[~ff, "k_pcap"].unique()):
            te = ((b["k_pcap"] == held) | ff_late).to_numpy()
            tr = ~te & ~((~ff) & (b["k_pcap"] == held)).to_numpy()
            m = xgb.XGBClassifier(n_estimators=300, max_depth=8, learning_rate=0.1, tree_method="hist",
                                  n_jobs=a.jobs, random_state=0).fit(x[tr], y[tr])
            p = m.predict(x[te])
            rows.append({"probe_features": fs, "held_chrome_capture": held.split("/")[-1],
                         "n_train": int(tr.sum()), "n_test_chrome": int((y[te] == 0).sum()),
                         "n_test_firefox_late": int((y[te] == 1).sum()),
                         "recall_chrome_unseen_capture": float((p[y[te] == 0] == 0).mean()),
                         "recall_firefox_later_time": float((p[y[te] == 1] == 1).mean()),
                         "balanced_accuracy": balanced_accuracy_score(y[te], p)})
            print(rows[-1], flush=True)
            if fs == "g1g2_notime" and not imps:
                rng = np.random.default_rng(0)
                ti = np.where(te)[0]
                ti = np.concatenate([rng.choice(ti[y[ti] == k], min(5000, (y[ti] == k).sum()), replace=False)
                                     for k in (0, 1)])
                pi = permutation_importance(m, x.iloc[ti], y[ti], scoring=make_scorer(balanced_accuracy_score),
                                            n_repeats=5, random_state=0, n_jobs=8)
                gain = m.get_booster().get_score(importance_type="gain")
                imps = [{"feature": c, "perm_drop_mean": pi.importances_mean[i], "perm_drop_std": pi.importances_std[i],
                         "xgb_gain": gain.get(c, 0.0)} for i, c in enumerate(x.columns)]
    pd.DataFrame(rows).to_csv(out / "browser_probe_grouped.csv", index=False)
    imp = pd.DataFrame(imps).sort_values(["perm_drop_mean", "xgb_gain"], ascending=False)
    imp.to_csv(out / "browser_probe_importance.csv", index=False)
    print(pd.DataFrame(rows).groupby("probe_features")[["recall_chrome_unseen_capture", "recall_firefox_later_time",
                                                       "balanced_accuracy"]].agg(["mean", "min"]).to_string())
    print(imp.head(25).to_string())


def item_synsize(a):
    """DoHBrw malicious DoH vs benign DoH: (1) a decision stump on g2_ps_00 (first-packet = SYN size) only;
    (2) XGBoost on all G1/G2 (no timing) vs the same without g2_ps_00. Out-of-fold predictions from a
    5-fold StratifiedGroupKFold grouped by capture (pcap), so no capture is on both sides. Balanced accuracy
    overall and per tool (mean of that tool's recall and benign-DoH specificity)."""
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.tree import DecisionTreeClassifier
    import xgboost as xgb
    out = BENCH / "b6_dohbrw"
    out.mkdir(parents=True, exist_ok=True)
    d = table("dohbrw")
    d = d[d["k_category"] != "non-DoH"]
    full = cols_for(["dohbrw"], "g1g2_notime")
    d = dedup(d, full)[0].reset_index(drop=True)
    y = d["label"].to_numpy()
    folds = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0).split(d, y, d["k_pcap"]))
    tools = d["k_category"].str.extract(r"\((\w+)\)", expand=False)
    variants = {"stump: g2_ps_00 only": ["g2_ps_00"], "xgb: all G1/G2": full,
                "xgb: G1/G2 without g2_ps_00": [c for c in full if c != "g2_ps_00"]}
    rows = []
    for name, cols in variants.items():
        x = to_model_matrix(feature_frame(d, cols), [])[0]
        p = np.zeros(len(d), dtype=int)
        thr = []
        for tr, te in folds:
            if name.startswith("stump"):
                m = DecisionTreeClassifier(max_depth=1, class_weight="balanced", random_state=0).fit(x.iloc[tr], y[tr])
                thr.append(float(m.tree_.threshold[0]))
            else:
                w = np.where(y[tr] == 1, (y[tr] == 0).sum() / max((y[tr] == 1).sum(), 1), 1.0)
                m = xgb.XGBClassifier(n_estimators=300, max_depth=8, learning_rate=0.1, tree_method="hist",
                                      n_jobs=a.jobs, random_state=0).fit(x.iloc[tr], y[tr], sample_weight=w)
            p[te] = m.predict(x.iloc[te])
        spec = float((p[y == 0] == 0).mean())
        r = {"model": name, "n_features": len(cols), "n_benign_doh": int((y == 0).sum()),
             "n_malicious_doh": int((y == 1).sum()), "benign_specificity": spec,
             "balanced_accuracy": balanced_accuracy_score(y, p),
             "stump_thresholds": ";".join(f"{t:g}" for t in thr)}
        for t in sorted(tools.dropna().unique()):
            rec = float((p[(tools == t).to_numpy()] == 1).mean())
            r[f"recall_{t}"] = rec
            r[f"balanced_accuracy_{t}"] = (rec + spec) / 2
        rows.append(r)
        print(r, flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(out / "synsize_test.csv", index=False)
    print(res.T.to_string())


def item_hosts(a):
    """12: host-level alerting on MTA E3. Flow scores (E3 model, 5 seeds) aggregated per source host
    (k_pcap, k_client_ip) per 1-hour window and per pcap, with max and top-3 mean. A unit is positive if it holds a
    malicious flow. Alerts at the flow-level val-FPR-1e-3 threshold (and the val max-F1 one). Reports unit
    detection, false-alarm rate on negative units, and false alarms per benign host-day (negative 1-h windows)."""
    out = BENCH / "b6_hosts"
    out.mkdir(parents=True, exist_ok=True)
    rows, census = [], None
    for fs in ("all", "loo_g5", "g1g2"):
        cols = set_columns(table("mta"), fs)
        d = dd("mta", cols)
        for seed in range(a.seeds):
            tr, va, te = split(d, "E3", "mta", seed)
            test = d.iloc[te].reset_index(drop=True)
            _, s, (t_f1, t_fpr) = fit_eval(d, test, tr, va, cols, seed, a.jobs, boot=0)
            test = test.assign(score=s, host=test["k_pcap"] + "|" + test["k_client_ip"],
                               hour=(test["k_first_seen_ms"] // 3_600_000).astype("int64"))
            if census is None:
                h = test.groupby("host")["label"].agg(["max", "size"])
                w = test.groupby(["host", "hour"])["label"].max()
                census = {"test_flows": len(test), "pcaps": int(test["k_pcap"].nunique()), "hosts": len(h),
                          "hosts_with_malicious": int(h["max"].sum()), "benign_only_hosts": int((h["max"] == 0).sum()),
                          "host_hours": len(w), "host_hours_with_malicious": int(w.sum()),
                          "benign_host_hours": int((w == 0).sum()),
                          "benign_flows_on_infected_hosts": int(test[test["host"].isin(h.index[h["max"] == 1]) & (test.label == 0)].shape[0])}
                (out / "census.json").write_text(json.dumps(census, indent=2))
                print(census, flush=True)
            for unit, keys in (("host x 1 h", ["host", "hour"]), ("host x pcap", ["host"])):
                g = test.groupby(keys)
                agg = pd.DataFrame({"pos": g["label"].max(), "max": g["score"].max(),
                                    "top3": g["score"].apply(lambda v: np.sort(v.to_numpy())[-3:].mean()),
                                    "n_flows": g.size()})
                n_neg_hours = int((agg["pos"] == 0).sum()) if unit == "host x 1 h" else None
                for how in ("max", "top3"):
                    for tname, thr in (("val FPR 1e-3", t_fpr), ("val max-F1", t_f1)):
                        alert = agg[how] >= thr
                        pos, neg = agg["pos"] == 1, agg["pos"] == 0
                        rows.append({"feature_set": fs, "seed": seed, "unit": unit, "aggregate": how, "threshold": tname,
                                     "n_pos_units": int(pos.sum()), "n_neg_units": int(neg.sum()),
                                     "unit_detection_rate": float(alert[pos].mean()) if pos.any() else np.nan,
                                     "unit_false_alarm_rate": float(alert[neg].mean()) if neg.any() else np.nan,
                                     "false_alarms_per_benign_host_day": float(alert[neg].sum() / n_neg_hours * 24)
                                     if n_neg_hours else np.nan,
                                     "flow_level_fpr": float((test.loc[test.label == 0, "score"] >= thr).mean())})
            print(fs, seed, flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(out / "results_per_seed.csv", index=False)
    keys = ["unit_detection_rate", "unit_false_alarm_rate", "false_alarms_per_benign_host_day", "flow_level_fpr",
            "n_pos_units", "n_neg_units"]
    s = res.groupby(["feature_set", "unit", "aggregate", "threshold"], sort=False)[keys].agg(["mean", "std"])
    s.columns = [f"{k}_{t}" for k, t in s.columns]
    s.reset_index().to_csv(out / "summary.csv", index=False)
    print(s.to_string())


def item_evasion(a):
    out = BENCH / "b6_evasion"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for fs in ("all", "loo_g5", "g1g2"):
        cols = set_columns(table("mta"), fs)
        d = dedup(table("mta"), cols)[0]
        for seed in range(a.seeds):
            tr, va, te = split(d, "E3", "mta", seed)
            test = d.iloc[te].reset_index(drop=True)
            for kind, k in (("clean", 0), ("pad", 16), ("pad", 64), ("pad", 256), ("jitter", 0)):
                r, _, _ = fit_eval(d, test, tr, va, cols, seed, a.jobs, boot=100,
                                   perturb=None if kind == "clean" else perturb(kind, k, seed))
                rows.append({"feature_set": fs, "attack": kind if kind != "pad" else f"pad{k}", "seed": seed, **r})
                print(fs, kind, k, seed, round(r["pr_auc"], 4), flush=True)
            pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    res = pd.DataFrame(rows)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign"]
    summ = res.groupby(["feature_set", "attack"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("item", choices=["seeds", "baserate", "rolling", "encoding", "ech", "training", "family", "evasion",
                                     "rolling_models", "rolling_enc", "post2026", "tls13", "family_models", "padech",
                                     "lodo", "hosts", "dohbrw", "browser", "synsize"])
    ap.add_argument("--seeds", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--min-posts", type=int, default=5)
    a = ap.parse_args()
    a.seeds = a.seeds or {"seeds": 20, "baserate": 20, "encoding": 20}.get(a.item, 5)
    {"seeds": item_seeds, "baserate": item_baserate, "rolling": item_rolling, "encoding": item_encoding,
     "ech": item_ech, "training": item_training, "family": item_family, "evasion": item_evasion,
     "rolling_models": item_rolling_models, "rolling_enc": item_rolling_enc, "post2026": item_post2026,
     "tls13": item_tls13, "family_models": item_family_models, "padech": item_padech,
     "lodo": item_lodo, "hosts": item_hosts, "dohbrw": item_dohbrw, "browser": item_browser, "synsize": item_synsize}[a.item](a)
