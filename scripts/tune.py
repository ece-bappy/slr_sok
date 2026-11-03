"""Hyperparameter tuning with Optuna on the headline E2/E3/E4 settings (runs on A2).

Usage: python scripts/tune.py [--model xgb|lgbm|rf|lr|cnn|bilstm] [--trials 40] [--seeds 5] [--jobs 16]
       [--out DIR] [--settings 0,1,...] [--timeout SECONDS]
The deep models (cnn, bilstm) run under the torch venv; if optuna is not installed there, the main
venv's site-packages are appended to sys.path (both venvs are Python 3.12), so nothing is installed.

Per setting: TPE search (fixed budget of --trials, seed 0) on the seed-0 split, objective = PR-AUC on the
**source validation set** (the same set used for early stopping and thresholds; the test set and the
target dataset are never seen). The best parameters are then refit for every seed and scored on test,
next to the fixed defaults, with the same protocol as run_benchmark.py / run_e4.py / run_deep.py.
--timeout caps each setting's search in seconds (deep models only need it; the trial count still caps it).
Deep models use the G2 packet sequence only, so settings with feature set `all` are skipped for them and
g1g2_notime maps to the CNN/BiLSTM no-timing input.
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import optuna
except ImportError:  # torch venv: borrow optuna from the main venv (same Python version) without installing
    sys.path.append(str(Path.home() / "tls-sok/.venv/lib/python3.12/site-packages"))
    import optuna
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split

from run_benchmark import (balance, bootstrap, dedup, feature_frame, fit_predict, metrics, set_columns, split,
                           thresholds, to_model_matrix)

SETTINGS = [("mta", "all", "E2"), ("mta", "all", "E3"), ("mta", "g1g2_notime", "E2"), ("mta", "g1g2_notime", "E3"),
            ("mcfp", "all", "E2"), ("mcfp", "g1g2_notime", "E2"),
            ("mcfp>mta", "g1g2_notime", "E4"), ("mta>mcfp", "g1g2_notime", "E4")]
DEEP = ("cnn", "bilstm")


def data(tables: dict, ds: str, fs: str, exp: str, seed: int, cache: dict):
    """(x_tr, y_tr, x_va, y_va, x_te, y_te) with training balanced 1:1, as in the benchmark scripts."""
    names = ds.split(">")
    cols = sorted(set.intersection(*(set(set_columns(tables[n], fs)) for n in names)))
    for n in names:
        if (n, fs) not in cache:
            cache[(n, fs)] = dedup(tables[n], cols if exp == "E4" else set_columns(tables[n], fs))[0]
    train, te_df, tr, va = splits(cache, names, ds, exp, seed, fs)
    y = train["label"].values
    trb = balance(tr, y, seed)
    x_tr, (x_va, x_te) = to_model_matrix(feature_frame(train.iloc[trb], cols),
                                         [feature_frame(train.iloc[va], cols), feature_frame(te_df, cols)])
    return x_tr, y[trb], x_va, y[va], x_te, te_df["label"].values


def splits(cache, names, ds, exp, seed, key):
    if exp == "E4":
        train, te_df = cache[(names[0], key)], cache[(names[1], key)]
        tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=train["label"].values,
                                  random_state=seed)
    else:
        train = cache[(ds, key)]
        tr, va, te = split(train, exp, ds, seed)
        te_df = train.iloc[te]
    return train, te_df, tr, va


def data_deep(tables: dict, ds: str, fs: str, exp: str, seed: int, cache: dict):
    from run_deep import g2_cols, tensor
    timing = fs != "g1g2_notime"
    names = ds.split(">")
    for n in names:
        if (n, fs) not in cache:
            cache[(n, fs)] = dedup(tables[n], g2_cols(timing))[0]
    train, te_df, tr, va = splits(cache, names, ds, exp, seed, fs)
    y = train["label"].values
    trb = balance(tr, y, seed)
    x = tensor(train, timing)
    return x[trb], y[trb], x[va], y[va], tensor(te_df, timing), te_df["label"].values


def space(model: str, trial: optuna.Trial) -> dict:
    f, i = trial.suggest_float, trial.suggest_int
    if model == "xgb":
        return {"n_estimators": 2000, "early_stopping_rounds": 50, "max_depth": i("max_depth", 3, 12),
                "learning_rate": f("learning_rate", 0.01, 0.3, log=True), "subsample": f("subsample", 0.5, 1.0),
                "colsample_bytree": f("colsample_bytree", 0.3, 1.0),
                "min_child_weight": f("min_child_weight", 1, 50, log=True),
                "reg_lambda": f("reg_lambda", 1e-3, 30, log=True), "reg_alpha": f("reg_alpha", 1e-4, 10, log=True),
                "gamma": f("gamma", 0, 5)}
    if model == "lgbm":
        return {"n_estimators": 2000, "early_stopping_rounds": 50, "num_leaves": i("num_leaves", 15, 255, log=True),
                "learning_rate": f("learning_rate", 0.01, 0.3, log=True), "subsample": f("subsample", 0.5, 1.0),
                "colsample_bytree": f("colsample_bytree", 0.3, 1.0),
                "min_child_samples": i("min_child_samples", 5, 200, log=True),
                "reg_lambda": f("reg_lambda", 1e-3, 30, log=True), "reg_alpha": f("reg_alpha", 1e-4, 10, log=True)}
    if model == "rf":
        return {"n_estimators": i("n_estimators", 100, 600, log=True), "max_depth": i("max_depth", 4, 40, log=True),
                "min_samples_leaf": i("min_samples_leaf", 1, 30, log=True),
                "max_features": f("max_features", 0.05, 0.7, log=True),
                "class_weight": trial.suggest_categorical("class_weight", [None, "balanced_subsample"])}
    if model == "lr":
        return {"C": f("C", 1e-3, 100, log=True), "top_k": i("top_k", 5, 100, log=True)}
    return {"lr": f("lr", 1e-4, 3e-3, log=True), "width": trial.suggest_categorical("width", [32, 64, 128]),
            "dropout": f("dropout", 0.0, 0.5), "batch": trial.suggest_categorical("batch", [256, 512, 1024]),
            "weight_decay": f("weight_decay", 1e-6, 1e-3, log=True)}


def fit_score(model, x_tr, y_tr, x_va, y_va, others, seed, jobs, params):
    """(validation scores, [other scores], best iteration) for any family, including the deep ones."""
    if model in DEEP:
        from run_deep import scores, train
        m, ep = train(x_tr, y_tr, x_va, y_va, seed, model, params)
        return scores(m, x_va), [scores(m, x) for x in others], ep
    s_va, s_o, it, _ = fit_predict(model, x_tr, y_tr, x_va, y_va, others, seed, jobs, params)
    return s_va, s_o, it


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="/data/tls-sok/tables")
    ap.add_argument("--model", default="xgb", choices=["xgb", "lgbm", "rf", "lr", *DEEP])
    ap.add_argument("--out", default=None, help="default /data/tls-sok/benchmark/tuning (xgb) or tuning_<model>")
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=100)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("--settings", default=None, help="comma-separated indices into SETTINGS (default: all)")
    a = ap.parse_args()
    settings = [SETTINGS[int(i)] for i in a.settings.split(",")] if a.settings else SETTINGS
    if a.model in DEEP:
        settings = [s for s in settings if s[1] != "all"]
    out = Path(a.out or ("/data/tls-sok/benchmark/tuning" + ("" if a.model == "xgb" else f"_{a.model}")))
    out.mkdir(parents=True, exist_ok=True)
    tables = {n: pd.read_parquet(f"{a.tables}/{n}.parquet") for n in ("mta", "mcfp")}
    load = data_deep if a.model in DEEP else data
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    done = pd.read_csv(out / "results_per_seed.csv") if (out / "results_per_seed.csv").exists() else pd.DataFrame()
    rows, best_all = done.to_dict("records"), json.loads((out / "best_params.json").read_text()) \
        if (out / "best_params.json").exists() else {}

    for ds, fs, exp in settings:
        key = f"{ds}|{fs}|{exp}"
        if key in best_all:  # resumable: settings already finished are skipped
            continue
        cache = {}
        x_tr, y_tr, x_va, y_va, _, _ = load(tables, ds, fs, exp, 0, cache)

        def objective(trial):
            s_va, _, _ = fit_score(a.model, x_tr, y_tr, x_va, y_va, [], 0, a.jobs, space(a.model, trial))
            return average_precision_score(y_va, s_va)
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
        study.optimize(objective, n_trials=a.trials, timeout=a.timeout)
        best = {**space(a.model, optuna.trial.FixedTrial(study.best_params)), "val_pr_auc": study.best_value,
                "n_trials_run": len(study.trials)}
        print(key, "best val PR-AUC", round(study.best_value, 5), len(study.trials), "trials", study.best_params,
              flush=True)
        study.trials_dataframe().to_csv(out / f"trials_{key.replace('|', '_').replace('>', '-')}.csv", index=False)
        for seed in range(a.seeds):
            x_tr_s, y_tr_s, x_va_s, y_va_s, x_te, y_te = load(tables, ds, fs, exp, seed, cache)
            for variant, params in (("default", None),
                                    ("tuned", {k: v for k, v in best.items() if k not in ("val_pr_auc", "n_trials_run")})):
                s_va, (s_te,), it = fit_score(a.model, x_tr_s, y_tr_s, x_va_s, y_va_s, [x_te], seed, a.jobs, params)
                thr_f1, thr_fpr = thresholds(y_va_s, s_va)
                m = metrics(y_te, s_te, thr_f1, thr_fpr)
                ci = bootstrap(y_te, s_te, thr_f1, thr_fpr, a.boot if len(y_te) <= 200_000 else 20, seed)
                rows.append({"setting": key, "dataset": ds, "feature_set": fs, "experiment": exp, "model": a.model,
                             "variant": variant, "seed": seed, "best_iteration": it,
                             "val_pr_auc": average_precision_score(y_va_s, s_va),
                             **m, **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                print(key, variant, seed, round(m["pr_auc"], 4), round(m["macro_f1"], 4), flush=True)
        best_all[key] = best
        pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
        (out / "best_params.json").write_text(json.dumps(best_all, indent=2, default=str))

    res = pd.DataFrame(rows)
    keys = ["val_pr_auc", "pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign",
            "tpr_at_val_fpr1e-3", "test_fpr_at_that_threshold"]
    summ = res.groupby(["setting", "variant"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


if __name__ == "__main__":
    main()
