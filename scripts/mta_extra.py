"""Re-check zips skipped by build_queues.py mta: queue traffic captures the first filter missed.

Usage: python scripts/mta_extra.py SKIPPED_LIST OUT.tsv
Keeps *.pcap.zip / *.pcapng.zip, and names with "traffic" that are not text, e-mail or spam examples.
Malware/artifact archives stay excluded.
"""
import re
import sys
import urllib.parse

from build_queues import get

TEXTISH = ("malspam", "text", "txt", "example", "email", "eml", "csv", "html")
rows = []
for line in open(sys.argv[1], encoding="utf-8"):
    year, url = line.rstrip("\n").split("\t")
    name = url.rsplit("/", 1)[-1].lower()
    if "artifact" in name:
        continue
    if re.search(r"\.pcap(ng)?\.zip$", name) or ("traffic" in name and not any(k in name for k in TEXTISH)):
        size = get(url, "HEAD")
        if size:
            post = url.split(f"/{year}/", 1)[1].rsplit("/", 1)[0]
            rows.append(f"mta/{year}/{post}/{urllib.parse.unquote(url.rsplit('/', 1)[-1])}\t{url}\t{size}\n")
            print(rows[-1], end="", flush=True)
open(sys.argv[2], "w", newline="\n", encoding="utf-8").writelines(rows)
print(len(rows), "extra files")
