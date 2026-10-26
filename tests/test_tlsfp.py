"""Pytest unit tests for TLS fingerprinting functions.

Tests cover ja3/ja4/ja3s/ja4s computation, GREASE removal, edge cases,
and raw ClientHello byte parsing via a mini serialiser helper.
"""

from __future__ import annotations

import hashlib
import struct

import pytest

from tlssok.tlsfp import (
    ClientHello,
    ServerHello,
    _parse_client_hello,
    _parse_server_hello,
    ja3,
    ja3s,
    ja4,
    ja4s,
    _GREASE,
    _is_grease,
)


# ---------------------------------------------------------------------------
# Helper: Serialise a ClientHello to raw bytes
# (Enough to be parseable by _parse_client_hello / the TLS record pipeline)
# ---------------------------------------------------------------------------

def _pack_uint8(v: int) -> bytes:
    return struct.pack("B", v)


def _pack_uint16(v: int) -> bytes:
    return struct.pack(">H", v)


def _pack_uint24(v: int) -> bytes:
    return struct.pack(">BH", v >> 16, v & 0xFFFF)


def _pack_len8(data: bytes) -> bytes:
    return _pack_uint8(len(data)) + data


def _pack_len16(data: bytes) -> bytes:
    return _pack_uint16(len(data)) + data


def _pack_len24(data: bytes) -> bytes:
    return _pack_uint24(len(data)) + data


def _build_sni_ext(hostname: str) -> bytes:
    name = hostname.encode()
    # host_name entry: type=0, len16, name
    entry = _pack_uint8(0) + _pack_len16(name)
    return _pack_len16(entry)


def _build_supported_versions_ext(versions: list[int]) -> bytes:
    body = b"".join(_pack_uint16(v) for v in versions)
    return _pack_len8(body)


def _build_supported_groups_ext(groups: list[int]) -> bytes:
    body = b"".join(_pack_uint16(g) for g in groups)
    return _pack_len16(body)


def _build_sig_algs_ext(algs: list[int]) -> bytes:
    body = b"".join(_pack_uint16(a) for a in algs)
    return _pack_len16(body)


def _build_alpn_ext(protos: list[str]) -> bytes:
    entries = b"".join(_pack_len8(p.encode()) for p in protos)
    return _pack_len16(entries)


def _build_extension(ext_type: int, data: bytes) -> bytes:
    return _pack_uint16(ext_type) + _pack_len16(data)


def build_client_hello_body(
    legacy_version: int = 0x0303,
    cipher_suites: list[int] | None = None,
    extensions: list[tuple[int, bytes]] | None = None,
) -> bytes:
    """Serialise a minimal ClientHello handshake body (without the 4-byte HS header)."""
    if cipher_suites is None:
        cipher_suites = [0x002F, 0x0035]  # AES128, AES256
    if extensions is None:
        extensions = []

    version_bytes = _pack_uint16(legacy_version)
    random_bytes = b"\x00" * 32
    session_id = _pack_len8(b"")  # empty

    cs_body = b"".join(_pack_uint16(c) for c in cipher_suites)
    cs_field = _pack_len16(cs_body)

    comp = _pack_len8(b"\x00")  # null compression

    ext_body = b"".join(_pack_uint16(t) + _pack_len16(d) for t, d in extensions)
    ext_field = _pack_len16(ext_body) if extensions else b""

    return version_bytes + random_bytes + session_id + cs_field + comp + ext_field


def build_raw_tls_record(content_type: int, version: int, payload: bytes) -> bytes:
    """Wrap payload in a single TLS record header."""
    return struct.pack(">BHH", content_type, version, len(payload)) + payload


def build_raw_handshake_record(msg_type: int, body: bytes) -> bytes:
    """Wrap body in a TLS handshake message."""
    return struct.pack(">B", msg_type) + _pack_uint24(len(body)) + body


# ---------------------------------------------------------------------------
# GREASE sanity
# ---------------------------------------------------------------------------

class TestGrease:
    def test_known_grease_values(self):
        known = [0x0A0A, 0x1A1A, 0x2A2A, 0x3A3A, 0x4A4A, 0x5A5A,
                 0x6A6A, 0x7A7A, 0x8A8A, 0x9A9A, 0xAAAA, 0xBABA,
                 0xCACA, 0xDADA, 0xEAEA, 0xFAFA]
        for v in known:
            assert _is_grease(v), f"{v:#06x} should be GREASE"

    def test_non_grease_values(self):
        non_grease = [0x0035, 0x002F, 0x1301, 0x0017, 0x000A]
        for v in non_grease:
            assert not _is_grease(v), f"{v:#06x} should NOT be GREASE"


