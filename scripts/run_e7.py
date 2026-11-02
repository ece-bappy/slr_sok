"""E7 end-to-end cost (runs on A2): feature extraction + inference, per flow.

Usage (each mode is one process, so peak RSS and CPU time are per mode; run under `taskset -c 0` or
`taskset -c 0,1` for the edge proxy, which pins the process and its children to 1 or 2 cores):
  .venv/bin/python scripts/run_e7.py prep                       # train xgb/lgbm/rf/lr, save models + data
  /data/tls-sok/venv-torch/bin/python scripts/run_e7.py prep_cnn  # train the 1D-CNN on the same split
  python scripts/run_e7.py infer --model xgb --threads 1 --tag edge1 [--device cuda]
  .venv/bin/python scripts/run_e7.py extract --threads 1 --tag edge1   # Zeek + tlsfp + NFStream + features

Models are trained once on MTA, feature set `all` (G1-G5, 174 features; the CNN uses the 20-packet
G2 sequence), E2 split seed 0, fixed hyperparameters as in run_benchmark.py. Inference timing:
  batch=1  : 2,000 single-flow calls (each a one-row frame through the model's own preprocessing)
  batched  : batches of 1,024 flows, and the whole test set in one call
CPU %    = process CPU time / wall time x 100 over the batched runs (100 = one core busy)
peak RSS = ru_maxrss of the process (includes the test data held in memory; data_mb is reported too)
Extraction runs the production pipeline (src/tlssok/extract.py) on a fixed sample of 30 MTA pcaps,
timing each stage, then build_tables.features() for the G1-G5 columns. Zeek runs as a child
process; its CPU time and RSS are counted from RUSAGE_CHILDREN.
"""
import argparse
import json
import os
import pickle
import random
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

E7 = Path("/data/tls-sok/e7")
OUT = Path("/data/tls-sok/benchmark/e7")
HERE = Path(__file__).resolve().parent


def rss_mb(who=resource.RUSAGE_SELF) -> float:
    return resource.getrusage(who).ru_maxrss / 1024


def cpu_s(who=resource.RUSAGE_SELF) -> float:
    r = resource.getrusage(who)
    return r.ru_utime + r.ru_stime


def save(row: dict, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(row, indent=2))
    print(json.dumps(row), flush=True)


# ---------------------------------------------------------------- training (once)

def sfx(fs: str) -> str:
    """File-name suffix for models trained on a feature set other than `all` (e.g. the Zeek-free g1g2g3)."""
    return "" if fs == "all" else f"_{fs}"


def prep(jobs: int, fs: str = "all") -> None:
    from run_benchmark import balance, dedup, feature_frame, fit_predict, set_columns, split, to_model_matrix
    E7.mkdir(parents=True, exist_ok=True)
    table = pd.read_parquet("/data/tls-sok/tables/mta.parquet")
    cols = set_columns(table, fs)
    df, _ = dedup(table, cols)
    tr, va, te = split(df, "E2", "mta", 0)
    y = df["label"].values
    trb = balance(tr, y, 0)
    if fs == "all":  # the CNN (prep_cnn) reads these
        for name, idx in (("train", trb), ("val", va), ("test", te)):
            df.iloc[idx].reset_index(drop=True).to_parquet(E7 / f"{name}.parquet")
    x_tr, (x_va, x_te) = to_model_matrix(feature_frame(df.iloc[trb], cols),
                                         [feature_frame(df.iloc[va], cols), feature_frame(df.iloc[te], cols)])
    pickle.dump({"x_te": x_te, "y_te": y[te], "cols": cols}, open(E7 / f"test_matrix{sfx(fs)}.pkl", "wb"))
    for kind in ("xgb", "lgbm", "rf", "lr"):
        t0 = time.time()
        model = train_model(kind, x_tr, y[trb], x_va, y[va], jobs)
        pickle.dump(model, open(E7 / f"{kind}{sfx(fs)}.pkl", "wb"))
        print(kind, "trained in", round(time.time() - t0, 1), "s", flush=True)


