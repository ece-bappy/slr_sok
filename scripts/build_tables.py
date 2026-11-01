"""Build one training table per benchmark dataset from the per-pcap extraction outputs (runs on A2).

Usage: python scripts/build_tables.py {raid,hikari} [--out /data/tls-sok/tables] [--workers 12] [--limit N]

raid:   raid_ms flows = C2 (1), raid_tranco flows = benign (0); TLS flows only (ClientHello seen).
hikari: TCP flows to server port 443 from hikari_attack + hikari_benign, labelled by joining the
        4-tuple with HIKARI's ALLFLOWMETER_HIKARI2021/2022 tables (unmatched or contradictory
        flows are dropped and counted). Attack pcaps also hold background traffic, so the pcap
        name is never used as the label.

Feature columns are prefixed by group: g1_ flow statistics, g2_ first-20-packet sequences,
g3_ handshake, g4_ certificate, g5_ fingerprints (categorical strings). IPs, ports, SNI, pcap and
times are kept only as keys (k_*) for grouping, splitting and reporting, never as features.
Writes OUT/<dataset>.parquet and OUT/<dataset>.card.json.
"""
import argparse
import ast
import glob
import json
import math
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

OUT_ROOT = "/data/tls-sok/out"
LABELS = "/data/tls-sok/raw/hikari/labels"
N_SEQ = 20

DIRS = ("bidirectional", "src2dst", "dst2src")
G1 = [f"{d}_{s}" for d in DIRS for s in (
    "duration_ms", "packets", "bytes", "min_ps", "mean_ps", "stddev_ps", "max_ps",
    "min_piat_ms", "mean_piat_ms", "stddev_piat_ms", "max_piat_ms",
    "syn_packets", "cwr_packets", "ece_packets", "urg_packets", "ack_packets", "psh_packets",
    "rst_packets", "fin_packets")]
EXT_TYPES = [0, 5, 10, 11, 13, 16, 17, 18, 21, 22, 23, 27, 28, 34, 35, 41, 42, 43, 44, 45, 49, 50,
             51, 57, 17513, 17613, 65037, 65281]  # common IANA extension types, ECH = 65037
TLS_VER = {769: "1.0", 770: "1.1", 771: "1.2", 772: "1.3"}


def as_list(v) -> list:
    """List columns may come back as lists, arrays, JSON text or Python-repr text."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return []
    if isinstance(v, (list, tuple, np.ndarray)):
        return list(v)
    if isinstance(v, str):
        if v in ("", "nan", "None"):
            return []
        try:
            return json.loads(v)
        except ValueError:
            return list(ast.literal_eval(v))
    return []


def grease(x) -> bool:
    return isinstance(x, (int, np.integer)) and (x & 0x0F0F) == 0x0A0A


def entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def num(v, default=np.nan):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_x509(zeek_dir: Path) -> dict:
    """fingerprint -> certificate features, from Zeek's x509.log (TLS 1.2 only in practice)."""
    p = zeek_dir / "x509.log"
    if not p.exists():
        return {}
    out = {}
    for line in open(p, encoding="utf-8"):
        r = json.loads(line)
        fp = r.get("fingerprint")
        if not fp:
            continue
        nb, na = num(r.get("certificate.not_valid_before")), num(r.get("certificate.not_valid_after"))
        out[fp] = {
            "g4_validity_days": (na - nb) / 86400 if nb == nb and na == na else np.nan,
            "g4_self_signed": float(r.get("certificate.subject") == r.get("certificate.issuer")),
            "g4_san_dns_count": float(len(r.get("san.dns") or [])),
            "g4_key_length": num(r.get("certificate.key_length")),
            "g4_key_alg": str(r.get("certificate.key_alg") or ""),
            "g4_sig_alg": str(r.get("certificate.sig_alg") or ""),
        }
    return out


