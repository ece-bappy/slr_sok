"""Reproduce the RAID 2024 classifiers (C-Basic, C-Cert, C-Behav) from the authors' released notebooks.

Usage: python scripts/r24_reproduce.py [--grid] [--out /data/tls-sok/benchmark/r24_repro]

Runs the code cells of 02-C-ALL, 03-C-CERT and 04-C-BEHAV (github.com/CarlosANovo/extending12to13, cloned
to /data/tls-sok/ext/extending12to13) in order, in one namespace per notebook, inside a working copy
(/data/tls-sok/ext/r24) that holds the released processed-datasets/ and data/{doh,mta} archives, plus
data/ms -> our OSF download of the Metasploit dataset (certificates_length.csv), which the README says to
fetch separately. Nothing in the notebooks is edited. Deviations, all logged per cell in cells.csv:
  - cells marked "Skip this if not performing grid search again!" are skipped unless --grid; the notebooks
    then use the hard-coded best parameters that the authors recorded from their own grid search;
  - cells that read data/ucnet/* fail: UCNet (the authors' campus network) is not in the repository; the
    README links an anonymised preprocessed copy (osf.io/x6yjg), which was not downloaded here;
  - `display` prints nothing; `multiprocess` and `tqdm.notebook` are mapped to multiprocessing / tqdm;
    matplotlib, if not installed, is replaced by a no-op stub (plots only; no effect on any number).
Every result line printed as "a & b & c" (the paper's LaTeX table rows) is compared with the same cell's
stored output in the notebook, which matches the paper's Tables 2-4; the gaps are in compare.csv.
"""
import argparse
import contextlib
import io
import json
import multiprocessing
import os
import re
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

REPO = Path("/data/tls-sok/ext/extending12to13")
WORK = Path("/data/tls-sok/ext/r24")
NOTEBOOKS = ["02-C-ALL.ipynb", "03-C-CERT.ipynb", "04-C-BEHAV.ipynb"]
GRID_MARK = "Skip this if not performing grid search again!"
NUM = re.compile(r"-?\d+\.\d+")


class _NoOp:
    """Stand-in for matplotlib: every attribute and call returns another no-op (plots do not affect results)."""

    def __getattr__(self, name):
        return _NoOp()

    def __call__(self, *a, **k):
        return _NoOp()

    def __iter__(self):
        return iter((_NoOp(), _NoOp()))


def table_lines(text: str) -> list[list[float]]:
    return [[float(x) for x in NUM.findall(l)] for l in text.splitlines() if " & " in l]


def stored_text(cell) -> str:
    out = []
    for o in cell.get("outputs", []):
        t = o.get("text") or o.get("data", {}).get("text/plain") or ""
        out.append("".join(t) if isinstance(t, list) else t)
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", action="store_true", help="also run the authors' grid-search cells")
    ap.add_argument("--out", default="/data/tls-sok/benchmark/r24_repro")
    a = ap.parse_args()
    out = Path(a.out + ("_grid" if a.grid else ""))
    out.mkdir(parents=True, exist_ok=True)
    (WORK / "data").mkdir(parents=True, exist_ok=True)
    if not (WORK / "data" / "ms").exists():
        os.symlink("/data/tls-sok/raw/raid_ms", WORK / "data" / "ms")
    (WORK / "tls_paper_funcs.py").write_bytes((REPO / "tls_paper_funcs.py").read_bytes())
    import tqdm
    sys.modules["multiprocess"] = multiprocessing
    sys.modules["tqdm.notebook"] = tqdm
    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:  # not in the A2 venv and nothing new is installed: plots become no-ops
        for m in ("matplotlib", "matplotlib.pyplot", "matplotlib.ticker"):
            sys.modules[m] = _NoOp()
    os.chdir(WORK)
    sys.path.insert(0, str(WORK))
    cells, compare = [], []
    for nb_name in NOTEBOOKS:
        nb = json.loads((REPO / nb_name).read_text())
        ns = {"display": lambda *x, **k: None, "__name__": "__main__"}
        for i, c in enumerate(nb["cells"]):
            if c["cell_type"] != "code":
                continue
            src = "".join(c["source"])
            rec = {"notebook": nb_name, "cell": i}
            if GRID_MARK in src and not a.grid:
                cells.append({**rec, "status": "skipped (grid search; hard-coded best parameters used)"})
                continue
            buf, t0 = io.StringIO(), time.time()
            try:
                with contextlib.redirect_stdout(buf):
                    exec(compile(src, f"{nb_name}:cell{i}", "exec"), ns)
                status = "ok"
            except Exception as exc:
                status = f"error: {type(exc).__name__}: {str(exc)[:200]}"
                if "ucnet" in src:
                    status += " (UCNet data not downloaded: osf.io/x6yjg)"
                (out / "errors.log").open("a").write(f"--- {nb_name} cell {i}\n{traceback.format_exc()}\n")
            got = buf.getvalue()
            cells.append({**rec, "status": status, "seconds": round(time.time() - t0, 1), "stdout": got[-500:]})
            ours, theirs = table_lines(got), table_lines(stored_text(c))
            for k, (o, t) in enumerate(zip(ours, theirs)):
                compare.append({"notebook": nb_name, "cell": i, "row": k, "reported": " & ".join(f"{v:.2f}" for v in t),
                                "reproduced": " & ".join(f"{v:.2f}" for v in o),
                                "max_abs_gap_pp": max((abs(x - y) for x, y in zip(o, t)), default=float("nan"))})
            print(nb_name, i, status, got.strip()[-200:].replace("\n", " | "), flush=True)
            pd.DataFrame(cells).to_csv(out / "cells.csv", index=False)
            pd.DataFrame(compare).to_csv(out / "compare.csv", index=False)
    import sklearn
    (out / "env.json").write_text(json.dumps({"python": sys.version, "sklearn": sklearn.__version__,
                                              "pandas": pd.__version__, "paper_sklearn": "1.3.2"}))
    print(pd.DataFrame(compare).to_string())


if __name__ == "__main__":
    main()