def train_model(kind, x_tr, y_tr, x_va, y_va, jobs):
    """Same estimators and settings as run_benchmark.fit_predict, but returning the fitted object."""
    from run_benchmark import LinearPrep
    if kind == "xgb":
        import xgboost as xgb
        m = xgb.XGBClassifier(n_estimators=1000, max_depth=8, learning_rate=0.1, subsample=0.8,
                              colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
                              max_cat_to_onehot=1, n_jobs=jobs, random_state=0,
                              early_stopping_rounds=30, eval_metric="logloss")
        m.fit(x_tr, y_tr, eval_set=[(x_va, y_va)], verbose=False)
        return m
    if kind == "lgbm":
        import lightgbm as lgb
        m = lgb.LGBMClassifier(n_estimators=1000, num_leaves=63, learning_rate=0.05, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.8, n_jobs=jobs, random_state=0, verbose=-1)
        m.fit(x_tr, y_tr, eval_set=[(x_va, y_va)], callbacks=[lgb.early_stopping(30, verbose=False)])
        return m
    if kind == "rf":
        from sklearn.ensemble import RandomForestClassifier
        from run_benchmark import _numeric
        m = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, max_features="sqrt", n_jobs=jobs,
                                   random_state=0)
        m.fit(_numeric(x_tr), y_tr)
        return m
    from sklearn.linear_model import LogisticRegression
    prep_ = LinearPrep().fit(x_tr)
    m = LogisticRegression(C=1.0, max_iter=2000).fit(prep_.transform(x_tr), y_tr)
    return {"prep": prep_, "lr": m}


def prep_cnn() -> None:
    import torch
    from run_deep import tensor, train
    tr, va, te = (pd.read_parquet(E7 / f"{n}.parquet") for n in ("train", "val", "test"))
    model, ep = train(tensor(tr, True), tr["label"].values, tensor(va, True), va["label"].values, 0)
    torch.save(model.state_dict(), E7 / "cnn.pt")
    np.save(E7 / "cnn_test_x.npy", tensor(te, True))
    np.save(E7 / "cnn_test_y.npy", te["label"].values)
    print("cnn trained,", ep, "epochs", flush=True)


# ---------------------------------------------------------------- inference

def scorer(kind: str, threads: int, device: str, fs: str = "all"):
    """Load a trained model; return (score(x) -> probabilities, model bytes on disk, test x, test y)."""
    if kind == "cnn":
        import torch
        from run_deep import CNN
        torch.set_num_threads(threads)
        x, y = np.load(E7 / "cnn_test_x.npy"), np.load(E7 / "cnn_test_y.npy")
        model = CNN(x.shape[1])
        model.load_state_dict(torch.load(E7 / "cnn.pt", map_location="cpu"))
        model.to(device).eval()

        def score(xb):
            with torch.no_grad():
                out = torch.sigmoid(model(torch.from_numpy(xb).to(device)))
                return out.cpu().numpy()
        return score, os.path.getsize(E7 / "cnn.pt"), x, y
    d = pickle.load(open(E7 / f"test_matrix{sfx(fs)}.pkl", "rb"))
    m = pickle.load(open(E7 / f"{kind}{sfx(fs)}.pkl", "rb"))
    if kind == "xgb":
        m.set_params(n_jobs=threads)
        if device == "cuda":
            m.set_params(device="cuda")
        raw = m.get_booster().save_raw("ubj")
        return (lambda xb: m.predict_proba(xb)[:, 1]), len(raw), d["x_te"], d["y_te"]
    if kind == "lgbm":
        size = len(m.booster_.model_to_string().encode())
        return (lambda xb: m.predict_proba(xb, num_threads=threads)[:, 1]), size, d["x_te"], d["y_te"]
    if kind == "rf":
        from run_benchmark import _numeric
        m.set_params(n_jobs=threads)
        return (lambda xb: m.predict_proba(_numeric(xb))[:, 1]), len(pickle.dumps(m)), d["x_te"], d["y_te"]
    prep_, lr = m["prep"], m["lr"]
    return (lambda xb: lr.predict_proba(prep_.transform(xb))[:, 1]), len(pickle.dumps(m)), d["x_te"], d["y_te"]


