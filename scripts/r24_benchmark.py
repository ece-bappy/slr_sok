"""RAID 2024 baselines (C-Cert, C-Behav) under our protocol (plan.md §5.3; runs on A2).

Usage: python scripts/r24_benchmark.py [--seeds 5] [--out /data/tls-sok/benchmark/r24_protocol]
Needs the record tables from scripts/r24_records.py and the authors' repository at
/data/tls-sok/ext/extending12to13 (their tls_paper_funcs.py and notebook constants are imported as is).

Features, computed with the authors' own functions on Joy-format record sequences:
  C-Cert   server certificate chain size: Wireshark's certificates_length for TLS < 1.3; for TLS 1.3 flows
           without PSK or HelloRetryRequest, cert_size_inference_simple_diagram(); -1 = not available.
  C-Behav  sizes + directions of the first 10 application-data records: tls_12_appdata_filtering() for
           TLS < 1.3; for TLS 1.3 additionally handshake_removal_only(); empty = not available.
Classifiers and settings as in the paper / notebooks (hard-coded best parameters from their grid search):
  C-Cert DT  (gini, depth 1, balanced)    C-Cert RF  (40 trees, entropy, depth 5, balanced)
  C-Behav DT (entropy, depth 16)          C-Behav RF (70 trees, depth 20, sqrt features, balanced)
  with their training-noise augmentation (C-Cert: subtract a draw from their curl error list; C-Behav:
  non-central chi-square noise on record sizes), each noisy copy concatenated with the original.
Our protocol around them: labels from our tables; rows deduplicated on the G1-G5 (`all`) vector, so every
classifier sees the same flows; settings RAID E2 (pcap-grouped), MTA E2 (post-grouped), MTA E3 (<= 2022
-> later), E4 MCFP -> MTA; each classifier is scored on the flows where its feature exists (coverage is
reported) and, as a reference, XGBoost on G1-G5 is trained and scored on exactly the same rows; 1:1
training balance, validation-only thresholds (max-F1, FPR 1e-3), 5 seeds, bootstrap CIs. The paper's own
operating point (predict(), i.e. probability 0.5) is reported too as tpr/tnr_at_0.5.
"""
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from run_benchmark import (balance, bootstrap, dedup, feature_frame, fit_predict, metrics, set_columns, split,
                           thresholds, to_model_matrix)

REPO = Path("/data/tls-sok/ext/extending12to13")
sys.path.insert(0, str(REPO))
from tls_paper_funcs import (cert_size_inference_simple_diagram, handshake_removal_only,  # noqa: E402
                             tls_12_appdata_filtering)

REC = Path("/data/tls-sok/r24rec")
SOURCES = {"mta": ["mta"], "mcfp": ["mcfp"], "raid": ["raid_ms", "raid_tranco"]}
KEY = ["k_source", "k_pcap", "k_client_ip", "k_client_port", "k_server_ip", "k_server_port"]
B10 = [f"tls_b_{i}" for i in range(10)]
D10 = [f"tls_dir_{i}" for i in range(10)]
BS, DS, TS = ([f"tls_{k}_{i}" for i in range(20)] for k in ("b", "dir", "tp"))
SETTINGS = [("raid", "E2"), ("mta", "E2"), ("mta", "E3"), ("mcfp>mta", "E4")]
CLASSIFIERS = ["c_cert_dt", "c_cert_rf", "c_behav_dt", "c_behav_rf"]


def diff_list() -> np.ndarray:
    """The authors' certificate-size error list (03-C-CERT, cell 24), read from the notebook itself."""
    nb = json.loads((REPO / "03-C-CERT.ipynb").read_text())
    src = next("".join(c["source"]) for c in nb["cells"] if "diff_list = np.array" in "".join(c["source"]))
    ns = {"np": np}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(src, ns)
    return ns["diff_list"]


def records(ds: str) -> pd.DataFrame:
    parts = []
    for s in SOURCES[ds]:
        for p in sorted((REC / s).rglob("*.parquet")):
            r = pd.read_parquet(p)
            if len(r):
                parts.append(r.assign(k_source=s, k_pcap=str(p.relative_to(REC / s))[:-len(".parquet")]))
    return pd.concat(parts, ignore_index=True)