# ---------------------------------------------------------------------------
# JA3 tests
# ---------------------------------------------------------------------------

class TestJA3:
    def _make_ch(self, **kwargs) -> ClientHello:
        ch = ClientHello(**kwargs)
        return ch

    def test_basic_ja3_is_md5(self):
        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x002F, 0x0035, 0xC02B],
            extensions_raw=[(0x000A, b""), (0x000B, b"")],
            supported_groups=[0x0017, 0x0018],
            ec_point_formats=[0x00],
        )
        result = ja3(ch)
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_grease_removed_from_ciphers(self):
        ch_no_grease = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x002F],
        )
        ch_with_grease = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x0A0A, 0x002F],  # 0x0A0A is GREASE
        )
        assert ja3(ch_no_grease) == ja3(ch_with_grease)

    def test_grease_removed_from_extensions(self):
        ch_no_grease = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x002F],
            extensions_raw=[(0x000A, b"")],
        )
        ch_with_grease = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x002F],
            extensions_raw=[(0xAAAA, b""), (0x000A, b"")],  # 0xAAAA GREASE
        )
        assert ja3(ch_no_grease) == ja3(ch_with_grease)

    def test_grease_removed_from_supported_groups(self):
        ch_clean = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x002F],
            extensions_raw=[(0x000A, b"")],
            supported_groups=[0x0017],
        )
        ch_grease = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x002F],
            extensions_raw=[(0x000A, b"")],
            supported_groups=[0xFAFA, 0x0017],
        )
        assert ja3(ch_clean) == ja3(ch_grease)

    def test_empty_extensions_ja3(self):
        ch = ClientHello(legacy_version=0x0303, cipher_suites=[0x002F])
        result = ja3(ch)
        assert len(result) == 32

    def test_known_ja3_value(self):
        # Manually computed: "769,47,,," -> md5
        ch = ClientHello(
            legacy_version=769,  # 0x0301 = TLS 1.0
            cipher_suites=[47],
            extensions_raw=[],
            supported_groups=[],
            ec_point_formats=[],
        )
        expected_str = "769,47,,,"
        expected = hashlib.md5(expected_str.encode()).hexdigest()
        assert ja3(ch) == expected


# ---------------------------------------------------------------------------
# JA3S tests
# ---------------------------------------------------------------------------

class TestJA3S:
    def test_basic_ja3s(self):
        sh = ServerHello(
            legacy_version=0x0303,
            cipher_suite=0x002F,
            extensions_raw=[(0x000A, b"")],
        )
        result = ja3s(sh)
        assert len(result) == 32

    def test_grease_removed(self):
        sh_clean = ServerHello(legacy_version=0x0303, cipher_suite=0x002F, extensions_raw=[])
        sh_grease = ServerHello(legacy_version=0x0303, cipher_suite=0x002F,
                                extensions_raw=[(0xCACA, b"")])
        assert ja3s(sh_clean) == ja3s(sh_grease)

    def test_known_ja3s_value(self):
        sh = ServerHello(legacy_version=771, cipher_suite=49199, extensions_raw=[])
        expected_str = "771,49199,"
        expected = hashlib.md5(expected_str.encode()).hexdigest()
        assert ja3s(sh) == expected


# ---------------------------------------------------------------------------
# JA4 tests  (FoxIO spec)
# ---------------------------------------------------------------------------

