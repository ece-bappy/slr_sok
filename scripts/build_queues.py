"""Build fetch.sh queues (<rel>\t<url>\t<bytes>) with exact sizes from HTTP HEAD, at 1 request/s.

Usage:
  python scripts/build_queues.py mcfp MCFP_SIZES.csv MCFP_NORMAL_SIZES.csv OUT.tsv
  python scripts/build_queues.py mta OUT.tsv [--years 2019-2026]

mcfp: malware captures from 2013-2018 that have a Zeek ssl.log and <= 2 GB of pcap, plus every Normal
      capture with TLS (sizes from review/datasets/*.csv). Only pcap files are queued.
mta:  per post, the pcap zip(s) and the IOC text zip; malware/artifact archives are never queued.
Skipped zip names are written to OUT.tsv.skipped for review.
"""
import csv
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (research dataset download; tls-sok)"}
MCFP = "https://mcfp.felk.cvut.cz/publicDatasets/"
MTA = "https://www.malware-traffic-analysis.net/"
PCAP_EXT = (".pcap", ".pcap.gz", ".pcap.bz2", ".pcap.xz", ".pcapng")
TEXTISH = ("malspam", "text", "txt", "example", "email", "eml", "csv", "html")


def get(url: str, method: str = "GET"):
    time.sleep(1)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA, method=method), timeout=60) as r:
                return r.headers.get("Content-Length") if method == "HEAD" else r.read().decode("utf-8", "replace")
        except Exception as e:  # transient network errors: back off and retry
            err = e
            time.sleep(10 * (attempt + 1))
    print("FAILED", url, err, flush=True)
    return None


def mcfp(sizes: str, normal: str, out: str) -> None:
    pick = [r["name"] for r in csv.DictReader(open(sizes, encoding="utf-8"))
            if r["year"] in ("2013", "2014", "2015", "2016", "2017", "2018")
            and int(r["ssl_log_bytes"]) > 0 and 0 < int(r["pcap_bytes"]) <= 2e9]
    pick += [r["name"] for r in csv.DictReader(open(normal, encoding="utf-8"))
             if "Normal" in r["name"] and int(r["ssl_log_bytes"]) > 0 and int(r["pcap_bytes"]) > 0]
    print(len(pick), "captures", flush=True)
    with open(out, "w", newline="\n", encoding="utf-8") as f:
        for n, cap in enumerate(pick, 1):
            page = get(MCFP + cap + "/") or ""
            for name in re.findall(r'href="([^"?/][^"]*)"', page):
                if name.endswith(PCAP_EXT) and "dns" not in name.lower():
                    url = MCFP + cap + "/" + name
                    size = get(url, "HEAD")
                    if size:
                        f.write(f"mcfp/{cap}/{urllib.parse.unquote(name)}\t{url}\t{size}\n")
            f.flush()
            if n % 10 == 0:
                print(n, flush=True)


def mta(out: str, years: range) -> None:
    # Resumable: finished posts are listed in OUT.done; rows are de-duplicated at the end.
    done_path = Path(out + ".done")
    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
    with open(out, "a", newline="\n", encoding="utf-8") as f, open(out + ".skipped", "a", encoding="utf-8") as skip, \
            open(done_path, "a", encoding="utf-8") as dl:
        for y in years:
            index = get(f"{MTA}{y}/index.html") or ""
            posts = sorted(set(re.findall(r'href="(\d\d/\d\d/(?:\d+/)?index\d*\.html)"', index)))
            print(y, len(posts), "posts", len([p for p in posts if f"{y}/{p}" in done]), "done", flush=True)
            for p in posts:
                if f"{y}/{p}" in done:
                    continue
                base = f"{MTA}{y}/{p}"
                page = get(base) or ""
                for href in sorted(set(re.findall(r'href="([^"]+\.zip)"', page))):
                    name = href.rsplit("/", 1)[-1].lower()
                    # IOC text, pcaps (even if "malware" is in the name), and traffic zips that are not
                    # text/e-mail examples; never malware/artifact archives or Fiddler .saz sessions
                    keep = ("ioc" in name or "indicator" in name) or (
                        "artifact" not in name and ".saz" not in name and (
                            re.search(r"\.pcap(ng)?\.zip$", name) or
                            ("pcap" in name and "malware" not in name) or
                            ("traffic" in name and not any(k in name for k in TEXTISH))))
                    url = urllib.parse.urljoin(base, href)
                    if not keep:
                        skip.write(f"{y}\t{url}\n")
                        continue
                    size = get(url, "HEAD")
                    if size:
                        f.write(f"mta/{y}/{p.rsplit('/', 1)[0]}/{urllib.parse.unquote(href.rsplit('/', 1)[-1])}\t{url}\t{size}\n")
                f.flush()
                if page:
                    dl.write(f"{y}/{p}\n")
                    dl.flush()
    for p in (out, out + ".skipped"):  # drop rows repeated by a resumed post
        lines = Path(p).read_text(encoding="utf-8").splitlines()
        Path(p).write_text("".join(l + "\n" for l in dict.fromkeys(lines)), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    if sys.argv[1] == "mcfp":
        mcfp(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        a, b = (sys.argv[4].split("-") if len(sys.argv) > 4 else ("2019", "2026"))
        mta(sys.argv[2], range(int(a), int(b) + 1))