def join(table: pd.DataFrame, rec: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Attach each table flow's record row: same pcap and 4-tuple, nearest first-packet time within 2 s."""
    r = rec.rename(columns={"c_ip": "k_client_ip", "c_port": "k_client_port", "s_ip": "k_server_ip",
                            "s_port": "k_server_port"})
    t = table.reset_index().rename(columns={"index": "_row"})
    m = t[KEY + ["_row", "k_first_seen_ms"]].merge(r, on=KEY, how="inner")
    m["_dt"] = (m["k_first_seen_ms"] / 1000 - m["start_time"]).abs()
    m = m[m["_dt"] <= 2.0].sort_values("_dt").drop_duplicates("_row")
    out = table.iloc[m["_row"].to_numpy()].reset_index(drop=True)
    cols = [c for c in m.columns if c.startswith("tls_") or c in ("s_selected_version", "s_psk", "hello_retry_req",
                                                                    "certificates_length")]
    out = pd.concat([out, m[cols].reset_index(drop=True)], axis=1)
    return out, {"table_rows": len(table), "matched": len(out), "match_rate": len(out) / max(len(table), 1)}


def r24_features(df: pd.DataFrame) -> pd.DataFrame:
    """C-Cert feature `cert_len` and C-Behav features b0..b9 / d0..d9 (authors' functions)."""
    tls13 = df["s_selected_version"].to_numpy() == 0x0304
    cert = np.where(tls13, -1, df["certificates_length"].to_numpy()).astype(float)
    infer = np.where(tls13 & (df["s_psk"].to_numpy() == -1) & (df["hello_retry_req"].to_numpy() == 0))[0]
    with contextlib.redirect_stdout(io.StringIO()):  # the function prints a line for every flow it cannot use
        for i in infer:
            cert[i] = cert_size_inference_simple_diagram(df.iloc[i], i)
    behav = np.full((len(df), 20), -1.0)
    v12 = np.where(~tls13)[0]
    if len(v12):
        f12 = tls_12_appdata_filtering(df.iloc[v12])
        behav[v12] = f12[B10 + D10].to_numpy(float)
    v13 = np.where(tls13)[0]
    if len(v13):
        f13 = tls_12_appdata_filtering(df.iloc[v13]).astype(int)
        for j, i in enumerate(v13):
            b, d = handshake_removal_only(f13.iloc[j])
            b, d = list(b)[:10], list(d)[:10]
            behav[i] = np.array(b + [-1] * (10 - len(b)) + d + [-1] * (10 - len(d)), dtype=float)
    out = pd.DataFrame(behav, columns=[f"r24_b{i}" for i in range(10)] + [f"r24_d{i}" for i in range(10)])
    out["r24_cert_len"] = cert
    out["r24_cert_ok"] = cert != -1
    out["r24_behav_ok"] = (behav[:, :10] != -1).any(axis=1)
    return out


def augment(kind: str, x: np.ndarray, y: np.ndarray, rng: np.random.Generator, diffs: np.ndarray):
    """The authors' training noise; the noisy copy is concatenated with the original."""
    if kind.startswith("c_cert"):
        noisy = x - rng.choice(diffs, size=x.shape)
    else:
        mask = (x != -1).astype(int) * np.concatenate([np.ones((len(x), 10)), np.zeros((len(x), 10))], axis=1)
        noisy = x + mask * (rng.noncentral_chisquare(3, 10, x.shape).astype(int) - 10)
    return np.concatenate([noisy, x]), np.concatenate([y, y])


def model(kind: str, seed: int):
    return {"c_cert_dt": lambda: DecisionTreeClassifier(random_state=seed, class_weight="balanced", criterion="gini",
                                                        max_depth=1),
            "c_cert_rf": lambda: RandomForestClassifier(random_state=seed, n_jobs=-1, class_weight="balanced",
                                                        criterion="entropy", max_depth=5, n_estimators=40),
            "c_behav_dt": lambda: DecisionTreeClassifier(random_state=seed, criterion="entropy", max_depth=16),
            "c_behav_rf": lambda: RandomForestClassifier(random_state=seed, n_jobs=-1, class_weight="balanced",
                                                         max_depth=20, max_features="sqrt", n_estimators=70)}[kind]()


def feat_cols(kind: str) -> list[str]:
    return ["r24_cert_len"] if kind.startswith("c_cert") else [f"r24_b{i}" for i in range(10)] + \
        [f"r24_d{i}" for i in range(10)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="/data/tls-sok/tables")
    ap.add_argument("--out", default="/data/tls-sok/benchmark/r24_protocol")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=32)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    diffs = diff_list()
    data, info = {}, {}
    for ds in ("raid", "mta", "mcfp"):
        cache = out / f"joined_{ds}.parquet"
        if cache.exists():
            data[ds] = pd.read_parquet(cache)
            info[ds] = json.loads((out / f"join_{ds}.json").read_text())
            continue
        table = pd.read_parquet(f"{a.tables}/{ds}.parquet")
        table = dedup(table, set_columns(table, "all"))[0]
        j, info[ds] = join(table, records(ds))
        j = pd.concat([j, r24_features(j)], axis=1)
        info[ds].update({"cert_available": float(j["r24_cert_ok"].mean()), "behav_available": float(j["r24_behav_ok"].mean()),
                         "tls13_share": float((j["s_selected_version"] == 0x0304).mean())})
        j.drop(columns=BS + DS + TS).to_parquet(cache)
        (out / f"join_{ds}.json").write_text(json.dumps(info[ds], indent=2))
        data[ds] = j
        print(ds, info[ds], flush=True)

    rows, ver_rows, cov = [], [], []
    for ds, exp in SETTINGS:
        for kind in CLASSIFIERS:
            ok = "r24_cert_ok" if kind.startswith("c_cert") else "r24_behav_ok"
            names = ds.split(">")
            sub = {n: data[n][data[n][ok]].reset_index(drop=True) for n in names}
            for n in names:
                cov.append({"setting": f"{ds}|{exp}", "classifier": kind, "dataset": n, "rows": len(data[n]),
                            "covered": len(sub[n]), "coverage": len(sub[n]) / len(data[n]),
                            "coverage_malicious": float(data[n].loc[data[n]["label"] == 1, ok].mean()),
                            "coverage_benign": float(data[n].loc[data[n]["label"] == 0, ok].mean())})
            for seed in range(a.seeds):
                if exp == "E4":
                    train, test = sub[names[0]], sub[names[1]]
                    y = train["label"].to_numpy()
                    tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=y, random_state=seed)
                else:
                    train = sub[ds]
                    y = train["label"].to_numpy()
                    sp = split(train, exp, ds, seed)
                    if isinstance(sp, str):
                        rows.append({"setting": f"{ds}|{exp}", "classifier": kind, "seed": seed, "status": sp})
                        break
                    tr, va, te = sp
                    test = train.iloc[te]
                trb = balance(tr, y, seed)
                y_te = test["label"].to_numpy()
                base = {"setting": f"{ds}|{exp}", "classifier": kind, "seed": seed, "status": "ok",
                        "n_train_balanced": len(trb)}
                cols = feat_cols(kind)
                rng = np.random.default_rng(seed)
                x_aug, y_aug = augment(kind, train.iloc[trb][cols].to_numpy(float), y[trb], rng, diffs)
                m = model(kind, seed).fit(x_aug, y_aug)
                s_va = m.predict_proba(train.iloc[va][cols].to_numpy(float))[:, 1]
                s_te = m.predict_proba(test[cols].to_numpy(float))[:, 1]
                # reference: XGBoost on G1-G5, same rows and split
                fcols = sorted(set(set_columns(train, "all")) & set(set_columns(test, "all")))
                x_tr, (x_va, x_te) = to_model_matrix(feature_frame(train.iloc[trb], fcols),
                                                     [feature_frame(train.iloc[va], fcols), feature_frame(test, fcols)])
                r_va, (r_te,), _, _ = fit_predict("xgb", x_tr, y[trb], x_va, y[va], [x_te], seed, a.jobs)
                for name, sv, st in ((kind, s_va, s_te), (f"xgb_all_same_rows[{kind}]", r_va, r_te)):
                    thr_f1, thr_fpr = thresholds(y[va], sv)
                    mt = metrics(y_te, st, thr_f1, thr_fpr)
                    ci = bootstrap(y_te, st, thr_f1, thr_fpr, a.boot if len(y_te) <= 200_000 else 20, seed)
                    p05 = st >= 0.5
                    rows.append({**base, "model": name, **mt, "tpr_at_0.5": float(p05[y_te == 1].mean()),
                                 "tnr_at_0.5": float(1 - p05[y_te == 0].mean()),
                                 **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                    vers = test["k_tls_version"].to_numpy()
                    for v in np.unique(vers):
                        i = vers == v
                        ver_rows.append({**base, "model": name, "tls_version": v,
                                         **metrics(y_te[i], st[i], thr_f1, thr_fpr)})
                    print(base["setting"], name, seed, {k: round(mt[k], 4) for k in ("pr_auc", "macro_f1")}, flush=True)
                pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    pd.DataFrame(ver_rows).to_csv(out / "results_per_tls_version.csv", index=False)
    pd.DataFrame(cov).to_csv(out / "coverage.csv", index=False)
    res = pd.DataFrame(rows)
    res = res[res["status"] == "ok"]
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3",
            "test_fpr_at_that_threshold", "tpr_at_0.5", "tnr_at_0.5", "n", "n_pos"]
    summ = res.groupby(["setting", "classifier", "model"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


if __name__ == "__main__":
    main()
