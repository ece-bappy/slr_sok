"""Passive TLS handshake parser using dpkt.

Reads pcap/pcapng files, reconstructs TCP flows, and parses TLS ClientHello,
ServerHello, and Certificate messages to produce per-flow fingerprints.
"""

from __future__ import annotations

import hashlib
import ipaddress
import io
import json
import logging
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Iterator, NamedTuple

import dpkt
import dpkt.pcap
import dpkt.pcapng
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GREASE values (RFC 8701)
# ---------------------------------------------------------------------------
_GREASE = frozenset(
    0x0A0A + 0x1010 * i for i in range(16)
)
# More explicit: 0x0a0a, 0x1a1a, 0x2a2a, ..., 0xfafa
_GREASE = frozenset(v for v in range(0x0000, 0x10000) if (v & 0x0F0F) == 0x0A0A and (v >> 8) == (v & 0xFF))


def _is_grease(val: int) -> bool:
    return val in _GREASE


# ---------------------------------------------------------------------------
# Feature visibility metadata
# ---------------------------------------------------------------------------
FEATURE_VISIBILITY: dict[str, dict] = {
    # --- ClientHello ---
    "ch_legacy_version":          {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    # ClientHello is always cleartext; under ECH only the outer hello is seen.
    "ch_supported_versions":      {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "ch_cipher_suites":           {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True, "ech_outer_only": True},
    "ch_extension_types":         {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True, "ech_outer_only": True},
    "ch_supported_groups":        {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "ch_ec_point_formats":        {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "ch_signature_algorithms":    {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "ch_alpn":                    {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True, "ech_outer_only": True},
    "ch_sni":                     {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True, "ech_outer_only": True},
    "ch_has_ech":                 {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    # --- Fingerprints ---
    "ja3":                        {"group": "G5", "tls12": True,  "tls13": True,  "tls13_ech": True, "ech_outer_only": True},
    "ja3s":                       {"group": "G5", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "ja4":                        {"group": "G5", "tls12": True,  "tls13": True,  "tls13_ech": True, "ech_outer_only": True},
    "ja4s":                       {"group": "G5", "tls12": True,  "tls13": True,  "tls13_ech": True},
    # --- ServerHello ---
    "sh_selected_version":        {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "sh_selected_cipher":         {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "sh_extension_types":         {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    # --- Certificate (TLS 1.2 only) ---
    "cert_count":                 {"group": "G4", "tls12": True,  "tls13": False, "tls13_ech": False},
    "cert_leaf_der_len":          {"group": "G4", "tls12": True,  "tls13": False, "tls13_ech": False},
    # --- Packet indices ---
    "pkt_idx_client_hello":       {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "pkt_idx_server_hello":       {"group": "G3", "tls12": True,  "tls13": True,  "tls13_ech": True},
    "pkt_idx_certificate":        {"group": "G4", "tls12": True,  "tls13": False, "tls13_ech": False},
}


# ---------------------------------------------------------------------------
# Dataclasses for parsed handshake messages
# ---------------------------------------------------------------------------

@dataclass
class ClientHello:
    legacy_version: int = 0x0303
    random: bytes = b""
    session_id: bytes = b""
    cipher_suites: list[int] = field(default_factory=list)
    compression_methods: list[int] = field(default_factory=list)
    # Extensions in wire order (type, data-bytes)
    extensions_raw: list[tuple[int, bytes]] = field(default_factory=list)
    # Parsed extension fields
    supported_versions: list[int] = field(default_factory=list)
    supported_groups: list[int] = field(default_factory=list)
    ec_point_formats: list[int] = field(default_factory=list)
    signature_algorithms: list[int] = field(default_factory=list)
    alpn: list[str] = field(default_factory=list)
    sni: str = ""
    has_ech: bool = False

    @property
    def extension_types(self) -> list[int]:
        return [t for t, _ in self.extensions_raw]


@dataclass
class ServerHello:
    legacy_version: int = 0x0303
    random: bytes = b""
    session_id: bytes = b""
    cipher_suite: int = 0
    compression_method: int = 0
    extensions_raw: list[tuple[int, bytes]] = field(default_factory=list)
    # Parsed
    selected_version: int = 0  # from supported_versions ext if present
    supported_versions: list[int] = field(default_factory=list)

    @property
    def extension_types(self) -> list[int]:
        return [t for t, _ in self.extensions_raw]


@dataclass
class CertificateInfo:
    cert_count: int = 0
    leaf_der_len: int = 0


# ---------------------------------------------------------------------------
# TLS constants
# ---------------------------------------------------------------------------
_TLS_CONTENT_HANDSHAKE = 22
_HS_CLIENT_HELLO = 1
_HS_SERVER_HELLO = 2
_HS_CERTIFICATE = 11

_EXT_SNI = 0x0000
_EXT_SUPPORTED_GROUPS = 0x000A
_EXT_EC_POINT_FORMATS = 0x000B
_EXT_SIG_ALGS = 0x000D
_EXT_ALPN = 0x0010
_EXT_SUPPORTED_VERSIONS = 0x002B
_EXT_ECH = 0xFE0D

_TLS_VERSION_MAP = {
    0x0304: "13",
    0x0303: "12",
    0x0302: "11",
    0x0301: "10",
    0x0300: "s3",
}


# ---------------------------------------------------------------------------
# Low-level TLS parsing helpers
# ---------------------------------------------------------------------------

def _read_uint8(buf: bytes, off: int) -> tuple[int, int]:
    return buf[off], off + 1


def _read_uint16(buf: bytes, off: int) -> tuple[int, int]:
    return struct.unpack_from(">H", buf, off)[0], off + 2


def _read_uint24(buf: bytes, off: int) -> tuple[int, int]:
    hi, lo = struct.unpack_from(">BH", buf, off)
    return (hi << 16) | lo, off + 3


def _read_bytes(buf: bytes, off: int, n: int) -> tuple[bytes, int]:
    return buf[off:off + n], off + n


def _read_len8_bytes(buf: bytes, off: int) -> tuple[bytes, int]:
    n, off = _read_uint8(buf, off)
    return _read_bytes(buf, off, n)


def _read_len16_bytes(buf: bytes, off: int) -> tuple[bytes, int]:
    n, off = _read_uint16(buf, off)
    return _read_bytes(buf, off, n)


def _parse_extensions(ext_data: bytes) -> list[tuple[int, bytes]]:
    """Parse TLS extension list; return list of (type, data) tuples."""
    exts: list[tuple[int, bytes]] = []
    off = 0
    while off + 4 <= len(ext_data):
        try:
            ext_type, off = _read_uint16(ext_data, off)
            ext_body, off = _read_len16_bytes(ext_data, off)
            exts.append((ext_type, ext_body))
        except (struct.error, IndexError):
            break
    return exts


def _parse_client_hello(data: bytes) -> ClientHello | None:
    """Parse a ClientHello handshake body (after 4-byte HS header)."""
    try:
        off = 0
        legacy_version, off = _read_uint16(data, off)
        random_bytes, off = _read_bytes(data, off, 32)
        session_id, off = _read_len8_bytes(data, off)
        # Cipher suites
        cs_data, off = _read_len16_bytes(data, off)
        ciphers = [struct.unpack_from(">H", cs_data, i)[0] for i in range(0, len(cs_data), 2)]
        # Compression methods
        comp_data, off = _read_len8_bytes(data, off)
        comp_methods = list(comp_data)

        ch = ClientHello(
            legacy_version=legacy_version,
            random=random_bytes,
            session_id=session_id,
            cipher_suites=ciphers,
            compression_methods=comp_methods,
        )

        if off + 2 > len(data):
            return ch  # No extensions

        ext_list_data, off = _read_len16_bytes(data, off)
        ch.extensions_raw = _parse_extensions(ext_list_data)

        # Parse well-known extensions
        for ext_type, ext_body in ch.extensions_raw:
            try:
                if ext_type == _EXT_SNI:
                    _parse_sni(ext_body, ch)
                elif ext_type == _EXT_SUPPORTED_GROUPS:
                    groups_data, _ = _read_len16_bytes(ext_body, 0)
                    ch.supported_groups = [struct.unpack_from(">H", groups_data, i)[0]
                                           for i in range(0, len(groups_data), 2)]
                elif ext_type == _EXT_EC_POINT_FORMATS:
                    pf_data, _ = _read_len8_bytes(ext_body, 0)
                    ch.ec_point_formats = list(pf_data)
                elif ext_type == _EXT_SIG_ALGS:
                    sa_data, _ = _read_len16_bytes(ext_body, 0)
                    ch.signature_algorithms = [struct.unpack_from(">H", sa_data, i)[0]
                                               for i in range(0, len(sa_data), 2)]
                elif ext_type == _EXT_ALPN:
                    _parse_alpn(ext_body, ch)
                elif ext_type == _EXT_SUPPORTED_VERSIONS:
                    sv_data, _ = _read_len8_bytes(ext_body, 0)
                    ch.supported_versions = [struct.unpack_from(">H", sv_data, i)[0]
                                             for i in range(0, len(sv_data), 2)]
                elif ext_type == _EXT_ECH:
                    ch.has_ech = True
            except (struct.error, IndexError):
                pass  # Malformed extension – skip

        return ch
    except (struct.error, IndexError, ValueError) as exc:
        log.debug("ClientHello parse error: %s", exc)
        return None


def _parse_sni(data: bytes, ch: ClientHello) -> None:
    """Parse server_name extension into ch.sni."""
    if len(data) < 2:
        return
    list_data, _ = _read_len16_bytes(data, 0)
    off2 = 0
    while off2 + 3 <= len(list_data):
        name_type, off2 = _read_uint8(list_data, off2)
        name_bytes, off2 = _read_len16_bytes(list_data, off2)
        if name_type == 0:  # host_name
            ch.sni = name_bytes.decode("ascii", errors="replace")
            return


def _parse_alpn(data: bytes, ch: ClientHello) -> None:
    """Parse application_layer_protocol_negotiation extension."""
    if len(data) < 2:
        return
    proto_list_data, _ = _read_len16_bytes(data, 0)
    off2 = 0
    while off2 < len(proto_list_data):
        proto, off2 = _read_len8_bytes(proto_list_data, off2)
        if proto:
            ch.alpn.append(proto.decode("ascii", errors="replace"))


def _parse_server_hello(data: bytes) -> ServerHello | None:
    """Parse a ServerHello handshake body (after 4-byte HS header)."""
    try:
        off = 0
        legacy_version, off = _read_uint16(data, off)
        random_bytes, off = _read_bytes(data, off, 32)
        session_id, off = _read_len8_bytes(data, off)
        cipher_suite, off = _read_uint16(data, off)
        compression_method, off = _read_uint8(data, off)

        sh = ServerHello(
            legacy_version=legacy_version,
            random=random_bytes,
            session_id=session_id,
            cipher_suite=cipher_suite,
            compression_method=compression_method,
            selected_version=legacy_version,
        )

        if off + 2 > len(data):
            return sh

        ext_list_data, _ = _read_len16_bytes(data, off)
        sh.extensions_raw = _parse_extensions(ext_list_data)

        for ext_type, ext_body in sh.extensions_raw:
            try:
                if ext_type == _EXT_SUPPORTED_VERSIONS:
                    version, _ = _read_uint16(ext_body, 0)
                    sh.supported_versions = [version]
                    sh.selected_version = version
            except (struct.error, IndexError):
                pass

        return sh
    except (struct.error, IndexError, ValueError) as exc:
        log.debug("ServerHello parse error: %s", exc)
        return None


def _parse_certificate(data: bytes) -> CertificateInfo | None:
    """Parse a Certificate handshake body (TLS 1.2 format)."""
    try:
        cert_list_data, _ = _read_len24_bytes(data, 0)
        certs: list[int] = []
        off2 = 0
        while off2 + 3 <= len(cert_list_data):
            cert_len, off2 = _read_uint24(cert_list_data, off2)
            if off2 + cert_len > len(cert_list_data):
                break
            certs.append(cert_len)
            off2 += cert_len
        leaf_len = certs[0] if certs else 0
        return CertificateInfo(cert_count=len(certs), leaf_der_len=leaf_len)
    except (struct.error, IndexError, ValueError) as exc:
        log.debug("Certificate parse error: %s", exc)
        return None


def _read_uint24_bytes(data: bytes, off: int) -> tuple[int, int]:
    n, off = _read_uint24(data, off)
    return n, off


def _read_len24_bytes(data: bytes, off: int) -> tuple[bytes, int]:
    n, off = _read_uint24(data, off)
    return data[off:off + n], off + n


# ---------------------------------------------------------------------------
# TLS record stream reassembly
# ---------------------------------------------------------------------------

class _TlsRecordReader:
    """Accumulates TCP payload bytes and yields complete TLS records."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> Iterator[tuple[int, int, bytes]]:
        """Feed TCP payload; yield (content_type, version, payload) tuples."""
        self._buf.extend(data)
        while len(self._buf) >= 5:
            ctype = self._buf[0]
            version = struct.unpack_from(">H", self._buf, 1)[0]
            length = struct.unpack_from(">H", self._buf, 3)[0]
            if len(self._buf) < 5 + length:
                break
            payload = bytes(self._buf[5:5 + length])
            del self._buf[:5 + length]
            yield ctype, version, payload


class _HandshakeReader:
    """Accumulates TLS handshake payloads and yields complete messages."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, payload: bytes) -> Iterator[tuple[int, bytes]]:
        """Feed TLS record payload; yield (msg_type, body) for complete HS messages."""
        self._buf.extend(payload)
        while len(self._buf) >= 4:
            msg_type = self._buf[0]
            length = struct.unpack_from(">I", b"\x00" + bytes(self._buf[1:4]))[0]
            if len(self._buf) < 4 + length:
                break
            body = bytes(self._buf[4:4 + length])
            del self._buf[:4 + length]
            yield msg_type, body


# ---------------------------------------------------------------------------
# Flow tracking
# ---------------------------------------------------------------------------

class _FlowKey(NamedTuple):
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    proto: int  # always 6 (TCP)


def _canonical_key(ip_src: str, port_src: int, ip_dst: str, port_dst: int) -> tuple[_FlowKey, bool]:
    """Return canonical 5-tuple and True if (src,sport) is the 'lower' side."""
    a = (ip_src, port_src)
    b = (ip_dst, port_dst)
    if a <= b:
        return _FlowKey(ip_src, port_src, ip_dst, port_dst, 6), True
    else:
        return _FlowKey(ip_dst, port_dst, ip_src, port_src, 6), False


@dataclass
class _Flow:
    key: _FlowKey
    client_ip: str
    client_port: int
    server_ip: str
    server_port: int
    first_ts: float
    last_ts: float
    pkt_count: int = 0  # both directions combined

    # Per-direction TLS readers
    client_tls: _TlsRecordReader = field(default_factory=_TlsRecordReader)
    server_tls: _TlsRecordReader = field(default_factory=_TlsRecordReader)
    client_hs: _HandshakeReader = field(default_factory=_HandshakeReader)
    server_hs: _HandshakeReader = field(default_factory=_HandshakeReader)

    # Results
    client_hello: ClientHello | None = None
    server_hello: ServerHello | None = None
    certificate: CertificateInfo | None = None

    pkt_idx_ch: int | None = None
    pkt_idx_sh: int | None = None
    pkt_idx_cert: int | None = None

    done_parsing: bool = False  # stop after all three found or 20 pkts
    pkt_parse_count: int = 0  # packets fed to parser

    # Track which side is 'client' (sent SYN or first packet)
    client_is_lower: bool = True  # canonical key lower side = client

    _MAX_PARSE_PKTS: int = 20

    def feed_packet(self, is_from_client: bool, tcp_payload: bytes, pkt_global_idx: int) -> None:
        if self.done_parsing:
            return
        self.pkt_parse_count += 1
        if self.pkt_parse_count > self._MAX_PARSE_PKTS:
            self.done_parsing = True
            return

        tls_reader = self.client_tls if is_from_client else self.server_tls
        hs_reader = self.client_hs if is_from_client else self.server_hs

        for ctype, _ver, payload in tls_reader.feed(tcp_payload):
            if ctype != _TLS_CONTENT_HANDSHAKE:
                continue
            for msg_type, body in hs_reader.feed(payload):
                if msg_type == _HS_CLIENT_HELLO and self.client_hello is None:
                    ch = _parse_client_hello(body)
                    if ch is not None:
                        self.client_hello = ch
                        self.pkt_idx_ch = pkt_global_idx
                elif msg_type == _HS_SERVER_HELLO and self.server_hello is None:
                    sh = _parse_server_hello(body)
                    if sh is not None:
                        self.server_hello = sh
                        self.pkt_idx_sh = pkt_global_idx
                elif msg_type == _HS_CERTIFICATE and self.certificate is None:
                    # Only capture for TLS <= 1.2
                    selected_ver = (
                        self.server_hello.selected_version
                        if self.server_hello else 0
                    )
                    if selected_ver < 0x0304:
                        cert = _parse_certificate(body)
                        if cert is not None:
                            self.certificate = cert
                            self.pkt_idx_cert = pkt_global_idx

        # Stop if all three found
        if (self.client_hello is not None
                and self.server_hello is not None
                and self.certificate is not None):
            self.done_parsing = True


# ---------------------------------------------------------------------------
# JA3 / JA3S
# ---------------------------------------------------------------------------

def ja3(ch: ClientHello) -> str:
    """Compute JA3 fingerprint for a ClientHello."""
    ver = ch.legacy_version
    ciphers = [c for c in ch.cipher_suites if not _is_grease(c)]
    ext_types = [t for t in ch.extension_types if not _is_grease(t)]
    groups = [g for g in ch.supported_groups if not _is_grease(g)]
    points = ch.ec_point_formats

    s = (
        f"{ver},"
        f"{'-'.join(str(c) for c in ciphers)},"
        f"{'-'.join(str(e) for e in ext_types)},"
        f"{'-'.join(str(g) for g in groups)},"
        f"{'-'.join(str(p) for p in points)}"
    )
    return hashlib.md5(s.encode()).hexdigest()


def ja3s(sh: ServerHello) -> str:
    """Compute JA3S fingerprint for a ServerHello."""
    ver = sh.legacy_version
    cipher = sh.cipher_suite
    ext_types = [t for t in sh.extension_types if not _is_grease(t)]

    s = (
        f"{ver},"
        f"{cipher},"
        f"{'-'.join(str(e) for e in ext_types)}"
    )
    return hashlib.md5(s.encode()).hexdigest()


# ---------------------------------------------------------------------------
# JA4 / JA4S  (FoxIO specification)
# ---------------------------------------------------------------------------

def _ja4_tls_version(ch: ClientHello) -> str:
    """Determine TLS version string for JA4 prefix."""
    # Highest non-GREASE supported_versions value
    non_grease = [v for v in ch.supported_versions if not _is_grease(v)]
    if non_grease:
        best = max(non_grease)
        return _TLS_VERSION_MAP.get(best, "00")
    return _TLS_VERSION_MAP.get(ch.legacy_version, "00")


def _ja4_alpn_chars(alpn: list[str]) -> str:
    """Return 2-char ALPN indicator per JA4 spec."""
    if not alpn:
        return "00"
    proto = alpn[0]
    if not proto:
        return "00"
    first = proto[0]
    last = proto[-1]

    def _char(c: str) -> str:
        if c.isalnum():
            return c
        return format(ord(c), "02x")

    return _char(first) + _char(last)


def ja4(ch: ClientHello) -> str:
    """Compute JA4 fingerprint for a ClientHello (FoxIO spec)."""
    # --- Part a ---
    transport = "t"  # TCP
    tls_ver = _ja4_tls_version(ch)
    sni_flag = "d" if ch.sni else "i"

    non_grease_ciphers = [c for c in ch.cipher_suites if not _is_grease(c)]
    non_grease_exts = [t for t in ch.extension_types if not _is_grease(t)]

    cipher_count = min(len(non_grease_ciphers), 99)
    ext_count = min(len(non_grease_exts), 99)

    alpn_chars = _ja4_alpn_chars(ch.alpn)

    part_a = f"{transport}{tls_ver}{sni_flag}{cipher_count:02d}{ext_count:02d}{alpn_chars}"

    # --- Part b: SHA256 of sorted ciphers (4-hex each, comma-joined), first 12 hex chars ---
    sorted_ciphers = sorted(non_grease_ciphers)
    cipher_str = ",".join(format(c, "04x") for c in sorted_ciphers)
    part_b = hashlib.sha256(cipher_str.encode()).hexdigest()[:12]

    # --- Part c ---
    # Extensions: sorted, excluding SNI (0x0000) and ALPN (0x0010)
    ext_for_c = sorted(e for e in non_grease_exts if e not in (_EXT_SNI, _EXT_ALPN))

    # Signature algorithms (original order) are appended before hashing
    if ext_for_c:
        c_str = ",".join(format(e, "04x") for e in ext_for_c)
        sig_algs = [s for s in ch.signature_algorithms if not _is_grease(s)]
        if sig_algs:
            c_str += "_" + ",".join(format(s, "04x") for s in sig_algs)
        part_c = hashlib.sha256(c_str.encode()).hexdigest()[:12]
    else:
        part_c = "000000000000"

    return f"{part_a}_{part_b}_{part_c}"


def ja4s(sh: ServerHello) -> str:
    """Compute JA4S fingerprint for a ServerHello (FoxIO spec)."""
    # Format: t{ver}{ext_count:02}{alpn}_{cipher}_{sha256(exts in wire order)[:12]}
    tls_ver = _TLS_VERSION_MAP.get(sh.selected_version or sh.legacy_version, "00")
    exts = [t for t in sh.extension_types if not _is_grease(t)]
    alpn: list[str] = []
    for ext_type, data in sh.extensions_raw:
        if ext_type == _EXT_ALPN and len(data) >= 3:
            n = data[2]
            alpn = [data[3:3 + n].decode("latin-1")]
    part_a = f"t{tls_ver}{min(len(exts), 99):02d}{_ja4_alpn_chars(alpn)}"
    if exts:
        ext_hash = hashlib.sha256(",".join(format(e, "04x") for e in exts).encode()).hexdigest()[:12]
    else:
        ext_hash = "000000000000"
    return f"{part_a}_{format(sh.cipher_suite, '04x')}_{ext_hash}"


# ---------------------------------------------------------------------------
# PCAP reading
# ---------------------------------------------------------------------------

def _open_pcap(path: Path) -> tuple[object, bool]:
    """Open pcap or pcapng based on magic bytes; return (reader, is_pcapng)."""
    with open(path, "rb") as f:
        magic = f.read(4)

    # pcapng: section header block type 0x0A0D0D0A
    if magic == b"\x0a\x0d\x0d\x0a":
        return dpkt.pcapng.Reader(open(path, "rb")), True
    else:
        return dpkt.pcap.Reader(open(path, "rb")), False


def _decode_ip(raw: bytes, linktype: int) -> object:
    """Return the network-layer object for a frame of the given pcap link type."""
    if linktype == 1:  # Ethernet
        return dpkt.ethernet.Ethernet(raw).data
    if linktype in (12, 14, 101):  # raw IP (v4 or v6)
        return dpkt.ip6.IP6(raw) if raw[0] >> 4 == 6 else dpkt.ip.IP(raw)
    if linktype == 228:
        return dpkt.ip.IP(raw)
    if linktype == 229:
        return dpkt.ip6.IP6(raw)
    if linktype == 113:  # Linux cooked capture
        return dpkt.sll.SLL(raw).data
    if linktype == 276:  # Linux cooked capture v2
        return dpkt.sll2.SLL2(raw).data
    if linktype in (0, 108):  # BSD loopback / OpenBSD loop
        return dpkt.loopback.Loopback(raw).data
    return dpkt.ethernet.Ethernet(raw).data


def _ip_to_str(addr: bytes) -> str:
    if len(addr) == 4:
        return str(ipaddress.IPv4Address(addr))
    elif len(addr) == 16:
        return str(ipaddress.IPv6Address(addr))
    return addr.hex()


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def parse_pcap(path: str | Path, stats: dict | None = None) -> pd.DataFrame:
    """Parse a pcap/pcapng file and return a DataFrame of TLS flows.

    One row per flow that contains at least a ClientHello. If *stats* is given it is filled with
    packets_read, truncated (True when the file ends inside a packet) and read_error.
    """
    path = Path(path)
    reader, _is_ng = _open_pcap(path)

    flows: dict[_FlowKey, _Flow] = {}
    finished: list[_Flow] = []  # flows closed by idle timeout, kept for output
    order: dict[int, int] = {}  # id(flow) -> creation index, for stable output order
    FLOW_TIMEOUT = 120.0  # seconds idle
    EXPIRE_EVERY = 10.0  # scan for idle flows at most every 10 s of capture time
    next_expire = None

    global_pkt_idx = 0  # 1-based per-flow packet counter stored per flow
    read_error = None
    bytes_read = 24  # classic pcap: global header + (16-byte record header + data) per packet
    max_caplen = 0

    linktype = reader.datalink()

    try:
        for ts, raw in reader:
            global_pkt_idx += 1
            bytes_read += 16 + len(raw)
            max_caplen = max(max_caplen, len(raw))
            if next_expire is None:
                next_expire = ts + EXPIRE_EVERY
            elif ts >= next_expire:
                for k in [k for k, f in flows.items() if ts - f.last_ts > FLOW_TIMEOUT]:
                    finished.append(flows.pop(k))
                next_expire = ts + EXPIRE_EVERY
            try:
                ip_layer = _decode_ip(raw, linktype)
            except Exception:
                continue

            if isinstance(ip_layer, dpkt.ip.IP):
                ip_src = _ip_to_str(ip_layer.src)
                ip_dst = _ip_to_str(ip_layer.dst)
                tcp = ip_layer.data
            elif isinstance(ip_layer, dpkt.ip6.IP6):
                ip_src = _ip_to_str(ip_layer.src)
                ip_dst = _ip_to_str(ip_layer.dst)
                tcp = ip_layer.data
            else:
                continue

            if not isinstance(tcp, dpkt.tcp.TCP):
                continue

            port_src = tcp.sport
            port_dst = tcp.dport

            fkey, lower_is_src = _canonical_key(ip_src, port_src, ip_dst, port_dst)

            # A reused 5-tuple after the idle timeout starts a new flow
            if fkey in flows and ts - flows[fkey].last_ts > FLOW_TIMEOUT:
                finished.append(flows.pop(fkey))

            if fkey not in flows:
                # Determine client side: prefer SYN; fall back to first sender
                syn_set = bool(tcp.flags & dpkt.tcp.TH_SYN) and not bool(tcp.flags & dpkt.tcp.TH_ACK)
                if syn_set:
                    client_ip, client_port = ip_src, port_src
                    server_ip, server_port = ip_dst, port_dst
                else:
                    # First packet = client
                    client_ip, client_port = ip_src, port_src
                    server_ip, server_port = ip_dst, port_dst

                flow = _Flow(
                    key=fkey,
                    client_ip=client_ip,
                    client_port=client_port,
                    server_ip=server_ip,
                    server_port=server_port,
                    first_ts=ts,
                    last_ts=ts,
                )
                flows[fkey] = flow
                order[id(flow)] = len(order)

            flow = flows[fkey]
            flow.last_ts = ts
            flow.pkt_count += 1

            # Determine direction
            is_from_client = (ip_src == flow.client_ip and port_src == flow.client_port)

            payload = bytes(tcp.data)
            if payload and not flow.done_parsing:
                flow.feed_packet(is_from_client, payload, flow.pkt_count)

    except Exception as exc:  # e.g. dpkt.NeedData when the capture ends inside a packet
        read_error = f"{type(exc).__name__}: {exc}"
        log.warning("Stopped reading %s after %d packets: %s", path, global_pkt_idx, read_error)

    if stats is not None:
        # dpkt stops silently at a record cut short at the end of the file; for classic pcap that
        # shows up as fewer bytes read than the file holds (pcapng: not checked)
        cut = not _is_ng and bytes_read < path.stat().st_size
        stats.update(packets_read=global_pkt_idx, read_error=read_error, max_caplen=max_caplen,
                     truncated=cut or (read_error is not None and "NeedData" in read_error))

    # Build DataFrame rows
    rows: list[dict] = []
    for flow in sorted(finished + list(flows.values()), key=lambda f: order[id(f)]):
        if flow.client_hello is None:
            continue

        ch = flow.client_hello
        sh = flow.server_hello
        cert = flow.certificate

        _ja3 = ja3(ch)
        _ja4 = ja4(ch)
        _ja3s = ja3s(sh) if sh else None
        _ja4s = ja4s(sh) if sh else None

        row: dict = {
            "client_ip": flow.client_ip,
            "client_port": flow.client_port,
            "server_ip": flow.server_ip,
            "server_port": flow.server_port,
            "first_ts": flow.first_ts,
            # ClientHello
            "ch_legacy_version": ch.legacy_version,
            "ch_supported_versions": ch.supported_versions,
            "ch_cipher_suites": ch.cipher_suites,
            "ch_extension_types": ch.extension_types,
            "ch_supported_groups": ch.supported_groups,
            "ch_ec_point_formats": ch.ec_point_formats,
            "ch_signature_algorithms": ch.signature_algorithms,
            "ch_alpn": ch.alpn,
            "ch_sni": ch.sni,
            "ch_has_ech": ch.has_ech,
            # Fingerprints
            "ja3": _ja3,
            "ja4": _ja4,
            "ja3s": _ja3s,
            "ja4s": _ja4s,
            # ServerHello
            "sh_selected_version": sh.selected_version if sh else None,
            "sh_selected_cipher": sh.cipher_suite if sh else None,
            "sh_extension_types": sh.extension_types if sh else None,
            # Certificate
            "cert_count": cert.cert_count if cert else None,
            "cert_leaf_der_len": cert.leaf_der_len if cert else None,
            # Packet indices (1-based, counting all pkts in both directions)
            "pkt_idx_client_hello": flow.pkt_idx_ch,
            "pkt_idx_server_hello": flow.pkt_idx_sh,
            "pkt_idx_certificate": flow.pkt_idx_cert,
        }
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df
