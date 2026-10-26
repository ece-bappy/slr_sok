"""Fill missing or junk abstracts in merged.csv from scholarly metadata APIs.

Usage: python scripts/enrich_abstracts.py [--merged review/search/merged.csv] [--out review/search/records.csv]

Tries, in order, for each record lacking a usable abstract (< 150 chars or only a link):
  1. Crossref /works/{doi}            (many Springer/IEEE/ACM deposits include the abstract)
  2. Semantic Scholar /paper/batch    (by DOI, arXiv id or S2 id; 500 per request)
  3. OpenAlex /works/doi:{doi}        (singleton lookups; needs OPENALEX_API_KEY)
  4. arXiv API                        (by arXiv id)
Publisher web pages are not scraped. merged.csv (the search export) is left unchanged; the
output adds abstract_source ("search", "crossref", "semanticscholar", "openalex", "arxiv" or
"none") and a per-record log goes to enrich_log.csv next to the output.
"""
import argparse
import csv
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "tls-sok-review/0.1 (systematic review; abstract lookup)"}


def usable(a: str) -> bool:
    a = (a or "").strip()
    return len(a) >= 150 and not re.fullmatch(r"(https?://\S+|doi:\S+|10\.\d+/\S+)", a)


def clean(a: str) -> str:
    a = re.sub(r"<[^>]+>", " ", a or "")  # JATS/HTML tags
    a = html.unescape(a)
    a = re.sub(r"^\s*(abstract|summary)[:.\s]+", "", a, flags=re.I)
    return re.sub(r"\s+", " ", a).strip()


def get_json(url: str, headers: dict | None = None, data: bytes | None = None, tries: int = 4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            return None
        except (TimeoutError, urllib.error.URLError, ConnectionError):
            if attempt < tries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            return None


def from_crossref(doi: str) -> str:
    d = get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    time.sleep(0.3)
    return clean((d or {}).get("message", {}).get("abstract", ""))


def from_s2_batch(ids: list[str]) -> dict[str, str]:
    """ids like 'DOI:10.x/y', 'ARXIV:2101.00001', '<s2 paperId>'; returns {id: abstract}.

    The keyless pool is shared and often answers 429, but one batch request covers 500 ids,
    so without a key we wait patiently (up to ~1 h per chunk) instead of giving up.
    """
    out = {}
    headers = {**UA, "Content-Type": "application/json"}
    key = user_env("S2_API_KEY")
    if key:
        headers["x-api-key"] = key
    waits = [5, 15, 30, 60] if key else [30, 60, 120, 300, 600, 900, 1200, 1200]
    url = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=abstract"
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        res = None
        for attempt, wait in enumerate([0] + waits):
            time.sleep(wait)
            try:
                req = urllib.request.Request(url, data=json.dumps({"ids": chunk}).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=120) as r:
                    res = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                print(f"  semantic scholar chunk {i // 500 + 1}: HTTP {e.code} (attempt {attempt + 1})", flush=True)
            except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
                print(f"  semantic scholar chunk {i // 500 + 1}: {e} (attempt {attempt + 1})", flush=True)
        if res is None:
            print(f"  semantic scholar chunk {i // 500 + 1}: GAVE UP, {len(chunk)} ids not looked up", flush=True)
            continue
        for qid, paper in zip(chunk, res):
            if paper and paper.get("abstract"):
                out[qid] = clean(paper["abstract"])
        time.sleep(3)
    return out


def user_env(name: str) -> str:
    """Environment variable, falling back to the Windows user environment (setx) for older shells."""
    k = os.environ.get(name, "")
    if not k and os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                k = winreg.QueryValueEx(h, name)[0]
        except OSError:
            pass
    return k.strip()


def openalex_key() -> str:
    return user_env("OPENALEX_API_KEY")


def from_openalex(doi: str, key: str) -> str:
    if not key:
        return ""
    d = get_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}?select=abstract_inverted_index"
                 f"&api_key={key}")
    time.sleep(0.15)
    inv = (d or {}).get("abstract_inverted_index") or {}
    pos = {p: w for w, ps in inv.items() for p in ps}
    return clean(" ".join(pos[i] for i in sorted(pos)))


def from_arxiv(arxiv_id: str) -> str:
    url = "http://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(arxiv_id)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            root = ET.fromstring(r.read())
    except Exception:
        return ""
    finally:
        time.sleep(3.5)  # arXiv asks for >= 3 s between requests
    ns = {"a": "http://www.w3.org/2005/Atom"}
    e = root.find("a:entry/a:summary", ns)
    return clean(e.text if e is not None else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", default=str(ROOT / "review" / "search" / "merged.csv"))
    ap.add_argument("--out", default=str(ROOT / "review" / "search" / "records.csv"))
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.merged, encoding="utf-8")))
    for r in rows:
        r["abstract_source"] = "search" if usable(r["abstract"]) else "none"
    need = [r for r in rows if r["abstract_source"] == "none"]
    print(f"{len(need)} of {len(rows)} records need an abstract")
    log = []

    def take(r: dict, text: str, source: str) -> bool:
        if usable(text):
            r["abstract"], r["abstract_source"] = text, source
            log.append({"id": r["id"], "source": source, "chars": len(text)})
            return True
        return False

    # 1. Crossref
    for n, r in enumerate([r for r in need if r["doi"]], 1):
        take(r, from_crossref(r["doi"]), "crossref")
        if n % 50 == 0:
            print(f"  crossref {n} done, recovered so far {len(log)}")
    # 2. Semantic Scholar batch
    left = [r for r in need if r["abstract_source"] == "none"]
    qid = {}
    for r in left:
        if r["doi"]:
            qid[r["id"]] = "DOI:" + r["doi"]
        elif r["arxiv_id"]:
            qid[r["id"]] = "ARXIV:" + r["arxiv_id"]
        elif r["s2_id"]:
            qid[r["id"]] = r["s2_id"]
    got = from_s2_batch(list(qid.values()))
    for r in left:
        if r["id"] in qid:
            take(r, got.get(qid[r["id"]], ""), "semanticscholar")
    print(f"  after semantic scholar: recovered {len(log)}")
    # 3. OpenAlex singleton by DOI
    key = openalex_key()
    for r in [r for r in need if r["abstract_source"] == "none" and r["doi"]]:
        take(r, from_openalex(r["doi"], key), "openalex")
    print(f"  after openalex: recovered {len(log)}")
    # 4. arXiv
    for r in [r for r in need if r["abstract_source"] == "none" and r["arxiv_id"]]:
        take(r, from_arxiv(r["arxiv_id"]), "arxiv")
    print(f"  after arxiv: recovered {len(log)}")

    out = Path(a.out)
    fields = list(rows[0].keys())
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(out.with_name("enrich_log.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "source", "chars"])
        w.writeheader()
        w.writerows(log)
    still = [r for r in need if r["abstract_source"] == "none"]
    print(f"recovered {len(log)} of {len(need)}; still missing {len(still)} -> {out}")


if __name__ == "__main__":
    main()