def infer(kind: str, threads: int, device: str, tag: str, fs: str = "all") -> None:
    from sklearn.metrics import average_precision_score
    os.environ["OMP_NUM_THREADS"] = str(threads)
    rss0 = rss_mb()
    score, size, x, y = scorer(kind, threads, device, fs)
    data_mb = (x.memory_usage(deep=True).sum() if isinstance(x, pd.DataFrame) else x.nbytes) / 2**20
    take = (lambda i: x.iloc[i]) if isinstance(x, pd.DataFrame) else (lambda i: x[i])
    n = len(y)
    score(take(slice(0, 64)))  # warm-up (CUDA context, lazy init)
    rng = np.random.default_rng(0)
    lat = []
    for i in rng.integers(0, n, 2000):
        t = time.perf_counter()
        score(take(slice(int(i), int(i) + 1)))
        lat.append(time.perf_counter() - t)
    lat = np.array(lat) * 1e3
    c0, w0 = cpu_s(), time.perf_counter()
    for s in range(0, n, 1024):
        score(take(slice(s, s + 1024)))
    w_b = time.perf_counter() - w0
    c1, w1 = cpu_s(), time.perf_counter()
    s_all = score(take(slice(0, n)))
    w_all = time.perf_counter() - w1
    c2 = cpu_s()
    save({"stage": "inference", "model": kind, "feature_set": fs, "device": device, "threads": threads, "tag": tag,
          "affinity_cores": len(os.sched_getaffinity(0)), "test_flows": n, "model_bytes": size,
          "batch1_ms_median": float(np.median(lat)), "batch1_ms_p95": float(np.percentile(lat, 95)),
          "batch1_ms_p99": float(np.percentile(lat, 99)), "batch1_flows_per_s": float(1e3 / np.mean(lat)),
          "batch1024_flows_per_s": n / w_b, "batch1024_cpu_pct": 100 * (c1 - c0) / w_b,
          "full_batch_flows_per_s": n / w_all, "full_batch_cpu_pct": 100 * (c2 - c1) / w_all,
          "peak_rss_mb": rss_mb(), "rss_before_load_mb": rss0, "data_mb": data_mb,
          "test_pr_auc": float(average_precision_score(y, s_all))}, f"infer_{kind}_{device}_{tag}{sfx(fs)}")


# ---------------------------------------------------------------- extraction

def sample_pcaps(k: int = 30) -> list[str]:
    import csv
    rows = [r for r in csv.DictReader(open("/data/tls-sok/out/mta/manifest.csv")) if int(r["tls_flows"] or 0) > 0]
    random.Random(0).shuffle(rows)
    return [r["pcap"] for r in rows[:k]]


def extract_all(threads: int, tag: str, no_zeek: bool = False) -> None:
    """One child process per pcap (fresh RSS), all inheriting this process's CPU affinity."""
    import subprocess
    tag = f"{tag}_nozeek" if no_zeek else tag
    rows = []
    for p in sample_pcaps():
        r = subprocess.run([sys.executable, __file__, "extract_one", p, "--threads", str(threads)]
                           + (["--no-zeek"] if no_zeek else []), capture_output=True, text=True)
        line = [l for l in r.stdout.splitlines() if l.startswith("{")]
        rows.append(json.loads(line[-1]) if line else {"pcap": p, "error": r.stderr[-2000:]})
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"extract_{tag}.csv", index=False)
    ok = df[df.get("error", pd.Series(index=df.index, dtype=object)).isna()] if "error" in df else df
    tot = {k: float(ok[k].sum()) for k in ("pcap_bytes", "packets", "tcp_flows", "tls_flows", "wall_s", "zeek_s",
                                            "tlsfp_s", "nfstream_s", "join_s", "features_s", "cpu_s")}
    save({"stage": "extraction", "tag": tag, "zeek": not no_zeek, "threads": threads,
          "affinity_cores": len(os.sched_getaffinity(0)),
          "pcaps_ok": len(ok), "pcaps_failed": len(df) - len(ok), **tot,
          "ms_per_tcp_flow": 1e3 * tot["wall_s"] / max(tot["tcp_flows"], 1),
          "ms_per_tls_flow": 1e3 * tot["wall_s"] / max(tot["tls_flows"], 1),
          "tcp_flows_per_s": tot["tcp_flows"] / tot["wall_s"], "packets_per_s": tot["packets"] / tot["wall_s"],
          "mbit_per_s": 8 * tot["pcap_bytes"] / 1e6 / tot["wall_s"],
          "cpu_pct": 100 * tot["cpu_s"] / tot["wall_s"], "peak_rss_mb_max": float(ok["peak_rss_mb"].max())},
         f"extract_{tag}")


