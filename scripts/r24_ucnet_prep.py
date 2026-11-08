"""Rebuild the RAID 2024 notebooks' UCNet input files from the released UCNet table (runs on A2).

Usage: python scripts/r24_ucnet_prep.py [--jobs 24]

The authors released one anonymised Joy table for UCNet (OSF osf.io/x6yjg, processed_all.csv, 10.1M TLS
flows; downloaded to /data/tls-sok/raw/ucnet/ and checked against OSF's MD5/SHA-256). Their notebooks read
four files from data/ucnet/:
  all.csv              the Joy table itself                      -> symlink to processed_all.csv
  all_data12.csv       TLS 1.2 flows, application-data records  -> tls_12_appdata_filtering + remove_empty
  all_data13.csv       TLS 1.3 flows, application-data records  -> same, plus cert_size_guess_simple
                       (cert_size_inference_simple_diagram on the full row, for flows without PSK)
  all_behav13_new.csv  TLS 1.3 after handshake removal          -> handshake_removal_only, empty rows dropped
The three derived files are not released, and neither is the notebook that made them. This script rebuilds
them with the authors' own functions (tls_paper_funcs.py), step for step as their 01-3-Tranco notebook does
for the Tranco data, with their TLS-version rule from 02-C-ALL. It is our reconstruction; the stage counts it
prints (ucnet_prep.json) can be checked against the counts in the paper's Section 6.
"""
import argparse
import contextlib
import io
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/data/tls-sok/ext/extending12to13")
sys.path.insert(0, str(REPO))
from tls_paper_funcs import (cert_size_inference_simple_diagram, handshake_removal_only,  # noqa: E402
                             remove_empty, tls_12_appdata_filtering)

SRC = Path("/data/tls-sok/raw/ucnet/processed_all.csv")
DST = Path("/data/tls-sok/ext/r24/data/ucnet")
OUT = Path("/data/tls-sok/benchmark/r24_repro_ucnet")
BS, DS = [f"tls_b_{i}" for i in range(20)], [f"tls_dir_{i}" for i in range(20)]
ID = ["c_port", "s_port", "ip_proto", "c_tls_version", "s_tls_version", "c_supported_versions",
      "s_supported_versions", "c_psk_present", "c_psk_kem", "s_psk", "hello_retry_req", "processed_sni",
      "s_cert_lengths", "first_hs_tp", "source_file", "tls_version_guess"]


def version_guess(df: pd.DataFrame) -> pd.Series:
    """The authors' rule (02-C-ALL cell 47 / 03-C-CERT cell 47), verbatim."""
    g = pd.Series("TLS 1.2", index=df.index)
    g[(df["c_tls_version"] == 5) & (df["s_tls_version"] == 5) &
      (df["c_supported_versions"] != "-1") & (df["c_supported_versions"] != "") &
      ((df["s_supported_versions"] == "7f17") | (df["s_supported_versions"] == "fb1a") |
       (df["s_supported_versions"] == "304") | (df["s_supported_versions"] == 304) |
       (df["s_supported_versions"] == "0304"))] = "TLS 1.3"
    return g


def _safe_infer(row, i):
    """The authors' function raises ValueError (max() of an empty list) when cutting at the Finished record
    leaves no records; treat that as a failed inference (-2, counted separately; downstream it is like -1)."""
    try:
        return cert_size_inference_simple_diagram(row, i)
    except ValueError:
        return -2


def _infer(chunk: pd.DataFrame) -> np.ndarray:
    with contextlib.redirect_stdout(io.StringIO()):
        return np.array([_safe_infer(chunk.iloc[i], i) for i in range(len(chunk))], float)


def _behav(chunk: pd.DataFrame) -> np.ndarray:
    out = np.full((len(chunk), 40), -1, dtype=np.int64)
    for i in range(len(chunk)):
        b, d = handshake_removal_only(chunk.iloc[i])
        b, d = list(b)[:20], list(d)[:20]
        out[i, :len(b)], out[i, 20:20 + len(d)] = b, d
    return out


def parallel(fn, df: pd.DataFrame, jobs: int):
    parts = np.array_split(np.arange(len(df)), max(1, jobs * 8))
    with Pool(jobs) as p:
        res = p.map(fn, [df.iloc[ix] for ix in parts if len(ix)])
    return np.concatenate(res) if res else np.array([])


SLIM_KEEP = (["c_tls_version", "s_tls_version", "c_supported_versions", "s_supported_versions", "s_psk",
              "hello_retry_req", "s_cert_lengths", "first_hs_tp", "tls_version_guess", "cert_size_guess_simple"]
             + BS + DS + [f"tls_tp_{i}" for i in range(20)])