class TestJA4:
    def _foxio_reference_ch(self) -> ClientHello:
        """Build a ClientHello matching the FoxIO reference: TLS 1.3, SNI present,
        15 ciphers, 16 extensions, ALPN h2."""
        # 15 non-GREASE ciphers
        ciphers = [0x1301, 0x1302, 0x1303, 0xC02B, 0xC02F, 0xC02C, 0xC030,
                   0xCCA9, 0xCCA8, 0xC013, 0xC014, 0x009C, 0x009D, 0x002F, 0x0035]
        assert len(ciphers) == 15

        # 16 extensions (non-GREASE); includes SNI (0x0000) and ALPN (0x0010)
        ext_types_non_grease = [
            0x0000,  # SNI
            0x0017,  # extended_master_secret
            0xFF01,  # renegotiation_info
            0x000A,  # supported_groups
            0x000B,  # ec_point_formats
            0x0023,  # session_ticket
            0x0010,  # ALPN
            0x0005,  # status_request
            0x0012,  # signed_cert_timestamp
            0x000D,  # signature_algorithms
            0x0012,  # ... (we need 16 unique; adjust)
            0x002B,  # supported_versions
            0x002D,  # psk_key_exchange_modes
            0x0033,  # key_share
            0x001B,  # compress_certificate
            0x0015,  # padding
        ]
        # Ensure exactly 16 unique values:
        ext_types_16 = list(dict.fromkeys([
            0x0000, 0x0017, 0xFF01, 0x000A, 0x000B,
            0x0023, 0x0010, 0x0005, 0x0012, 0x000D,
            0x002B, 0x002D, 0x0033, 0x001B, 0x0015, 0x0039,
        ]))
        assert len(ext_types_16) == 16

        sig_algs = [0x0403, 0x0503, 0x0603, 0x0807, 0x0808, 0x0809, 0x080A, 0x080B,
                    0x0804, 0x0805, 0x0806, 0x0401, 0x0501, 0x0601, 0x0303, 0x0301]

        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=ciphers,
            extensions_raw=[(t, b"") for t in ext_types_16],
            supported_versions=[0x0304],  # TLS 1.3
            sni="example.com",
            alpn=["h2"],
            signature_algorithms=sig_algs,
        )
        return ch

    def test_foxio_reference_prefix(self):
        """JA4 must start with t13d1516h2_ for the reference ClientHello."""
        ch = self._foxio_reference_ch()
        result = ja4(ch)
        assert result.startswith("t13d1516h2_"), (
            f"Expected prefix 't13d1516h2_', got '{result[:11]}'"
        )

    def test_ja4_structure(self):
        """JA4 must have format: part_a_part_b_part_c."""
        ch = self._foxio_reference_ch()
        result = ja4(ch)
        parts = result.split("_")
        # part_a, part_b, and possibly part_c with sig_algs (_-separated)
        assert len(parts) >= 3, f"JA4 has wrong structure: {result}"
        part_a = parts[0]
        assert len(part_a) == 10, f"JA4 part_a length wrong: {part_a!r}"
        assert part_a[0] == "t"  # TCP

    def test_ja4_sni_flag(self):
        ch_sni = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1301],
            supported_versions=[0x0304],
            sni="example.com",
        )
        ch_no_sni = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1301],
            supported_versions=[0x0304],
            sni="",
        )
        assert ja4(ch_sni)[3] == "d"
        assert ja4(ch_no_sni)[3] == "i"

    def test_ja4_tls_version_from_supported_versions(self):
        """Highest non-GREASE supported_version determines TLS version string."""
        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1301],
            supported_versions=[0x0303, 0x0304],  # TLS 1.2 and 1.3
        )
        result = ja4(ch)
        assert result[1:3] == "13", f"Expected '13' version, got: {result}"

    def test_ja4_grease_excluded_from_cipher_count(self):
        ch_clean = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1301, 0x1302],
            supported_versions=[0x0304],
        )
        ch_grease = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x0A0A, 0x1301, 0x1302],  # GREASE prepended
            supported_versions=[0x0304],
        )
        # cipher count should be the same (2)
        assert ja4(ch_clean)[4:6] == ja4(ch_grease)[4:6]

    def test_ja4_empty_extensions(self):
        """With no extensions, part_c hash must be '000000000000'."""
        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x002F],
            extensions_raw=[],
        )
        result = ja4(ch)
        parts = result.split("_")
        # part_c starts with the 12-char hash; with no ext for c it's zeros
        assert parts[2] == "000000000000", f"Expected '000000000000' in part_c, got: {parts[2]}"

    def test_ja4_alpn_h2(self):
        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1301],
            supported_versions=[0x0304],
            alpn=["h2"],
        )
        result = ja4(ch)
        assert result[8:10] == "h2", f"ALPN chars wrong: {result}"

    def test_ja4_alpn_none(self):
        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1301],
            supported_versions=[0x0304],
            alpn=[],
        )
        result = ja4(ch)
        assert result[8:10] == "00", f"Empty ALPN should be '00': {result}"

    def test_ja4_part_b_is_sha256_sorted_ciphers(self):
        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1302, 0x1301],  # unsorted
            supported_versions=[0x0304],
        )
        sorted_ciphers = [0x1301, 0x1302]
        cipher_str = ",".join(format(c, "04x") for c in sorted_ciphers)
        expected_b = hashlib.sha256(cipher_str.encode()).hexdigest()[:12]
        result = ja4(ch)
        parts = result.split("_")
        assert parts[1] == expected_b

    def test_ja4_grease_excluded_from_ext_count(self):
        ch = ClientHello(
            legacy_version=0x0303,
            cipher_suites=[0x1301],
            supported_versions=[0x0304],
            extensions_raw=[(0xAAAA, b""), (0x000A, b""), (0x000D, b"")],
        )
        # 0xAAAA is GREASE -> ext_count = 2
        result = ja4(ch)
        assert result[6:8] == "02", f"Ext count wrong: {result}"


