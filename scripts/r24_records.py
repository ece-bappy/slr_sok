"""TLS record sequences in Joy's format, for the RAID 2024 baselines (C-Cert, C-Behav) on our datasets.

Usage: python scripts/r24_records.py SOURCE [SOURCE ...] [--jobs 32] [--out /data/tls-sok/r24rec]
SOURCE is an out/ dataset directory with a manifest.csv (mta, mcfp, raid_ms, raid_tranco).

The RAID 2024 code (github.com/CarlosANovo/extending12to13) consumes Joy output: for each TLS flow the
first 20 TLS records as tls_b_i (record length field, i.e. payload bytes without the 5-byte header),
tls_dir_i (0 = client->server, 1 = server->client) and tls_tp_i (content type), padded with -1, plus the
server certificate DER lengths (s_cert_lengths, ':'-joined) and ServerHello facts. This script produces
those columns from the raw pcaps, so the authors' own functions (tls_paper_funcs.py) can be applied
unchanged. Flow boundaries follow src/tlssok/tlsfp.py (5-tuple, 120 s idle timeout, client = SYN sender
or first sender), so rows join one-to-one to our flow tables on (pcap, 4-tuple, first-packet time).
TCP retransmissions are dropped by sequence number; payload after a sequence gap is not used.
Output: one parquet per pcap under OUT/SOURCE/<name>.parquet (resumable: existing files are skipped).
Malware pcaps are only parsed, never executed.
"""
import argparse
import struct
import sys
from multiprocessing import Pool
from pathlib import Path

import dpkt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from tlssok.tlsfp import _decode_ip, _ip_to_str, _open_pcap, _parse_server_hello  # noqa: E402

N_REC = 20
TIMEOUT = 120.0
HRR_RANDOM = bytes.fromhex("cf21ad74e59a6111be1d8c021e65b891c2a211167abb8c5e079e09e2c8a8339c")


class Flow:
    __slots__ = ("client", "first_ts", "last_ts", "next_seq", "buf", "recs", "hs", "sh", "certs", "dead")

    def __init__(self, client, ts):
        self.client, self.first_ts, self.last_ts = client, ts, ts
        self.next_seq = [None, None]   # per direction: 0 = client->server, 1 = server->client
        self.buf = [bytearray(), bytearray()]
        self.recs = []                  # (dir, content_type, length)
        self.hs = bytearray()           # server plaintext handshake stream
        self.sh = None
        self.certs = None
        self.dead = [False, False]

    def feed(self, d, seq, payload):
        if self.dead[d] or len(self.recs) >= N_REC:  # the handshake is always within the first 20 records
            return
        nxt = self.next_seq[d]
        if nxt is not None:
            off = (nxt - seq) & 0xFFFFFFFF
            if off < 0x80000000:  # seq <= next: retransmission, maybe with new bytes at the end
                if off >= len(payload):
                    return
                payload = payload[off:]
            else:  # gap: bytes are missing, so record boundaries after this point are unknown
                self.dead[d] = True
                return
        self.next_seq[d] = (seq + len(payload)) & 0xFFFFFFFF
        b = self.buf[d]
        b.extend(payload)
        while len(b) >= 5:
            ct, length = b[0], struct.unpack_from(">H", b, 3)[0]
            if ct not in (20, 21, 22, 23, 24):
                self.dead[d] = True
                return
            if len(b) < 5 + length:
                break
            if len(self.recs) < N_REC:
                self.recs.append((d, ct, length))
            if d == 1 and ct == 22 and self.certs is None and (self.sh is None or self.sh.selected_version < 0x0304):
                self.handshake(bytes(b[5:5 + length]))
            del b[:5 + length]

    def handshake(self, payload):
        self.hs.extend(payload)
        while len(self.hs) >= 4:
            t, n = self.hs[0], int.from_bytes(self.hs[1:4], "big")
            if len(self.hs) < 4 + n:
                return
            body = bytes(self.hs[4:4 + n])
            del self.hs[:4 + n]
            if t == 2 and self.sh is None:
                self.sh = _parse_server_hello(body)
            elif t == 11 and self.certs is None:
                lst, certs, o = body[3:3 + int.from_bytes(body[:3], "big")], [], 0
                while o + 3 <= len(lst):
                    k = int.from_bytes(lst[o:o + 3], "big")
                    certs.append(k)
                    o += 3 + k
                self.certs = certs

    def row(self, key):
        (ci, cp), (si, sp) = self.client, [k for k in key if k != self.client][0]
        r = {"c_ip": ci, "c_port": cp, "s_ip": si, "s_port": sp, "start_time": self.first_ts}
        for i in range(N_REC):
            d, ct, n = self.recs[i] if i < len(self.recs) else (-1, -1, -1)
            r[f"tls_b_{i}"], r[f"tls_dir_{i}"], r[f"tls_tp_{i}"] = n, d, ct
        sh = self.sh
        exts = {e for e, _ in (sh.extensions_raw or [])} if sh is not None and hasattr(sh, "extensions_raw") else set()
        r["s_selected_version"] = sh.selected_version if sh is not None else -1
        r["s_psk"] = 1 if 41 in exts else -1  # pre_shared_key in ServerHello: resumed session, no certificate
        r["hello_retry_req"] = int(sh is not None and sh.random == HRR_RANDOM)
        r["s_cert_lengths"] = ":".join(map(str, self.certs)) if self.certs else "-1"
        r["certificates_length"] = sum(c + 3 for c in self.certs) if self.certs else -1  # = Wireshark's field
        return r


