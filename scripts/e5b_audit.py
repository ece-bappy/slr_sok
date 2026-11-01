"""E5b shortcut and label-circularity audit (plan §5.4), runs on A2.

Usage:
  python scripts/e5b_audit.py origin [--seeds 5] [--cap 15000]
      (i) dataset-of-origin probe: benign-only flows from RAID Tranco, HIKARI benign, CTU-Normal (MCFP) and
      MTA same-host background; a multiclass XGBoost predicts the source. High balanced accuracy = the
      benign environment alone is learnable, so any malicious-vs-benign pairing across sources can be
      solved by recognising the source. Run per feature set; HIKARI has G1/G2 only, so the sets with TLS
      fields use the other three sources. Two splits: stratified random, and grouped (no capture / post /
      client host in both parts).
  python scripts/e5b_audit.py sslbl
      (ii) builds mta_sslbl and mcfp_sslbl tables for the circularity comparison only: positives = flows
      whose leaf-certificate SHA-1 or JA3 is on abuse.ch SSLBL (from *_all.parquet, i.e. all extracted TLS
      flows, labelled or not); negatives = the same negatives as the main tables (MTA same-host
      background, CTU-Normal). Writes agreement counts between SSLBL and the IOC/sandbox labels. The
      tables are then run through run_benchmark.py like the main ones and compared.
  python scripts/e5b_audit.py table
      (iii) collects the single-feature AUC screens of every benchmark run plus the has_server_hello
      flag's own AUC into one shortcut table.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from run_benchmark import dedup, feature_frame, set_columns, to_model_matrix

TABLES = Path("/data/tls-sok/tables")
OUT = Path("/data/tls-sok/benchmark/e5b")
GROUP = {"raid": "k_pcap", "hikari": "k_client_ip", "mcfp": "k_capture", "mta": "k_post"}
SOURCE_NAME = {"raid": "RAID Tranco", "hikari": "HIKARI benign", "mcfp": "CTU-Normal", "mta": "MTA background"}


# ---------------------------------------------------------------- (i) origin probe

def origin(seeds: int, cap: int) -> None:
    ben = {}
    for ds in GROUP:
        t = pd.read_parquet(TABLES / f"{ds}.parquet")
        t = t[t["label"] == 0].copy()
        t["source"], t["group"] = ds, ds + ":" + t[GROUP[ds]].astype(str)
        ben[ds] = t
    rows, conf_rows = [], []
    for fs in ("g1g2", "g1g2_notime", "tier_tls13", "all"):
        srcs = [s for s in ben if not (s == "hikari" and fs not in ("g1g2", "g1g2_notime"))]
        cols = sorted(set.intersection(*(set(set_columns(ben[s], fs)) for s in srcs)))
        parts = []
        for s in srcs:
            d = ben[s].copy()
            d["label"] = 0  # dedup within a source only
            d, _ = dedup(d, cols)
            parts.append(d)
        allb = pd.concat(parts, ignore_index=True)
        y_all = allb["source"].map({s: i for i, s in enumerate(srcs)}).to_numpy()
        for split_kind in ("random", "grouped"):
            for seed in range(seeds):
                rng = np.random.default_rng(seed)
                # equal rows per source (at most cap), so chance = 1 / number of sources
                n = min(cap, min((y_all == i).sum() for i in range(len(srcs))))
                if split_kind == "random":
                    pick = np.concatenate([rng.choice(np.flatnonzero(y_all == i), n, replace=False)
                                           for i in range(len(srcs))])
                    tr, te = train_test_split(pick, test_size=0.3, stratify=y_all[pick], random_state=seed)
                else:
                    sgk = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
                    tr_all, te_all = next(sgk.split(allb, y_all, allb["group"].values))
                    sub = lambda idx: np.concatenate([rng.choice(idx[y_all[idx] == i],
                                                                 min(n, (y_all[idx] == i).sum()), replace=False)
                                                      for i in range(len(srcs))])
                    tr, te = sub(tr_all), sub(te_all)
                tr, va = train_test_split(tr, test_size=0.15, stratify=y_all[tr], random_state=seed)
                x_tr, (x_va, x_te) = to_model_matrix(feature_frame(allb.iloc[tr], cols),
                                                     [feature_frame(allb.iloc[va], cols),
                                                      feature_frame(allb.iloc[te], cols)])
                m = xgb.XGBClassifier(n_estimators=500, max_depth=8, learning_rate=0.1, subsample=0.8,
                                      colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
                                      max_cat_to_onehot=1, n_jobs=16, random_state=seed,
                                      early_stopping_rounds=30, objective="multi:softprob")
                m.fit(x_tr, y_all[tr], eval_set=[(x_va, y_all[va])], verbose=False)
                p = m.predict(x_te)
                yt = y_all[te]
                row = {"feature_set": fs, "split": split_kind, "seed": seed, "sources": "+".join(srcs),
                       "n_features": len(cols), "n_test": len(te), "chance": 1 / len(srcs),
                       "balanced_accuracy": balanced_accuracy_score(yt, p), "macro_f1": f1_score(yt, p, average="macro")}
                for i, s in enumerate(srcs):
                    row[f"recall_{s}"] = float((p[yt == i] == i).mean()) if (yt == i).any() else np.nan
                rows.append(row)
                if seed == 0:
                    cm = confusion_matrix(yt, p, labels=range(len(srcs)))
                    for i, s in enumerate(srcs):
                        conf_rows.append({"feature_set": fs, "split": split_kind, "true": SOURCE_NAME[s],
                                          **{SOURCE_NAME[t]: int(cm[i, j]) for j, t in enumerate(srcs)}})
                    g = m.get_booster().get_score(importance_type="gain")
                    top = sorted(g.items(), key=lambda kv: -kv[1])[:5]
                    row["top_features_seed0"] = "; ".join(f"{k}" for k, _ in top)
                print(fs, split_kind, seed, round(row["balanced_accuracy"], 4), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "origin_probe_per_seed.csv", index=False)
    pd.DataFrame(conf_rows).to_csv(OUT / "origin_probe_confusion_seed0.csv", index=False)
    rec = [c for c in res.columns if c.startswith("recall_")]
    summ = res.groupby(["feature_set", "split", "sources"], sort=False)[["balanced_accuracy", "macro_f1", "chance"] + rec].agg(["mean", "std"])
    summ.columns = [f"{a}_{b}" for a, b in summ.columns]
    summ.reset_index().to_csv(OUT / "origin_probe_summary.csv", index=False)
    print(summ.to_string())


# ---------------------------------------------------------------- (ii) SSLBL labels

def sslbl() -> None:
    raw = Path("/data/tls-sok/raw/sslbl")
    certs = pd.read_csv(raw / "sslblacklist.csv", comment="#", header=None, names=["listed", "sha1", "reason"])
    ja3 = pd.read_csv(raw / "ja3_fingerprints.csv", comment="#", header=None,
                      names=["ja3", "first_seen", "last_seen", "reason"])
    bad_sha1, bad_ja3 = set(certs["sha1"].str.lower()), set(ja3["ja3"].str.lower())
    report = {"sslbl_downloaded_on": (raw / "downloaded_on.txt").read_text().strip(),
              "sslbl_cert_sha1": len(bad_sha1), "sslbl_ja3": len(bad_ja3)}
    for ds in ("mta", "mcfp"):
        full = pd.read_parquet(TABLES / f"{ds}_all.parquet")
        sha = pd.concat([pd.read_csv(p).assign(k_pcap=str(p.relative_to(f"/data/tls-sok/out/sha1/{ds}"))[:-4])
                         for p in Path(f"/data/tls-sok/out/sha1/{ds}").rglob("*.csv")], ignore_index=True)
        sha = sha.drop_duplicates(["k_pcap", "client_ip", "client_port", "server_ip", "server_port"])
        full = full.merge(sha.rename(columns={"client_ip": "k_client_ip", "client_port": "k_client_port",
                                              "server_ip": "k_server_ip", "server_port": "k_server_port"}),
                          on=["k_pcap", "k_client_ip", "k_client_port", "k_server_ip", "k_server_port"], how="left")
        cert_hit = full["leaf_sha1"].fillna("").str.lower().isin(bad_sha1)
        ja3_hit = full["g5_ja3"].fillna("").str.lower().isin(bad_ja3)
        hit = cert_hit | ja3_hit
        lab = full["label"]
        rep = {"tls_flows": len(full), "with_leaf_sha1": int(full["leaf_sha1"].notna().sum()),
               "sslbl_hits": int(hit.sum()), "cert_hits": int(cert_hit.sum()), "ja3_hits": int(ja3_hit.sum()),
               "hits_by_main_label": {str(k): int(v) for k, v in lab[hit].fillna(-1).value_counts().items()},
               "main_positives_with_sslbl_hit": int((hit & (lab == 1)).sum()),
               "main_positives": int((lab == 1).sum()),
               "main_negatives_with_sslbl_hit": int((hit & (lab == 0)).sum())}
        # SSLBL-labelled table: hits = 1; the main table's negatives that are not hits = 0
        neg = full[(lab == 0) & ~hit].assign(label=0)
        pos = full[hit].assign(label=1)
        t = pd.concat([pos, neg], ignore_index=True).drop(columns=["leaf_sha1"])
        if ds == "mta":
            t["k_category"] = np.where(t["label"] == 1, "SSLBL hit", "same-host background")
        t = t.astype({"label": int})
        t.to_parquet(TABLES / f"{ds}_sslbl.parquet", index=False)
        rep["sslbl_table_rows"] = {"1": int((t["label"] == 1).sum()), "0": int((t["label"] == 0).sum())}
        rep["sslbl_positive_reasons_top"] = (certs.set_index(certs["sha1"].str.lower())["reason"]
                                             .reindex(full.loc[cert_hit, "leaf_sha1"].str.lower())
                                             .value_counts().head(10).to_dict())
        report[ds] = rep
        print(ds, json.dumps(rep, default=str), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sslbl_agreement.json").write_text(json.dumps(report, indent=2, default=str))


# ---------------------------------------------------------------- (iii) shortcut table

def table() -> None:
    bench = Path("/data/tls-sok/benchmark")
    screens = [pd.read_csv(p) for p in bench.glob("*/shortcut_screen.csv") if p.stat().st_size > 1]
    sc = pd.concat(screens, ignore_index=True)
    rows = []
    for ds in ("raid", "mta", "mcfp", "mta_sslbl", "mcfp_sslbl"):
        p = TABLES / f"{ds}.parquet"
        if not p.exists():
            continue
        t = pd.read_parquet(p)
        if "g3_has_server_hello" not in t:
            continue
        x = t["g3_has_server_hello"].fillna(-1).to_numpy()
        auc = roc_auc_score(t["label"], x) if np.unique(x).size > 1 else 0.5
        rows.append({"dataset": ds, "feature_set": "single flag", "feature": "g3_has_server_hello",
                     "train_auc_alone": round(max(auc, 1 - auc), 4), "flag": max(auc, 1 - auc) >= 0.99,
                     "share_without_sh_malicious": round(float((x[t["label"] == 1] == 0).mean()), 4),
                     "share_without_sh_benign": round(float((x[t["label"] == 0] == 0).mean()), 4)})
    sc = pd.concat([sc, pd.DataFrame(rows)], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    sc.to_csv(OUT / "shortcut_table.csv", index=False)
    print(sc[sc["flag"] == True].groupby(["dataset", "feature_set"]).size().to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["origin", "sslbl", "table"])
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--cap", type=int, default=15000)
    a = ap.parse_args()
    {"origin": lambda: origin(a.seeds, a.cap), "sslbl": sslbl, "table": table}[a.part]()
    sys.exit(0)