def features(f: pd.DataFrame, x509: dict) -> pd.DataFrame:
    out = {}  # column name -> Series; built into one frame at the end (avoids fragmentation)
    for c in G1:
        out["g1_" + c] = pd.to_numeric(f[c], errors="coerce")
    for col, short in (("splt_direction", "dir"), ("splt_ps", "ps"), ("splt_piat_ms", "piat")):
        seqs = f[col].map(as_list)
        for i in range(N_SEQ):
            out[f"g2_{short}_{i:02d}"] = seqs.map(lambda s: s[i] if i < len(s) else -1).astype(float)
    if "tls_ja3" not in f.columns:  # no TLS records parsed in this pcap
        return pd.DataFrame(out, index=f.index)
    has_ch = f["tls_ja3"].notna()
    sv = f["tls_ch_supported_versions"].map(lambda s: [x for x in as_list(s) if not grease(x)])
    out["g3_ch_legacy_version"] = pd.to_numeric(f["tls_ch_legacy_version"], errors="coerce")
    out["g3_ch_max_supported_version"] = sv.map(lambda s: max(s, default=0)).where(has_ch)
    for col, short in (("tls_ch_cipher_suites", "ciphers"), ("tls_ch_extension_types", "extensions"),
                       ("tls_ch_supported_groups", "groups"), ("tls_ch_signature_algorithms", "sigalgs"),
                       ("tls_ch_ec_point_formats", "ec_formats")):
        out[f"g3_n_{short}"] = f[col].map(lambda s: sum(not grease(x) for x in as_list(s))).where(has_ch)
    exts = f["tls_ch_extension_types"].map(lambda s: set(as_list(s)))
    for t in EXT_TYPES:
        out[f"g3_ext_{t}"] = exts.map(lambda s, t=t: float(t in s)).where(has_ch)
    alpn = f["tls_ch_alpn"].map(as_list)
    out["g3_has_alpn"] = alpn.map(lambda s: float(bool(s))).where(has_ch)
    out["g3_alpn_first"] = alpn.map(lambda s: str(s[0]) if s else "").where(has_ch)
    sni = f["tls_ch_sni"].fillna("").astype(str)
    out["g3_sni_present"] = (sni != "").astype(float).where(has_ch)
    out["g3_sni_len"] = sni.str.len().astype(float).where(has_ch)
    out["g3_sni_entropy"] = sni.map(entropy).where(has_ch)
    out["g3_has_ech"] = f["tls_ch_has_ech"].map(lambda v: float(bool(v)) if v == v else np.nan)
    out["g3_has_server_hello"] = f["tls_sh_selected_version"].notna().astype(float).where(has_ch)
    out["g3_sh_selected_version"] = pd.to_numeric(f["tls_sh_selected_version"], errors="coerce")
    out["g3_sh_selected_cipher"] = pd.to_numeric(f["tls_sh_selected_cipher"], errors="coerce")
    out["g3_n_sh_extensions"] = f["tls_sh_extension_types"].map(lambda s: float(len(as_list(s)))).where(
        f["tls_sh_selected_version"].notna())
    out["g4_cert_count"] = pd.to_numeric(f["tls_cert_count"], errors="coerce")
    out["g4_leaf_der_len"] = pd.to_numeric(f["tls_cert_leaf_der_len"], errors="coerce")
    leaf = f.get("zeek_cert_chain_fps", pd.Series(index=f.index, dtype=object)).map(
        lambda s: (as_list(s) or [None])[0])
    cert = pd.DataFrame([x509.get(fp, {}) for fp in leaf], index=f.index)
    for c in ("g4_validity_days", "g4_self_signed", "g4_san_dns_count", "g4_key_length", "g4_key_alg", "g4_sig_alg"):
        out[c] = cert[c] if c in cert else pd.Series("" if c.endswith("alg") else np.nan, index=f.index)
    for c in ("ja3", "ja4", "ja3s", "ja4s"):
        out["g5_" + c] = f["tls_" + c].fillna("").astype(str)
    return pd.DataFrame(out, index=f.index)


def one_pcap(task: tuple) -> pd.DataFrame | None:
    dataset, source, pcap_dir = task
    p = Path(pcap_dir)
    f = pd.read_parquet(p / "flows.parquet")
    f = f[f["protocol"] == 6] if "protocol" in f else f
    if dataset == "raid":
        f = f[f["tls_ja3"].notna()] if "tls_ja3" in f else f.iloc[0:0]
    else:
        f = f[f["dst_port"] == 443]
    if f.empty:
        return None
    x = features(f.reset_index(drop=True), load_x509(p / "zeek"))
    f = f.reset_index(drop=True)
    keys = pd.DataFrame({
        "k_source": source,
        "k_pcap": os.path.relpath(p, f"{OUT_ROOT}/{source}"),
        "k_client_ip": f["src_ip"].astype(str), "k_client_port": f["src_port"].astype(int),
        "k_server_ip": f["dst_ip"].astype(str), "k_server_port": f["dst_port"].astype(int),
        "k_first_seen_ms": f["bidirectional_first_seen_ms"].astype("int64"),
        "k_sni": f["tls_ch_sni"].fillna("").astype(str) if "tls_ch_sni" in f else "",
        "k_tls_version": pd.to_numeric(f["tls_sh_selected_version"], errors="coerce").map(TLS_VER).fillna("none")
                         if "tls_sh_selected_version" in f else "none",
    })
    if "tls_client_ip" in f:  # use the TLS parser's client/server roles where it saw a handshake
        m = f["tls_client_ip"].notna()
        keys.loc[m, "k_client_ip"] = f.loc[m, "tls_client_ip"].astype(str)
        keys.loc[m, "k_server_ip"] = f.loc[m, "tls_server_ip"].astype(str)
        keys.loc[m, "k_client_port"] = f.loc[m, "tls_client_port"].astype(int)
        keys.loc[m, "k_server_port"] = f.loc[m, "tls_server_port"].astype(int)
    return pd.concat([keys, x], axis=1)