def one(job):
    name, pcap, out = job
    if out.exists():
        return name, "skip"
    flows, done = {}, []
    try:
        reader, _ = _open_pcap(Path(pcap))
        link = reader.datalink()
        for ts, raw in reader:
            try:
                ip = _decode_ip(raw, link)
            except Exception:
                continue
            if not isinstance(ip, (dpkt.ip.IP, dpkt.ip6.IP6)) or not isinstance(ip.data, dpkt.tcp.TCP):
                continue
            tcp = ip.data
            a, b = (_ip_to_str(ip.src), tcp.sport), (_ip_to_str(ip.dst), tcp.dport)
            key = (a, b) if a <= b else (b, a)
            f = flows.get(key)
            if f is not None and ts - f.last_ts > TIMEOUT:
                done.append((key, flows.pop(key)))
                f = None
            if f is None:
                f = flows[key] = Flow(a, ts)  # client = first sender (the SYN sender when the SYN is captured)
            f.last_ts = ts
            if tcp.data:
                f.feed(0 if a == f.client else 1, tcp.seq, bytes(tcp.data))
    except Exception as exc:  # truncated capture: keep what was read, as tlsfp does
        err = f"{type(exc).__name__}"
    else:
        err = ""
    rows = [f.row(k) for k, f in done + list(flows.items())
            if any(ct == 22 for _, ct, _ in f.recs)]
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out)
    return name, f"{len(rows)} flows {err}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--out", default="/data/tls-sok/r24rec")
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--limit", type=int, default=None, help="first N pcaps per source (smoke tests)")
    a = ap.parse_args()
    jobs = []
    for s in a.sources:
        man = pd.read_csv(f"/data/tls-sok/out/{s}/manifest.csv")
        man = man[man["tls_flows"].fillna(0) > 0]
        if a.limit:
            man = man.head(a.limit)
        jobs += [(f"{s}/{n}", p, Path(a.out) / s / f"{n}.parquet") for n, p in zip(man["name"], man["pcap"])]
    jobs.sort(key=lambda j: -Path(j[1]).stat().st_size)  # largest first, for better load balance
    with Pool(a.jobs) as pool:
        for i, (name, msg) in enumerate(pool.imap_unordered(one, jobs), 1):
            print(f"{i}/{len(jobs)} {name}: {msg}", flush=True)


if __name__ == "__main__":
    main()
