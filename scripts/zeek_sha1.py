"""Leaf-certificate SHA-1 per TLS connection, for the SSLBL label-circularity audit (E5b) only.

Usage: python scripts/zeek_sha1.py {mta,mcfp} [--workers 12]

The main extraction keeps Zeek's default SHA-256 certificate fingerprints, but SSLBL lists SHA-1, so this
re-runs Zeek with X509::hash_function = sha1_hash on every pcap that has an extraction manifest and
writes OUT/sha1/<dataset>/<pcap name>.csv (client ip/port, server ip/port, leaf SHA-1). Resumable: pcaps
with an output file are skipped. These SHA-1s are never used as features or as the main labels.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

OUT = Path("/data/tls-sok/out")


def one(task: tuple) -> str:
    pcap, dest = task
    with tempfile.TemporaryDirectory(dir="/data/tls-sok/tmp") as t:
        subprocess.run(["zeek", "-C", "-r", pcap, "LogAscii::use_json=T",
                        "-e", "redef X509::hash_function = sha1_hash;"], cwd=t, capture_output=True)
        rows = []
        ssl = Path(t) / "ssl.log"
        if ssl.exists():
            for line in open(ssl, encoding="utf-8"):
                r = json.loads(line)
                fps = r.get("cert_chain_fps") or []
                if fps:
                    rows.append((r["id.orig_h"], r["id.orig_p"], r["id.resp_h"], r["id.resp_p"], fps[0]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".part")
    pd.DataFrame(rows, columns=["client_ip", "client_port", "server_ip", "server_port", "leaf_sha1"]).to_csv(
        part, index=False)
    part.rename(dest)
    return f"{dest.name}: {len(rows)}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=["mta", "mcfp"])
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    (Path("/data/tls-sok/tmp")).mkdir(exist_ok=True)
    tasks = []
    for m in sorted((OUT / a.dataset).rglob("manifest.json")):
        info = json.loads(m.read_text())
        dest = OUT / "sha1" / a.dataset / (info["name"] + ".csv")
        if not dest.exists():
            tasks.append((info["pcap"], dest))
    print(f"{a.dataset}: {len(tasks)} pcaps to do", flush=True)
    with ProcessPoolExecutor(a.workers) as ex:
        for i, msg in enumerate(ex.map(one, tasks), 1):
            if i % 50 == 0 or i == len(tasks):
                print(i, msg, flush=True)
    print("SHA1_FINISHED", a.dataset, flush=True)


if __name__ == "__main__":
    sys.exit(main())
