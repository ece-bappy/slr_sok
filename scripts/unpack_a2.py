"""Unpack the archived pcaps on A2 into /data/tls-sok/unpacked, safely resumable.

Usage: python scripts/unpack_a2.py [raid_tranco|raid_ms|hikari_benign|all]

Each member is written to NAME.part and renamed only after its size matches the archive entry, and a
file is skipped only if it already has the exact size, so an interrupted run never leaves a partial
pcap that looks complete. Only pcaps are extracted; RAID's sslkeylog_*.txt files are left out because
they would allow decryption, which this study excludes.
"""
import shutil
import sys
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path

RAW = Path("/data/tls-sok/raw")
OUT = Path("/data/tls-sok/unpacked")
PCAP = (".pcap", ".pcapng")


def say(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def put(src, dest: Path, size: int) -> bool:
    """Copy the stream *src* to *dest* via a .part file; False if it was already complete."""
    if dest.exists() and dest.stat().st_size == size:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with open(part, "wb") as f:
        shutil.copyfileobj(src, f, 16 << 20)
    if part.stat().st_size != size:
        raise IOError(f"{dest}: wrote {part.stat().st_size} bytes, expected {size}")
    part.rename(dest)
    return True


def unzip(archive: Path, dest_dir: Path, flat: bool) -> None:
    with zipfile.ZipFile(archive) as z:
        members = [m for m in z.infolist() if m.filename.endswith(PCAP)]
        new = 0
        for m in members:
            dest = dest_dir / (Path(m.filename).name if flat else m.filename)
            if dest.exists() and dest.stat().st_size == m.file_size:
                continue
            with z.open(m) as src:
                new += put(src, dest, m.file_size)
    say(f"{archive.name}: {len(members)} pcaps, {new} extracted now")


def untar(archive: Path, dest_dir: Path) -> None:
    n = new = 0
    with tarfile.open(archive, "r:gz") as t:
        for m in t:  # streaming: the archive is read once
            if not (m.isfile() and m.name.endswith(PCAP)):
                continue
            n += 1
            new += put(t.extractfile(m), dest_dir / m.name, m.size)
    say(f"{archive.name}: {n} pcaps, {new} extracted now")


def main(what: str) -> None:
    for p in OUT.rglob("*.part"):  # leftovers from an interrupted run
        p.unlink()
    if what in ("all", "raid_tranco"):
        for z in sorted((RAW / "raid_tranco" / "pcaps").glob("*.zip")):
            unzip(z, OUT / "raid_tranco", flat=False)
    if what in ("all", "raid_ms"):
        untar(RAW / "raid_ms" / "captures.tar.gz", OUT / "raid_ms")
    if what in ("all", "hikari_benign"):
        unzip(RAW / "hikari" / "ground-truth.zip", OUT / "hikari_benign", flat=True)
    say(f"UNPACK_FINISHED {what}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
