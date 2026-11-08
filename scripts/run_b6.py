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


def item_family(a):
    out = BENCH / "b6_family"
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
            for seed in range(a.seeds):
                tr, va = train_test_split(np.arange(len(rest)), test_size=0.15, stratify=rest["label"], random_state=seed)
                r, s_te, thr = fit_eval(rest, test, tr, va, cols, seed, a.jobs, boot=100)
                rows.append({"feature_set": fs, "family": fam_name, "n_posts": int(counts[fam_name]), "seed": seed, **r})
                print(fs, fam_name, seed, round(r["recall_malicious"], 3), flush=True)
            pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    if not rows:
        return
    res = pd.DataFrame(rows)
    keys = ["recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3", "test_fpr_at_that_threshold", "pr_auc", "roc_auc", "n", "n_pos"]
    summ = res.groupby(["feature_set", "family"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


# ------------------------------------------------------------------ item 8: evasion
def perturb(kind, k, seed):
    def f(df):
        df = df.copy()
        mal = df["label"].to_numpy() == 1
        if kind == "pad":  # uniform per-packet padding on malicious flows
            for i in range(20):
                c = f"g2_ps_{i:02d}"
                if c in df:
                    v = df[c].to_numpy(float)
                    df[c] = np.where(mal & (v > 0), v + k, v)
            for side in ("bidirectional", "src2dst", "dst2src"):
                if f"g1_{side}_bytes" in df:
                    df[f"g1_{side}_bytes"] = np.where(mal, df[f"g1_{side}_bytes"] + k * df[f"g1_{side}_packets"],
                                                      df[f"g1_{side}_bytes"])
                for s in ("min_ps", "mean_ps", "max_ps"):
                    c = f"g1_{side}_{s}"
                    if c in df:
                        df[c] = np.where(mal, df[c] + k, df[c])
        else:  # IAT jitter: every timing feature of a malicious flow scaled by one factor in [0.5, 2] (log-uniform)
            rng = np.random.default_rng(seed)
            fac = np.exp(rng.uniform(np.log(0.5), np.log(2.0), len(df)))
            for c in [c for c in df.columns if c.startswith(("g1_", "g2_")) and ("piat" in c or "duration" in c)]:
                df[c] = np.where(mal, df[c] * fac, df[c])
        return df
    return f


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
    ap.add_argument("item", choices=["seeds", "baserate", "rolling", "encoding", "ech", "training", "family", "evasion"])
    ap.add_argument("--seeds", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--min-posts", type=int, default=5)
    a = ap.parse_args()
    a.seeds = a.seeds or {"seeds": 20, "baserate": 20, "encoding": 20}.get(a.item, 5)
    {"seeds": item_seeds, "baserate": item_baserate, "rolling": item_rolling, "encoding": item_encoding,
     "ech": item_ech, "training": item_training, "family": item_family, "evasion": item_evasion}[a.item](a)