def slim() -> None:
    """Drop the columns the notebooks' UCNet cells never read (inter-arrival times, SNI, source file, ports),
    so that the 11M-flow table fits in A2's 30 GB next to the notebooks' own data. Streams the CSV text with the
    csv module, so every kept field is byte-identical (the notebooks' type inference is unchanged). The full
    files are kept as *.full.csv; all.csv becomes a slim copy of processed_all.csv instead of a symlink."""
    import csv
    csv.field_size_limit(1 << 30)
    for name in ("all.csv", "all_data12.csv", "all_data13.csv", "all_behav13_new.csv"):
        src = SRC if name == "all.csv" else DST / name.replace(".csv", ".full.csv")
        if name != "all.csv" and not src.exists():
            (DST / name).rename(src)
        if (DST / name).is_symlink():
            (DST / name).unlink()
        with open(src, newline="") as fi, open(DST / f"{name}.tmp", "w", newline="") as fo:
            r, w = csv.reader(fi), csv.writer(fo, lineterminator="\n")
            head = next(r)
            keep = [i for i, c in enumerate(head) if c in SLIM_KEEP or (i == 0 and c == "")]  # keep the index column
            w.writerow([head[i] for i in keep])
            for row in r:
                w.writerow([row[i] for i in keep])
        (DST / f"{name}.tmp").rename(DST / name)
        print(name, "kept", len(keep), "of", len(head), "columns", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--slim", action="store_true", help="only rewrite data/ucnet/*.csv without unused columns")
    a = ap.parse_args()
    if a.slim:
        slim()
        return
    DST.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if not (DST / "all.csv").exists():
        os.symlink(SRC, DST / "all.csv")
    df = pd.read_csv(SRC, dtype={"c_supported_versions": str, "s_supported_versions": str}, low_memory=False)
    df = df.drop(columns=[c for c in df.columns if c.startswith("tls_ipt_")])
    df["tls_version_guess"] = version_guess(df)
    n = {"flows": len(df), "tls12": int((df.tls_version_guess == "TLS 1.2").sum()),
         "tls13": int((df.tls_version_guess == "TLS 1.3").sum())}

    d12 = tls_12_appdata_filtering(df[df.tls_version_guess == "TLS 1.2"])
    n["tls12_no_appdata_removed"] = int((d12[BS] == -1).all(axis=1).sum())
    remove_empty(d12)
    d12[ID] = df.loc[d12.index, ID]
    d12.to_csv(DST / "all_data12.csv")
    n["all_data12_rows"] = len(d12)
    del d12

    t13 = df[df.tls_version_guess == "TLS 1.3"]
    del df
    cert = np.full(len(t13), -1.0)
    ok = ((t13["s_psk"] == -1) & (t13["hello_retry_req"] == 0)).to_numpy()
    cols = BS + DS + [f"tls_tp_{i}" for i in range(20)]
    cert[ok] = parallel(_infer, t13.loc[ok, cols].reset_index(drop=True), a.jobs)
    n["tls13_cert_inference_raised_valueerror"] = int((cert == -2).sum())
    cert[cert == -2] = -1
    n.update({"tls13_psk": int((t13["s_psk"] != -1).sum()), "tls13_hrr": int((t13["hello_retry_req"] != 0).sum()),
              "tls13_cert_inferred": int((cert > -1).sum()), "tls13_cert_inference_failed": int((ok & (cert == -1)).sum())})
    d13 = tls_12_appdata_filtering(t13).astype(int)
    d13["cert_size_guess_simple"] = cert
    n["tls13_no_appdata_removed"] = int((d13[BS] == -1).all(axis=1).sum())
    remove_empty(d13)
    d13[ID] = t13.loc[d13.index, ID]
    d13.to_csv(DST / "all_data13.csv")
    n["all_data13_rows"] = len(d13)

    beh = parallel(_behav, d13[BS + DS].reset_index(drop=True), a.jobs)
    b13 = pd.DataFrame(beh, columns=BS + DS, index=d13.index)
    empty = (b13[BS] == -1).all(axis=1)
    n["tls13_behav_empty_removed"] = int(empty.sum())
    b13 = b13[~empty]
    b13[ID + ["cert_size_guess_simple"]] = d13.loc[b13.index, ID + ["cert_size_guess_simple"]]
    b13.to_csv(DST / "all_behav13_new.csv")
    n["all_behav13_rows"] = len(b13)
    (OUT / "ucnet_prep.json").write_text(json.dumps(n, indent=2))
    print(json.dumps(n, indent=2))


if __name__ == "__main__":
    main()