def extract_one(pcap: str, threads: int, no_zeek: bool = False) -> None:
    import tempfile
    sys.path.insert(0, str(HERE.parent / "src"))
    import nfstream
    from tlssok import extract as ex
    from build_tables import features, load_x509
    timers = {}

    def timed(name, fn):
        def run(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                timers[name] = timers.get(name, 0.0) + time.perf_counter() - t
        return run
    real = nfstream.NFStreamer
    ex.nfstream.NFStreamer = lambda *a, **k: real(*a, n_meters=threads, **k)
    # Zeek-free pipeline: no conn/ssl/x509 logs, so G4 validity/key/sig fields are empty; G1-G3, G5 unaffected
    ex._run_zeek = timed("zeek_s", (lambda pcap, zdir, zbin: zdir.mkdir(parents=True, exist_ok=True))
                         if no_zeek else ex._run_zeek)
    ex.parse_pcap = timed("tlsfp_s", ex.parse_pcap)
    ex._run_nfstream = timed("nfstream_s", ex._run_nfstream)
    E7.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=E7) as tmp:
        t0 = time.perf_counter()
        rep = ex.extract(Path(pcap), Path(tmp), zeek_bin="/usr/local/bin/zeek")
        t1 = time.perf_counter()
        f = pd.read_parquet(Path(tmp) / "flows.parquet") if (Path(tmp) / "flows.parquet").exists() else pd.DataFrame()
        feats = features(f, load_x509(Path(tmp) / "zeek")) if len(f) else f
        t2 = time.perf_counter()
    stages = sum(timers.values())
    print(json.dumps({"pcap": pcap, "pcap_bytes": os.path.getsize(pcap), "packets": rep.get("packets_read"),
                      "tcp_flows": rep["nfstream_tcp_rows"], "tls_flows": rep["tls_rows"], "feature_cols": feats.shape[1],
                      "wall_s": t2 - t0, **timers, "join_s": (t1 - t0) - stages, "features_s": t2 - t1,
                      "cpu_s": cpu_s() + cpu_s(resource.RUSAGE_CHILDREN),
                      "peak_rss_mb": max(rss_mb(), rss_mb(resource.RUSAGE_CHILDREN))}))


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["prep", "prep_cnn", "infer", "extract", "extract_one"])
    ap.add_argument("pcap", nargs="?")
    ap.add_argument("--model", default="xgb")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--tag", default="server")
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--set", default="all", help="prep/infer: feature set (g1g2g3 = Zeek-free option)")
    ap.add_argument("--no-zeek", action="store_true", help="extract: skip Zeek (NFStream + tlsfp only)")
    a = ap.parse_args()
    if a.mode == "prep":
        prep(a.jobs, a.set)
    elif a.mode == "prep_cnn":
        prep_cnn()
    elif a.mode == "infer":
        infer(a.model, a.threads, a.device, a.tag, a.set)
    elif a.mode == "extract":
        extract_all(a.threads, a.tag, a.no_zeek)
    else:
        extract_one(a.pcap, a.threads, a.no_zeek)