# ---------------------------------------------------------------------------
# JA4S tests
# ---------------------------------------------------------------------------

class TestJA4S:
    def test_basic_ja4s_structure(self):
        sh = ServerHello(
            legacy_version=0x0303,
            selected_version=0x0303,
            cipher_suite=0x1301,
            extensions_raw=[(0x002B, b"")],
        )
        result = ja4s(sh)
        parts = result.split("_")
        assert len(parts) == 3
        assert parts[0] == "t120100" and parts[1] == "1301"

    def test_ja4s_foxio_reference(self):
        # FoxIO README example: TLS 1.3, supported_versions + key_share, no ALPN
        sh = ServerHello(
            legacy_version=0x0303,
            selected_version=0x0304,
            cipher_suite=0x1301,
            extensions_raw=[(0x0033, b""), (0x002B, b"\x03\x04")],
        )
        assert ja4s(sh) == "t130200_1301_234ea6891581"

    def test_ja4s_tls13(self):
        sh = ServerHello(
            legacy_version=0x0303,
            selected_version=0x0304,
            cipher_suite=0x1301,
        )
        result = ja4s(sh)
        assert result.startswith("t13"), f"Expected 't13' prefix, got: {result}"

    def test_ja4s_empty_extensions(self):
        sh = ServerHello(
            legacy_version=0x0303,
            selected_version=0x0303,
            cipher_suite=0x002F,
            extensions_raw=[],
        )
        result = ja4s(sh)
        assert result.endswith("000000000000")


# ---------------------------------------------------------------------------
# Raw bytes parsing tests
# ---------------------------------------------------------------------------

