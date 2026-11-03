"""Unsupervised baselines (plan.md §5.3): Isolation Forest and an autoencoder, trained on benign flows only
(runs on A2, torch venv for the autoencoder's GPU).

Usage: /data/tls-sok/venv-torch/bin/python scripts/run_unsup.py [--seeds 5] [--out /data/tls-sok/benchmark/unsup]

Settings: MTA E2 and E3, MCFP E2, and E4 MCFP -> MTA, each with feature set g1g2 (with timing) and
g1g2_notime. Same splits and per-set dedup as run_benchmark.py / run_e4.py, but
  - training uses only the *benign* rows of the training split (no labels otherwise; at most 200k rows);
  - thresholds come from the *benign* rows of the validation split only: the 99th and 99.9th percentiles
    of their anomaly scores (benign-validation FPR 1e-2 and 1e-3). Malicious validation rows are unused.
In the output, macro_f1 / recall_* are at the FPR-1e-2 threshold (column thr_f1 holds that threshold, for
compatibility with metrics()), and tpr_at_val_fpr1e-3 / test_fpr_at_that_threshold at the 1e-3 one.
Input: run_benchmark.LinearPrep (signed log1p, train-median imputation + missing flags, z-scaling), fit on
the benign training rows.
Models: IsolationForest(300 trees, max_samples 256); autoencoder d -> 64 -> 16 -> 64 -> d (ReLU), MSE,
Adam 1e-3, batch 1024, at most 50 epochs, early stopping on benign-validation loss (patience 3).
Anomaly score = -score_samples (IF) or reconstruction MSE (AE).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from torch import nn

from run_benchmark import LinearPrep, bootstrap, dedup, feature_frame, metrics, set_columns, split, to_model_matrix
from run_e4 import build

TABLES = "/data/tls-sok/tables"
DEV = "cuda" if torch.cuda.is_available() else "cpu"
SETTINGS = [("mta", "E2"), ("mta", "E3"), ("mcfp", "E2"), ("mcfp>mta", "E4")]
MAX_TRAIN = 200_000


def autoencoder(x_tr, x_va, seed):
    torch.manual_seed(seed)
    d = x_tr.shape[1]
    model = nn.Sequential(nn.Linear(d, 64), nn.ReLU(), nn.Linear(64, 16), nn.ReLU(), nn.Linear(16, 64), nn.ReLU(),
                          nn.Linear(64, d)).to(DEV)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    xt, xv = torch.from_numpy(x_tr).to(DEV), torch.from_numpy(x_va).to(DEV)
    g = torch.Generator(device="cpu").manual_seed(seed)
    best, state, bad = np.inf, None, 0
    for _ in range(50):
        model.train()
        for idx in torch.randperm(len(xt), generator=g).split(1024):
            opt.zero_grad()
            b = xt[idx.to(DEV)]
            loss = ((model(b) - b) ** 2).mean()
            loss.backward()
            opt.step()
        v = recon(model, xv).mean()
        if v < best - 1e-5:
            best, state, bad = v, {k: t.clone() for k, t in model.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 3:
                break
    model.load_state_dict(state)
    return lambda x: recon(model, torch.from_numpy(x).to(DEV))


def recon(model, x):
    model.eval()
    with torch.no_grad():
        return torch.cat([((model(x[i:i + 65536]) - x[i:i + 65536]) ** 2).mean(1) for i in range(0, len(x), 65536)]
                         ).cpu().numpy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/tls-sok/benchmark/unsup")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=16)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tables = {n: pd.read_parquet(f"{TABLES}/{n}.parquet") for n in ("mta", "mcfp")}
    rows = []
    for fs in ("g1g2", "g1g2_notime"):
        cols = sorted(set(set_columns(tables["mta"], fs)) & set(set_columns(tables["mcfp"], fs)))
        d = {n: dedup(t, cols)[0] for n, t in tables.items()}
        for ds, exp in SETTINGS:
            for seed in range(a.seeds):
                if exp == "E4":
                    train, test = build(ds, d, seed)
                    y = train["label"].to_numpy()
                    tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=y, random_state=seed)
                    te_df = test
                else:
                    train = d[ds]
                    y = train["label"].to_numpy()
                    tr, va, te = split(train, exp, ds, seed)
                    te_df = train.iloc[te]
                rng = np.random.default_rng(seed)
                tr_b = tr[y[tr] == 0]
                tr_b = rng.choice(tr_b, min(len(tr_b), MAX_TRAIN), replace=False)
                va_b = va[y[va] == 0]
                m_tr, (m_va, m_te) = to_model_matrix(feature_frame(train.iloc[tr_b], cols),
                                                     [feature_frame(train.iloc[va_b], cols), feature_frame(te_df, cols)])
                prep = LinearPrep().fit(m_tr)
                x_tr, x_va, x_te = (np.nan_to_num(prep.transform(m)).astype(np.float32) for m in (m_tr, m_va, m_te))
                y_te = te_df["label"].to_numpy()
                for model in ("iforest", "autoencoder"):
                    if model == "iforest":
                        m = IsolationForest(n_estimators=300, random_state=seed, n_jobs=a.jobs).fit(x_tr)
                        score = lambda x: -m.score_samples(x)
                    else:
                        score = autoencoder(x_tr, x_va, seed)
                    s_va, s_te = score(x_va), score(x_te)
                    thr_1e2, thr_1e3 = np.quantile(s_va, 0.99), np.quantile(s_va, 0.999)
                    mt = metrics(y_te, s_te, thr_1e2, thr_1e3)
                    ci = bootstrap(y_te, s_te, thr_1e2, thr_1e3, a.boot if len(y_te) <= 200_000 else 20, seed)
                    rows.append({"setting": f"{ds}|{exp}", "model": model, "feature_set": fs, "seed": seed,
                                 "n_train_benign": len(tr_b), "n_val_benign": len(va_b), "thr_fpr1e-2": thr_1e2,
                                 "thr_fpr1e-3": thr_1e3, "test_fpr_at_val_fpr1e-2": float(
                                     (s_te[y_te == 0] >= thr_1e2).mean()), **mt,
                                 **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                    print(fs, ds, exp, model, seed, {k: round(mt[k], 4) for k in ("pr_auc", "roc_auc", "macro_f1")},
                          flush=True)
                pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
    res = pd.DataFrame(rows)
    keys = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "test_fpr_at_val_fpr1e-2",
            "tpr_at_val_fpr1e-3", "test_fpr_at_that_threshold"]
    summ = res.groupby(["setting", "model", "feature_set"], sort=False)[keys + ["n", "n_pos"]].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


if __name__ == "__main__":
    main()
