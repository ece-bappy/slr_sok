"""Deep packet-sequence models (1D-CNN, BiLSTM) for E2/E3/E4 headline settings (runs on A2's GPU, torch venv).

Usage: /data/tls-sok/venv-torch/bin/python scripts/run_deep.py {within,e4} [--seeds 5] [--arch cnn|bilstm]

Input: the first 20 packets of each flow (G2): signed size (direction x size / 1500), direction, and
log1p(inter-arrival ms); the *_notime variant drops the inter-arrival channel. No TLS fields, so the
model sits in the TLS 1.3 + ECH visibility tier. Same protocol as run_benchmark.py / run_e4.py:
per-table dedup on the G2 columns, 1:1 training balance, validation-only early stopping and thresholds,
5 seeds, bootstrap CIs.
Models: CNN = Conv1d(C->64, k3) -> ReLU -> Conv1d(64->64, k3) -> ReLU -> global max pool -> Linear(64->1);
BiLSTM = 1-layer bidirectional LSTM (hidden 64 per direction) over the 20 packets -> max pool over time ->
Linear(128->1). Both: Adam 1e-3, batch 512, at most 30 epochs, early stopping on validation loss
(patience 3). train() takes an optional hyperparameter dict (used by tune.py only).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from torch import nn

from run_benchmark import balance, bootstrap, dedup, metrics, split, thresholds
from run_e4 import PAIRS, build

TABLES = "/data/tls-sok/tables"
OUT = Path("/data/tls-sok/benchmark")
N = 20
DEV = "cuda" if torch.cuda.is_available() else "cpu"


def g2_cols(timing: bool) -> list[str]:
    kinds = ("ps", "dir", "piat") if timing else ("ps", "dir")
    return [f"g2_{k}_{i:02d}" for k in kinds for i in range(N)]


def tensor(df: pd.DataFrame, timing: bool) -> np.ndarray:
    ps = df[[f"g2_ps_{i:02d}" for i in range(N)]].to_numpy(float)
    dr = df[[f"g2_dir_{i:02d}" for i in range(N)]].to_numpy(float)
    seen = ps >= 0
    sign = np.where(dr == 1, -1.0, 1.0)
    chans = [np.where(seen, sign * ps / 1500.0, 0.0), np.where(seen, dr, -1.0)]
    if timing:
        iat = df[[f"g2_piat_{i:02d}" for i in range(N)]].to_numpy(float)
        chans.append(np.where(seen, np.log1p(np.clip(iat, 0, None)), 0.0))
    return np.stack(chans, 1).astype(np.float32)  # (rows, channels, 20)


class CNN(nn.Module):
    def __init__(self, c: int, width: int = 64, dropout: float = 0.0):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(c, width, 3, padding=1), nn.ReLU(), nn.Conv1d(width, width, 3, padding=1),
                                 nn.ReLU(), nn.AdaptiveMaxPool1d(1), nn.Flatten(), nn.Dropout(dropout),
                                 nn.Linear(width, 1))

    def forward(self, x):
        return self.net(x).squeeze(1)


class BiLSTM(nn.Module):
    def __init__(self, c: int, width: int = 64, dropout: float = 0.0):
        super().__init__()
        self.lstm = nn.LSTM(c, width, batch_first=True, bidirectional=True)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(2 * width, 1))

    def forward(self, x):  # x: (batch, channels, 20) as for the CNN
        out, _ = self.lstm(x.transpose(1, 2))
        return self.head(out.max(dim=1).values).squeeze(1)


ARCH = {"cnn": (CNN, "cnn1d"), "bilstm": (BiLSTM, "bilstm")}


def scores(model, x: np.ndarray) -> np.ndarray:
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(x), 8192):
            out.append(torch.sigmoid(model(torch.from_numpy(x[i:i + 8192]).to(DEV))).cpu().numpy())
    return np.concatenate(out) if out else np.array([])


def train(x_tr, y_tr, x_va, y_va, seed: int, arch: str = "cnn", hp: dict | None = None):
    hp = {"lr": 1e-3, "batch": 512, "width": 64, "dropout": 0.0, "weight_decay": 0.0, **(hp or {})}
    torch.manual_seed(seed)
    model = ARCH[arch][0](x_tr.shape[1], hp["width"], hp["dropout"]).to(DEV)
    opt = torch.optim.Adam(model.parameters(), lr=hp["lr"], weight_decay=hp["weight_decay"])
    loss_fn = nn.BCEWithLogitsLoss()
    xt, yt = torch.from_numpy(x_tr), torch.from_numpy(y_tr.astype(np.float32))
    xv, yv = torch.from_numpy(x_va).to(DEV), torch.from_numpy(y_va.astype(np.float32)).to(DEV)
    best, best_state, bad, epochs = np.inf, None, 0, 0
    g = torch.Generator().manual_seed(seed)
    for epoch in range(30):
        model.train()
        for idx in torch.randperm(len(xt), generator=g).split(int(hp["batch"])):
            opt.zero_grad()
            loss = loss_fn(model(xt[idx].to(DEV)), yt[idx].to(DEV))
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            v = sum(loss_fn(model(xv[i:i + 8192]), yv[i:i + 8192]).item() * len(xv[i:i + 8192])
                    for i in range(0, len(xv), 8192)) / len(xv)
        epochs = epoch + 1
        if v < best - 1e-4:
            best, best_state, bad = v, {k: t.clone() for k, t in model.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 3:
                break
    model.load_state_dict(best_state)
    return model, epochs


def evaluate(base, y_va, s_va, y_te, s_te, vers, boot, seed, rows, ver_rows, extra):
    thr_f1, thr_fpr = thresholds(y_va, s_va)
    m = metrics(y_te, s_te, thr_f1, thr_fpr)
    ci = bootstrap(y_te, s_te, thr_f1, thr_fpr, boot if len(y_te) <= 200_000 else max(20, boot // 4), seed)
    rows.append({**base, **extra, "thr_f1": thr_f1, "thr_fpr": thr_fpr, **m,
                 **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
    for v in np.unique(vers):
        i = vers == v
        ver_rows.append({**base, "tls_version": v, **metrics(y_te[i], s_te[i], thr_f1, thr_fpr)})
    print(base, {k: round(m[k], 4) for k in ("pr_auc", "macro_f1", "recall_malicious", "recall_benign")}, flush=True)


KEYS = ["pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign", "tpr_at_val_fpr1e-3",
        "test_fpr_at_that_threshold", "accuracy"]


def within(seeds: int, boot: int, datasets: str, out_name: str, arch: str = "cnn") -> None:
    rows, ver_rows = [], []
    name = ARCH[arch][1]
    plan = {"mta": ("E2", "E3"), "hikari": ("E2", "E3"), "mcfp": ("E2",), "raid": ("E2",)}
    plan = {k: v for k, v in plan.items() if k in datasets.split(",")}
    for ds, exps in plan.items():
        table = pd.read_parquet(f"{TABLES}/{ds}.parquet")
        for timing in (True, False):
            fs = "cnn_g2" if timing else "cnn_g2_notime"
            df, _ = dedup(table, g2_cols(timing))
            y, x = df["label"].to_numpy(), tensor(df, timing)
            for exp in exps:
                for seed in range(seeds):
                    sp = split(df, exp, ds, seed)
                    base = {"dataset": ds, "model": name, "feature_set": fs, "experiment": exp, "seed": seed}
                    if isinstance(sp, str):
                        rows.append({**base, "status": sp})
                        break
                    tr, va, te = sp
                    trb = balance(tr, y, seed)
                    model, ep = train(x[trb], y[trb], x[va], y[va], seed, arch)
                    evaluate(base, y[va], scores(model, x[va]), y[te], scores(model, x[te]),
                             df["k_tls_version"].to_numpy()[te], boot, seed, rows, ver_rows,
                             {"status": "ok", "n_train_balanced": len(trb), "epochs": ep})
    save(OUT / out_name, rows, ver_rows, ["dataset", "model", "feature_set", "experiment"])


def e4(seeds: int, boot: int, out_name: str, arch: str = "cnn") -> None:
    rows, ver_rows = [], []
    name = ARCH[arch][1]
    tables = {n: pd.read_parquet(f"{TABLES}/{n}.parquet") for n in ("mta", "mcfp", "raid")}
    for timing in (True, False):
        fs = "cnn_g2" if timing else "cnn_g2_notime"
        d = {n: dedup(t, g2_cols(timing))[0] for n, t in tables.items()}
        for pair in PAIRS:
            for seed in range(seeds):
                train_df, test_df = build(pair, d, seed)
                y = train_df["label"].to_numpy()
                tr, va = train_test_split(np.arange(len(train_df)), test_size=0.15, stratify=y, random_state=seed)
                trb = balance(tr, y, seed)
                x = tensor(train_df, timing)
                model, ep = train(x[trb], y[trb], x[va], y[va], seed, arch)
                base = {"pair": pair, "model": name, "feature_set": fs, "seed": seed}
                evaluate(base, y[va], scores(model, x[va]), test_df["label"].to_numpy(),
                         scores(model, tensor(test_df, timing)), test_df["k_tls_version"].to_numpy(), boot, seed,
                         rows, ver_rows, {"n_train_balanced": len(trb), "epochs": ep})
    save(OUT / out_name, rows, ver_rows, ["pair", "model", "feature_set"])


def save(out: Path, rows, ver_rows, by) -> None:
    out.mkdir(parents=True, exist_ok=True)
    res = pd.DataFrame(rows)
    res.to_csv(out / "results_per_seed.csv", index=False)
    pd.DataFrame(ver_rows).to_csv(out / "results_per_tls_version.csv", index=False)
    ok = res[res.get("status", pd.Series("ok", index=res.index)).fillna("ok") == "ok"]
    summ = ok.groupby(by, sort=False)[KEYS].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ = summ.reset_index()
    if "status" in res:
        summ = pd.concat([summ, res[res["status"].fillna("ok") != "ok"][by + ["status"]].drop_duplicates()])
    summ.to_csv(out / "summary.csv", index=False)
    (out / "device.json").write_text(json.dumps({"device": DEV, "torch": torch.__version__}))
    print(summ.to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["within", "e4"])
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--datasets", default="mta,hikari,mcfp,raid", help="within only")
    ap.add_argument("--name", default=None, help="output folder (default deep / e4_deep)")
    ap.add_argument("--arch", default="cnn", choices=list(ARCH))
    ap.add_argument("--pairs", default=",".join(PAIRS), help="e4 only")
    a = ap.parse_args()
    if a.part == "within":
        within(a.seeds, a.boot, a.datasets, a.name or "deep", a.arch)
    else:
        PAIRS[:] = a.pairs.split(",")
        e4(a.seeds, a.boot, a.name or "e4_deep", a.arch)