class TestRawParsing:
    def test_parse_basic_client_hello_body(self):
        """Build raw ClientHello bytes and verify ciphers are recovered."""
        ciphers = [0x002F, 0x0035, 0xC02B]
        body = build_client_hello_body(
            legacy_version=0x0303,
            cipher_suites=ciphers,
        )
        ch = _parse_client_hello(body)
        assert ch is not None
        assert ch.legacy_version == 0x0303
        assert ch.cipher_suites == ciphers

    def test_parse_client_hello_with_sni(self):
        """ClientHello with SNI extension: verify sni is extracted."""
        sni_data = _build_sni_ext("test.example.com")
        exts = [(0x0000, sni_data)]
        body = build_client_hello_body(
            legacy_version=0x0303,
            cipher_suites=[0x002F],
            extensions=exts,
        )
        ch = _parse_client_hello(body)
        assert ch is not None
        assert ch.sni == "test.example.com"

    def test_parse_client_hello_with_supported_versions(self):
        """supported_versions extension is parsed correctly."""
        sv_data = _build_supported_versions_ext([0x0304, 0x0303])
        exts = [(0x002B, sv_data)]
        body = build_client_hello_body(extensions=exts)
        ch = _parse_client_hello(body)
        assert ch is not None
        assert 0x0304 in ch.supported_versions
        assert 0x0303 in ch.supported_versions

    def test_parse_client_hello_with_alpn(self):
        """ALPN extension is parsed into list of protocol strings."""
        alpn_data = _build_alpn_ext(["h2", "http/1.1"])
        exts = [(0x0010, alpn_data)]
        body = build_client_hello_body(extensions=exts)
        ch = _parse_client_hello(body)
        assert ch is not None
        assert ch.alpn == ["h2", "http/1.1"]

    def test_parse_client_hello_with_sig_algs(self):
        """signature_algorithms extension parsed into list."""
        algs = [0x0403, 0x0503, 0x0804]
        sa_data = _build_sig_algs_ext(algs)
        exts = [(0x000D, sa_data)]
        body = build_client_hello_body(extensions=exts)
        ch = _parse_client_hello(body)
        assert ch is not None
        assert ch.signature_algorithms == algs

    def test_parse_client_hello_ech_presence(self):
        """ECH extension (0xfe0d) is detected."""
        exts = [(0xFE0D, b"\x00" * 4)]
        body = build_client_hello_body(extensions=exts)
        ch = _parse_client_hello(body)
        assert ch is not None
        assert ch.has_ech is True

    def test_parse_client_hello_no_ech(self):
        body = build_client_hello_body()
        ch = _parse_client_hello(body)
        assert ch is not None
        assert ch.has_ech is False

    def test_parse_truncated_body_does_not_crash(self):
        """Truncated input must not raise; may return None or partial."""
        for trunc in [0, 1, 5, 10, 33]:
            body = build_client_hello_body()[:trunc]
            # Should not raise
            ch = _parse_client_hello(body)
            # May be None or partial; that's fine

    def test_parse_full_hello_extension_types(self):
        """All extension types are present in wire order."""
        exts = [
            (0x0000, _build_sni_ext("foo.com")),
            (0x000A, _build_supported_groups_ext([0x0017])),
            (0x002B, _build_supported_versions_ext([0x0304])),
        ]
        body = build_client_hello_body(extensions=exts)
        ch = _parse_client_hello(body)
        assert ch is not None
        assert ch.extension_types == [0x0000, 0x000A, 0x002B]
        assert ch.sni == "foo.com"
        assert ch.supported_groups == [0x0017]
        assert 0x0304 in ch.supported_versions

    def test_parse_server_hello_basic(self):
        """Build and parse a minimal ServerHello body."""
        version = 0x0303
        random = b"\x00" * 32
        session_id = b""
        cipher = 0x1301
        comp = 0

        body = (
            struct.pack(">H", version)
            + random
            + struct.pack("B", len(session_id)) + session_id
            + struct.pack(">H", cipher)
            + struct.pack("B", comp)
        )
        sh = _parse_server_hello(body)
        assert sh is not None
        assert sh.legacy_version == version
        assert sh.cipher_suite == cipher

    def test_parse_server_hello_selected_version_from_ext(self):
        """supported_versions extension overrides legacy_version for selected_version."""
        version = 0x0303
        random = b"\x00" * 32
        cipher = 0x1301
        comp = 0

        # Build supported_versions extension with TLS 1.3
        sv_ext_body = struct.pack(">H", 0x0304)
        ext = struct.pack(">H", 0x002B) + struct.pack(">H", len(sv_ext_body)) + sv_ext_body
        ext_list = struct.pack(">H", len(ext)) + ext

        body = (
            struct.pack(">H", version)
            + random
            + struct.pack("B", 0)  # empty session_id
            + struct.pack(">H", cipher)
            + struct.pack("B", comp)
            + ext_list
        )
        sh = _parse_server_hello(body)
        assert sh is not None
        assert sh.selected_version == 0x0304


# ---------------------------------------------------------------------------
# FEATURE_VISIBILITY metadata test
# ---------------------------------------------------------------------------

class TestFeatureVisibility:
    def test_all_expected_columns_present(self):
        from tlssok.tlsfp import FEATURE_VISIBILITY
        required = {
            "ch_legacy_version", "ch_cipher_suites", "ja3", "ja4",
            "sh_selected_version", "cert_count",
        }
        for col in required:
            assert col in FEATURE_VISIBILITY, f"Missing column: {col}"

    def test_cert_fields_tls12_only(self):
        from tlssok.tlsfp import FEATURE_VISIBILITY
        for col in ("cert_count", "cert_leaf_der_len"):
            vis = FEATURE_VISIBILITY[col]
            assert vis["tls12"] is True
            assert vis["tls13"] is False

    def test_ech_outer_only_flag_on_sni(self):
        from tlssok.tlsfp import FEATURE_VISIBILITY
        sni_vis = FEATURE_VISIBILITY["ch_sni"]
        assert sni_vis.get("ech_outer_only") is True

    def test_groups_have_valid_group_value(self):
        from tlssok.tlsfp import FEATURE_VISIBILITY
        valid_groups = {"G3", "G4", "G5"}
        for col, meta in FEATURE_VISIBILITY.items():
            assert meta["group"] in valid_groups, f"Invalid group for {col}: {meta['group']}"
