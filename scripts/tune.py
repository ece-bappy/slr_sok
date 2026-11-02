"""XGBoost hyperparameter tuning with Optuna on the headline E2/E3/E4 settings (runs on A2).

Usage: python scripts/tune.py [--trials 40] [--seeds 5] [--jobs 16] [--out /data/tls-sok/benchmark/tuning]

Per setting: TPE search (fixed budget of --trials, seed 0) on the seed-0 split, objective = PR-AUC on the
**source validation set** (the same set used for early stopping and thresholds; the test set and the
target dataset are never seen). The best parameters are then refit for every seed and scored on test,
next to the fixed defaults, with the same protocol as run_benchmark.py / run_e4.py.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split

from run_benchmark import (balance, bootstrap, dedup, feature_frame, fit_predict, metrics, set_columns, split,
                           thresholds, to_model_matrix)

SETTINGS = [("mta", "all", "E2"), ("mta", "all", "E3"), ("mta", "g1g2_notime", "E2"), ("mta", "g1g2_notime", "E3"),
            ("mcfp", "all", "E2"), ("mcfp", "g1g2_notime", "E2"),
            ("mcfp>mta", "g1g2_notime", "E4"), ("mta>mcfp", "g1g2_notime", "E4")]


def data(tables: dict, ds: str, fs: str, exp: str, seed: int, cache: dict):
    """(x_tr, y_tr, x_va, y_va, x_te, y_te) with training balanced 1:1, as in the benchmark scripts."""
    names = ds.split(">")
    cols = sorted(set.intersection(*(set(set_columns(tables[n], fs)) for n in names)))
    for n in names:
        if (n, fs) not in cache:
            cache[(n, fs)] = dedup(tables[n], cols if exp == "E4" else set_columns(tables[n], fs))[0]
    if exp == "E4":
        train, test = cache[(names[0], fs)], cache[(names[1], fs)]
        y = train["label"].values
        tr, va = train_test_split(np.arange(len(train)), test_size=0.15, stratify=y, random_state=seed)
        te_df = test
    else:
        train = cache[(ds, fs)]
        y = train["label"].values
        tr, va, te = split(train, exp, ds, seed)
        te_df = train.iloc[te]
    trb = balance(tr, y, seed)
    x_tr, (x_va, x_te) = to_model_matrix(feature_frame(train.iloc[trb], cols),
                                         [feature_frame(train.iloc[va], cols), feature_frame(te_df, cols)])
    return x_tr, y[trb], x_va, y[va], x_te, te_df["label"].values


def space(trial: optuna.Trial) -> dict:
    return {"n_estimators": 2000, "early_stopping_rounds": 50,
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
            "min_child_weight": trial.suggest_float("min_child_weight", 1, 50, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 30, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10, log=True),
            "gamma": trial.suggest_float("gamma", 0, 5)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="/data/tls-sok/tables")
    ap.add_argument("--out", default="/data/tls-sok/benchmark/tuning")
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=100)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--settings", default=None, help="comma-separated indices into SETTINGS (default: all)")
    a = ap.parse_args()
    settings = [SETTINGS[int(i)] for i in a.settings.split(",")] if a.settings else SETTINGS
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tables = {n: pd.read_parquet(f"{a.tables}/{n}.parquet") for n in ("mta", "mcfp")}
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    done = pd.read_csv(out / "results_per_seed.csv") if (out / "results_per_seed.csv").exists() else pd.DataFrame()
    rows, best_all = done.to_dict("records"), json.loads((out / "best_params.json").read_text()) \
        if (out / "best_params.json").exists() else {}

    for ds, fs, exp in settings:
        key = f"{ds}|{fs}|{exp}"
        if key in best_all:  # resumable: settings already finished are skipped
            continue
        cache = {}
        x_tr, y_tr, x_va, y_va, _, _ = data(tables, ds, fs, exp, 0, cache)

        def objective(trial):
            s_va, _, _, _ = fit_predict("xgb", x_tr, y_tr, x_va, y_va, [], 0, a.jobs, space(trial))
            return average_precision_score(y_va, s_va)
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
        study.optimize(objective, n_trials=a.trials)
        best = {**space(optuna.trial.FixedTrial(study.best_params)), "val_pr_auc": study.best_value}
        print(key, "best val PR-AUC", round(study.best_value, 5), study.best_params, flush=True)
        study.trials_dataframe().to_csv(out / f"trials_{key.replace('|', '_').replace('>', '-')}.csv", index=False)
        for seed in range(a.seeds):
            x_tr_s, y_tr_s, x_va_s, y_va_s, x_te, y_te = data(tables, ds, fs, exp, seed, cache)
            for variant, params in (("default", None), ("tuned", {k: v for k, v in best.items() if k != "val_pr_auc"})):
                s_va, (s_te,), it, _ = fit_predict("xgb", x_tr_s, y_tr_s, x_va_s, y_va_s, [x_te], seed, a.jobs, params)
                thr_f1, thr_fpr = thresholds(y_va_s, s_va)
                m = metrics(y_te, s_te, thr_f1, thr_fpr)
                ci = bootstrap(y_te, s_te, thr_f1, thr_fpr, a.boot if len(y_te) <= 200_000 else 20, seed)
                rows.append({"setting": key, "dataset": ds, "feature_set": fs, "experiment": exp, "variant": variant,
                             "seed": seed, "best_iteration": it, "val_pr_auc": average_precision_score(y_va_s, s_va),
                             **m, **{k: f"{v[0]:.4f}-{v[1]:.4f}" for k, v in ci.items()}})
                print(key, variant, seed, round(m["pr_auc"], 4), round(m["macro_f1"], 4), flush=True)
        best_all[key] = best
        pd.DataFrame(rows).to_csv(out / "results_per_seed.csv", index=False)
        (out / "best_params.json").write_text(json.dumps(best_all, indent=2))

    res = pd.DataFrame(rows)
    keys = ["val_pr_auc", "pr_auc", "roc_auc", "macro_f1", "recall_malicious", "recall_benign",
            "tpr_at_val_fpr1e-3", "test_fpr_at_that_threshold"]
    summ = res.groupby(["setting", "variant"], sort=False)[keys].agg(["mean", "std"])
    summ.columns = [f"{k}_{s}" for k, s in summ.columns]
    summ.reset_index().to_csv(out / "summary.csv", index=False)
    print(summ.to_string())


if __name__ == "__main__":
    main()