def hikari_labels() -> dict:
    """(year, src, sport, dst, dport) -> (label, category); contradictory tuples map to None."""
    lab = {}
    for year, fn, cat in (("2021", "ALLFLOWMETER_HIKARI2021.csv", "traffic_category"),
                          ("2022", "ALLFLOWMETER_HIKARI2022.csv", "attack_category")):
        d = pd.read_csv(f"{LABELS}/{fn}", usecols=["originh", "originp", "responh", "responp", cat, "Label"])
        for o, op, r, rp, c, l in d.itertuples(index=False):
            k = (year, str(o), int(op), str(r), int(rp))
            v = (int(l), str(c))
            if k in lab and lab[k] is not None and lab[k][0] != v[0]:
                lab[k] = None
            elif k not in lab:
                lab[k] = v
    return lab


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=["raid", "hikari"])
    ap.add_argument("--out", default="/data/tls-sok/tables")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="pcaps per source, for smoke tests")
    a = ap.parse_args()

    sources = {"raid": {"raid_ms": 1, "raid_tranco": 0}, "hikari": {"hikari_attack": None, "hikari_benign": None}}[a.dataset]
    tasks = []
    for src in sources:
        dirs = sorted(str(Path(m).parent) for m in glob.glob(f"{OUT_ROOT}/{src}/**/manifest.json", recursive=True))
        tasks += [(a.dataset, src, d) for d in (dirs[: a.limit] if a.limit else dirs)]
    with ProcessPoolExecutor(a.workers) as ex:
        parts = [p for p in ex.map(one_pcap, tasks, chunksize=4) if p is not None]
    df = pd.concat(parts, ignore_index=True).copy()
    card = {"dataset": a.dataset, "pcaps": len(tasks), "rows_extracted": len(df)}

    if a.dataset == "raid":
        df["label"] = df["k_source"].map(sources)
        df["k_category"] = df["k_source"].map({"raid_ms": "Metasploit C2", "raid_tranco": "benign"})
        df["k_year"] = pd.to_datetime(df["k_first_seen_ms"], unit="ms").dt.year.astype(str)
    else:
        lab = hikari_labels()
        df["k_year"] = df["k_pcap"].str.extract(r"(20\d\d)-\d\d-\d\d", expand=False).fillna("2021")
        hits = []
        for y, c, cp, s, sp in df[["k_year", "k_client_ip", "k_client_port", "k_server_ip", "k_server_port"]].itertuples(index=False):
            hits.append(lab.get((y, c, cp, s, sp), lab.get((y, s, sp, c, cp), "missing")))
        miss = sum(h == "missing" for h in hits)
        conflict = sum(h is None for h in hits)
        card.update(hikari_label_missing=miss, hikari_label_conflict=conflict)
        ok = [isinstance(h, tuple) for h in hits]
        df = df[ok].reset_index(drop=True)
        hits = [h for h in hits if isinstance(h, tuple)]
        df["label"] = [h[0] for h in hits]
        df["k_category"] = [h[1] for h in hits]
        df = df.drop(columns=[c for c in df.columns if c.startswith(("g3_", "g4_", "g5_"))])  # G1/G2 only

    before = len(df)
    df = df.drop_duplicates(["k_client_ip", "k_client_port", "k_server_ip", "k_server_port", "k_first_seen_ms"])
    card["exact_flow_duplicates_removed"] = before - len(df)
    feats = [c for c in df.columns if c[:3] in ("g1_", "g2_", "g3_", "g4_", "g5_")]
    vec_dup = df.duplicated(feats + ["label"])
    conflict = df[feats].duplicated(keep=False) & ~df.duplicated(feats + ["label"], keep=False)
    card.update({
        "rows": len(df), "label_counts": df["label"].value_counts().to_dict(),
        "category_counts": df["k_category"].value_counts().to_dict(),
        "tls_version_counts": {f"{l}:{v}": n for (l, v), n in df.groupby(["label", "k_tls_version"]).size().items()},
        "year_counts": {f"{l}:{y}": n for (l, y), n in df.groupby(["label", "k_year"]).size().items()},
        "features_per_group": {g: sum(c.startswith(g) for c in feats) for g in ("g1_", "g2_", "g3_", "g4_", "g5_")},
        "same_feature_vector_duplicates_within_class": int(vec_dup.sum()),
        "feature_vectors_in_both_classes_rows": int(conflict.sum()),
        "clients_per_label": df.groupby("label")["k_client_ip"].nunique().to_dict(),
        "servers_per_label": df.groupby("label")["k_server_ip"].nunique().to_dict(),
        "dropped_from_features": "IPs, ports, MACs/OUI, VLAN/tunnel ids, absolute timestamps, SNI string, pcap name, NFStream ids",
    })
    Path(a.out).mkdir(parents=True, exist_ok=True)
    tag = a.dataset + (f"_limit{a.limit}" if a.limit else "")
    df.to_parquet(f"{a.out}/{tag}.parquet", index=False)
    Path(f"{a.out}/{tag}.card.json").write_text(json.dumps(card, indent=2, default=str))
    print(json.dumps(card, indent=2, default=str))


if __name__ == "__main__":
    main()
