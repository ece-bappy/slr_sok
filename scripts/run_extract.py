"""Resumable batch feature extraction on A2: one output folder per pcap.

Usage (on A2, from ~/tls-sok, detached so it survives the user's PC):
  nohup setsid .venv/bin/python scripts/run_extract.py DATASET LIST.txt [--workers 6] \
      [--out /data/tls-sok/out] > /data/tls-sok/out/DATASET.nohup 2>&1 < /dev/null &

LIST.txt holds one pcap path per line, and its common prefix is stripped to name the output folders.
Each pcap is extracted into OUT/DATASET/<name>.tmp, which is renamed to OUT/DATASET/<name> once
manifest.json is written. Finished pcaps are skipped, so after a crash or reboot just run the same
command again: only unfinished pcaps are redone. A lock file stops two drivers on one dataset.
Progress: OUT/DATASET/progress.log; per-pcap errors: OUT/DATASET/_failed/<name>.err;
summary of all finished pcaps: OUT/DATASET/manifest.csv (rewritten at the end of every run).
"""
import argparse
import csv
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

HEADER_ONLY_SNAPLEN = 200  # below this, TLS handshake records cannot be in the capture


def log(path: Path, msg: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def snaplen(pcap: Path) -> int | None:
    """Snapshot length from the pcap header (capinfos), None if unknown."""
    r = subprocess.run(["capinfos", "-l", "-M", str(pcap)], capture_output=True, text=True)
    m = re.search(r"Packet size limit:\s+file hdr:\s+(\d+)", r.stdout)
    return int(m.group(1)) if m else None


def tls_visibility(tls_parquet: Path) -> dict:
    if not tls_parquet.exists():
        return {"tls_flows": 0, "with_server_hello": 0, "with_certificate": 0}
    import pandas as pd
    t = pd.read_parquet(tls_parquet, columns=["sh_selected_version", "cert_count"])
    return {"tls_flows": len(t), "with_server_hello": int(t["sh_selected_version"].notna().sum()),
            "with_certificate": int(t["cert_count"].notna().sum())}


def one(dataset: str, pcap: str, name: str, out_root: str) -> tuple[str, str, float]:
    final = Path(out_root) / name
    tmp = Path(out_root) / (name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    t0 = time.time()
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")}
    r = subprocess.run([sys.executable, "-m", "tlssok.extract", pcap, str(tmp)],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0 or not (tmp / "join_report.json").exists():
        err = Path(out_root) / "_failed" / (name.replace("/", "__") + ".err")
        err.parent.mkdir(exist_ok=True)
        err.write_text(f"returncode {r.returncode}\n--- stdout\n{r.stdout[-5000:]}\n--- stderr\n{r.stderr[-20000:]}")
        shutil.rmtree(tmp, ignore_errors=True)
        return name, "FAIL", time.time() - t0
    report = json.loads((tmp / "join_report.json").read_text())
    snap = snaplen(Path(pcap))
    vis = tls_visibility(tmp / "tls.parquet")
    # the file header can overstate it (HIKARI benign says 65535 but stores 42-94 B packets),
    # so use the largest packet actually stored
    header_only = (report.get("max_caplen") or 0) < HEADER_ONLY_SNAPLEN
    manifest = {
        "dataset": dataset, "name": name, "pcap": pcap, "pcap_bytes": os.path.getsize(pcap),
        "snaplen_header": snap, "header_only": header_only,
        # G3-G5 (handshake, certificate, JA3/JA4) need TLS records in the capture
        "handshake_features_available": (not header_only) and vis["tls_flows"] > 0,
        **vis, **report, "seconds": round(time.time() - t0, 1),
        "finished": datetime.now().isoformat(timespec="seconds"),
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2))
    if final.exists():  # left over from an older run; the new result replaces it
        shutil.rmtree(final)
    tmp.rename(final)
    return name, "DONE", manifest["seconds"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("pcap_list")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default="/data/tls-sok/out")
    a = ap.parse_args()

    root = Path(a.out) / a.dataset
    root.mkdir(parents=True, exist_ok=True)
    lock = open(root / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"another driver is already running on {root}")
    progress = root / "progress.log"

    pcaps = [p.strip() for p in open(a.pcap_list, encoding="utf-8") if p.strip()]
    prefix = os.path.commonpath(pcaps) if len(pcaps) > 1 else str(Path(pcaps[0]).parent)
    names = {p: re.sub(r"\.(pcap|pcapng)$", "", os.path.relpath(p, prefix)) for p in pcaps}
    for d in root.glob("**/*.tmp"):  # half-written outputs from an interrupted run
        shutil.rmtree(d, ignore_errors=True)
    todo = [p for p in pcaps if not (root / names[p] / "manifest.json").exists()]
    todo.sort(key=os.path.getsize, reverse=True)  # big files first, so the tail is short
    log(progress, f"RUN_START {len(pcaps)} pcaps, {len(pcaps) - len(todo)} already done, "
                  f"{len(todo)} to do, {a.workers} workers")

    done = failed = 0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, a.dataset, p, names[p], str(root)): p for p in todo}
        for f in as_completed(futs):
            try:
                name, status, secs = f.result()
            except Exception as e:  # the worker itself crashed
                name, status, secs = names[futs[f]], f"FAIL ({type(e).__name__}: {e})", 0.0
            done += status == "DONE"
            failed += status != "DONE"
            log(progress, f"{status.split()[0]} {name} {secs:.0f}s [{done + failed}/{len(todo)}]")

    rows = [json.loads(m.read_text()) for m in sorted(root.glob("**/manifest.json"))]
    if rows:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(root / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    log(progress, f"RUN_FINISHED done {done} failed {failed}; {len(rows)}/{len(pcaps)} pcaps have output")


if __name__ == "__main__":
    main()
