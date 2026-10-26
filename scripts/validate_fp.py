"""Cross-check tlssok JA3/JA3S/JA4 against tshark's built-in implementation.

Usage: python scripts/validate_fp.py PCAP
"""
import subprocess
import sys

from tlssok.tlsfp import parse_pcap

FIELDS = ["ip.src", "ipv6.src", "tcp.srcport", "ip.dst", "ipv6.dst", "tcp.dstport",
          "tls.handshake.ja3", "tls.handshake.ja4"]


def tshark_clienthellos(pcap: str) -> dict[tuple, tuple[str, str]]:
    cmd = ["tshark", "-r", pcap, "-Y", "tls.handshake.type == 1", "-T", "fields",
           "-E", "separator=\t", "-E", "occurrence=f"]
    for f in FIELDS:
        cmd += ["-e", f]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    ref = {}
    for line in out.splitlines():
        s4, s6, sp, d4, d6, dp, ja3, ja4 = (line.split("\t") + [""] * 8)[:8]
        key = (s4 or s6, int(sp), d4 or d6, int(dp))
        ref.setdefault(key, (ja3, ja4))
    return ref


def main(pcap: str) -> None:
    ref = tshark_clienthellos(pcap)
    df = parse_pcap(pcap)
    cols = {c.lower(): c for c in df.columns}
    need = ["client_ip", "client_port", "server_ip", "server_port", "ja3", "ja4"]
    missing = [c for c in need if c not in cols]
    if missing:
        sys.exit(f"parse_pcap output lacks columns {missing}; has {list(df.columns)}")
    n = ja3_ok = ja4_ok = 0
    bad = []
    for r in df.itertuples(index=False):
        row = r._asdict()
        key = (str(row[cols["client_ip"]]), int(row[cols["client_port"]]),
               str(row[cols["server_ip"]]), int(row[cols["server_port"]]))
        if key not in ref:
            continue
        n += 1
        rja3, rja4 = ref[key]
        ja3_ok += row[cols["ja3"]] == rja3
        ja4_ok += row[cols["ja4"]] == rja4
        if row[cols["ja4"]] != rja4 and len(bad) < 5:
            bad.append((key, row[cols["ja4"]], rja4))
    print(f"tshark ClientHellos: {len(ref)}  tlssok flows: {len(df)}  matched by 5-tuple: {n}")
    if n:
        print(f"JA3 agreement: {ja3_ok}/{n}  JA4 agreement: {ja4_ok}/{n}")
    for b in bad:
        print("JA4 mismatch:", b)


if __name__ == "__main__":
    main(sys.argv[1])
