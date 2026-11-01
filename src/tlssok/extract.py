"""CLI entrypoint: extract features from a pcap using Zeek, NFStream, and tlsfp.

Usage:
    python -m tlssok.extract PCAP OUTDIR [--n-packets 20] [--zeek-bin zeek]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import nfstream
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from tlssok.tlsfp import parse_pcap

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Zeek helpers
# ---------------------------------------------------------------------------

def _run_zeek(pcap: Path, zeek_dir: Path, zeek_bin: str) -> None:
    """Run Zeek on *pcap*, writing JSON logs into *zeek_dir*."""
    zeek_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        zeek_bin,
        "-C",
        "-r", str(pcap.resolve()),
        "LogAscii::use_json=T",
    ]
    log.info("Running Zeek: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(zeek_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.warning("Zeek exited with code %d: %s", result.returncode, result.stderr)
    else:
        log.info("Zeek finished OK")


def _load_zeek_conn(zeek_dir: Path) -> pd.DataFrame:
    """Load Zeek conn.log (JSON) and return a cleaned DataFrame (TCP only)."""
    conn_path = zeek_dir / "conn.log"
    if not conn_path.exists():
        log.warning("conn.log not found in %s", zeek_dir)
        return pd.DataFrame()

    df = pd.read_json(conn_path, lines=True)
    if df.empty:
        return df

    # Keep TCP only
    if "proto" in df.columns:
        df = df[df["proto"] == "tcp"].copy()

    # Normalise column names
    rename = {
        "id.orig_h": "src_ip",
        "id.orig_p": "src_port",
        "id.resp_h": "dst_ip",
        "id.resp_p": "dst_port",
        "ts": "start_ts",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    return df


def _load_zeek_ssl(zeek_dir: Path) -> pd.DataFrame:
    """Load Zeek ssl.log (JSON) keyed by uid."""
    ssl_path = zeek_dir / "ssl.log"
    if not ssl_path.exists():
        return pd.DataFrame()
    return pd.read_json(ssl_path, lines=True)


# ---------------------------------------------------------------------------
# NFStream helper
# ---------------------------------------------------------------------------

def _run_nfstream(pcap: Path, n_packets: int) -> pd.DataFrame:
    """Run NFStream on *pcap* and return a DataFrame (TCP only)."""
    log.info("Running NFStream on %s", pcap)
    streamer = nfstream.NFStreamer(
        source=str(pcap),
        splt_analysis=n_packets,
        statistical_analysis=True,
        idle_timeout=120,
        active_timeout=3600,
        n_dissections=0,
    )
    df = streamer.to_pandas()
    if df.empty:
        return df
    # Keep TCP (protocol 6)
    if "protocol" in df.columns:
        df = df[df["protocol"] == 6].copy()
    return df


# ---------------------------------------------------------------------------
# Flow key normalisation
# ---------------------------------------------------------------------------

def _add_flow_key(df: pd.DataFrame, src_col: str, sport_col: str,
                   dst_col: str, dport_col: str, key_col: str = "flow_key") -> pd.DataFrame:
    """Add a direction-independent key "low_ip|low_port|high_ip|high_port" (vectorised)."""
    df = df.copy()
    s, d = df[src_col].astype(str), df[dst_col].astype(str)
    sp, dp = df[sport_col].astype(int), df[dport_col].astype(int)
    swap = (s > d) | ((s == d) & (sp > dp))
    fwd = s + "|" + sp.astype(str) + "|" + d + "|" + dp.astype(str)
    rev = d + "|" + dp.astype(str) + "|" + s + "|" + sp.astype(str)
    df[key_col] = fwd.where(~swap, rev)
    return df


# ---------------------------------------------------------------------------
# Join logic
# ---------------------------------------------------------------------------

def _merge_on_key_and_time(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_ts: str,
    right_ts: str,
    tolerance: float = 1.0,
    suffixes: tuple[str, str] = ("_l", "_r"),
) -> pd.DataFrame:
    """Merge two DataFrames on flow_key with time tolerance using merge_asof."""
    if left.empty or right.empty:
        return pd.DataFrame()

    left = left.copy().sort_values(left_ts)
    right = right.copy().sort_values(right_ts)

    merged = pd.merge_asof(
        left,
        right,
        left_on=left_ts,
        right_on=right_ts,
        by="flow_key",
        tolerance=tolerance,
        direction="nearest",
        suffixes=suffixes,
    )
    return merged


# ---------------------------------------------------------------------------
# Main extract pipeline
# ---------------------------------------------------------------------------

def extract(
    pcap: Path,
    outdir: Path,
    n_packets: int = 20,
    zeek_bin: str = "zeek",
) -> dict:
    """Run all three extractors, join results, write parquet files.

    Returns a report dict with row counts and match rates.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    zeek_dir = outdir / "zeek"

    # --- Run extractors ---
    _run_zeek(pcap, zeek_dir, zeek_bin)

    log.info("Running tlsfp parser")
    read_stats: dict = {}
    tls_df = parse_pcap(pcap, read_stats)

    nfs_df = _run_nfstream(pcap, n_packets)

    # --- Save individual parquet files ---
    _save_parquet(nfs_df, outdir / "nfstream.parquet")
    _save_parquet(tls_df, outdir / "tls.parquet")

    # --- Load Zeek logs ---
    conn_df = _load_zeek_conn(zeek_dir)
    ssl_df = _load_zeek_ssl(zeek_dir)
    if not conn_df.empty and not ssl_df.empty and "uid" in conn_df.columns and "uid" in ssl_df.columns:
        conn_df = conn_df.merge(ssl_df[["uid"] + [c for c in ssl_df.columns if c != "uid"]],
                                on="uid", how="left")

    # --- Build flow keys ---
    if not conn_df.empty:
        for c in ("src_ip", "src_port", "dst_ip", "dst_port"):
            if c not in conn_df.columns:
                log.warning("Zeek conn missing column %s", c)
        conn_df = _add_flow_key(conn_df, "src_ip", "src_port", "dst_ip", "dst_port")

    if not nfs_df.empty:
        # NFStream column names may vary; adapt common variants
        _nfs_src = _first_existing(nfs_df.columns, ["src_ip", "src_ip"])
        _nfs_sport = _first_existing(nfs_df.columns, ["src_port", "src_port"])
        _nfs_dst = _first_existing(nfs_df.columns, ["dst_ip", "dst_ip"])
        _nfs_dport = _first_existing(nfs_df.columns, ["dst_port", "dst_port"])
        if all(c is not None for c in [_nfs_src, _nfs_sport, _nfs_dst, _nfs_dport]):
            nfs_df = _add_flow_key(nfs_df, _nfs_src, _nfs_sport, _nfs_dst, _nfs_dport)
        nfs_ts = _first_existing(nfs_df.columns, ["bidirectional_first_seen_ms",
                                                   "src2dst_first_seen_ms", "start_ts"])

    if not tls_df.empty:
        tls_df = _add_flow_key(tls_df, "client_ip", "client_port", "server_ip", "server_port")

    # --- Merge: NFStream is the base flow table; attach Zeek and TLS rows ---
    # Each side gets a marker column so unmatched rows can be counted after merge_asof.
    flows_df = pd.DataFrame()
    zeek_matched = tls_matched = 0
    if not nfs_df.empty and "flow_key" in nfs_df.columns:
        nfs_ts_col = _first_existing(nfs_df.columns, [
            "bidirectional_first_seen_ms", "src2dst_first_seen_ms", "start_ts"
        ]) or "bidirectional_first_seen_ms"
        flows_df = nfs_df.copy()
        flows_df["_ts_s"] = flows_df[nfs_ts_col] / (1000.0 if "ms" in nfs_ts_col else 1.0)

        if not conn_df.empty and "flow_key" in conn_df.columns and "start_ts" in conn_df.columns:
            z = conn_df.add_prefix("zeek_").rename(columns={"zeek_flow_key": "flow_key"})
            z["_ts_s"] = conn_df["start_ts"].astype(float).values
            z["_zeek_hit"] = True
            flows_df = _merge_on_key_and_time(flows_df, z, "_ts_s", "_ts_s", tolerance=1.0)
            zeek_matched = int(flows_df["_zeek_hit"].fillna(False).astype(bool).sum())
            flows_df = flows_df.drop(columns=["_zeek_hit"])

        if not tls_df.empty and "flow_key" in tls_df.columns:
            t = tls_df.add_prefix("tls_").rename(columns={"tls_flow_key": "flow_key"})
            t["_ts_s"] = tls_df["first_ts"].astype(float).values
            t["_tls_hit"] = True
            flows_df = _merge_on_key_and_time(flows_df, t, "_ts_s", "_ts_s", tolerance=1.0)
            tls_matched = int(flows_df["_tls_hit"].fillna(False).astype(bool).sum())
            flows_df = flows_df.drop(columns=["_tls_hit"])

    _save_parquet(flows_df, outdir / "flows.parquet")

    # --- Join report ---
    def _rate(num: int, denom: int) -> float:
        return round(num / denom, 4) if denom else 0.0

    zeek_tcp_rows, nfs_tcp_rows, tls_rows = len(conn_df), len(nfs_df), len(tls_df)
    report = {
        "zeek_conn_tcp_rows": zeek_tcp_rows,
        "nfstream_tcp_rows": nfs_tcp_rows,
        "tls_rows": tls_rows,
        "nfs_with_zeek_match": zeek_matched,
        "zeek_match_rate_of_nfs": _rate(zeek_matched, nfs_tcp_rows),
        "zeek_match_rate_of_zeek": _rate(zeek_matched, zeek_tcp_rows),
        "nfs_with_tls_match": tls_matched,
        "tls_match_rate_of_tls": _rate(tls_matched, tls_rows),
        "packets_read": read_stats.get("packets_read"),
        "max_caplen": read_stats.get("max_caplen"),
        "truncated": read_stats.get("truncated"),
        "read_error": read_stats.get("read_error"),
    }

    report_path = outdir / "join_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return report


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _save_parquet(df: pd.DataFrame, path: Path) -> None:
    if df.empty:
        log.info("Empty DataFrame; skipping %s", path)
        return
    # Coerce object columns with list values to string for Parquet compat
    df_out = df.copy()
    for col in df_out.columns:
        if df_out[col].dtype == object:
            try:
                pq.write_table(pa.Table.from_pandas(df_out[[col]]), "/dev/null")
            except Exception:
                df_out[col] = df_out[col].astype(str)
    try:
        df_out.to_parquet(path, index=False)
        log.info("Saved %s (%d rows)", path, len(df_out))
    except Exception as exc:
        log.warning("Failed to save %s: %s", path, exc)
        # Fallback: stringify all object columns
        for col in df_out.select_dtypes(include="object").columns:
            df_out[col] = df_out[col].astype(str)
        df_out.to_parquet(path, index=False)


def _first_existing(columns, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tlssok.extract",
        description="Extract TLS flow features from a pcap file.",
    )
    p.add_argument("pcap", type=Path, help="Input pcap/pcapng file")
    p.add_argument("outdir", type=Path, help="Output directory")
    p.add_argument("--n-packets", type=int, default=20,
                   help="Number of packets for NFStream SPLT analysis (default: 20)")
    p.add_argument("--zeek-bin", default="zeek",
                   help="Path to Zeek binary (default: zeek)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> None:
    p = _build_parser()
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    extract(
        pcap=args.pcap,
        outdir=args.outdir,
        n_packets=args.n_packets,
        zeek_bin=args.zeek_bin,
    )


if __name__ == "__main__":
    main()
