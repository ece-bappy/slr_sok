"""Download repository copies (arXiv, HAL, university repositories, PMC) of the papers in download_list.csv.

Usage: python scripts/fetch_repo_pdfs.py [--dry-run]
Finds each paper's repository locations through the OpenAlex API and downloads only from
non-publisher hosts, one file at a time with a pause between requests. Publisher sites are never
fetched by script (their terms forbid it); those stay manual. Saves to D:/new papers/papers/core/<id>.pdf,
keeps a file only if it really is a PDF, and records the result in review/fulltext/fetch_log.csv.
"""
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from enrich_abstracts import user_env

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "review" / "fulltext" / "download_list.csv"
LOG = ROOT / "review" / "fulltext" / "fetch_log.csv"
DEST = ROOT.parent / "papers" / "core"
PAUSE_S = 6  # between downloads; arXiv asks for at least 3 s
UA = "tls-sok-literature-review/1.0 (academic systematic review; polite single-threaded fetch)"
PUBLISHER_HOSTS = ("ieee", "springer", "sciencedirect", "elsevier", "acm.org", "wiley", "mdpi", "tandfonline",
                   "nature.com", "plos.org", "frontiersin", "hindawi", "sagepub", "doi.org", "techscience", "iospress",
                   "sciencepubco", "acceptance")


def openalex_repo_urls(rows: list[dict]) -> dict:
    """id -> [pdf urls on repository hosts], best first (arXiv first)."""
    key = user_env("OPENALEX_API_KEY")
    by_doi = {r["doi_link"].replace("https://doi.org/", "").lower(): r["id"] for r in rows if r["doi_link"]}
    out = {}
    dois = list(by_doi)
    for i in range(0, len(dois), 50):
        q = urllib.parse.urlencode({"filter": "doi:" + "|".join(dois[i : i + 50]), "per-page": 100,
                                    "select": "doi,locations", "api_key": key})
        with urllib.request.urlopen(f"https://api.openalex.org/works?{q}", timeout=120) as resp:
            for w in json.loads(resp.read())["results"]:
                rid = by_doi.get((w["doi"] or "").replace("https://doi.org/", "").lower())
                urls = []
                for loc in w.get("locations") or []:
                    u = loc.get("pdf_url") or ""
                    src = (loc.get("source") or {}).get("type", "")
                    if u and src == "repository" and not any(h in u.lower() for h in PUBLISHER_HOSTS):
                        urls.append(u.replace("://arxiv.org/", "://export.arxiv.org/"))
                if rid and urls:
                    out[rid] = sorted(set(urls), key=lambda u: "arxiv" not in u)
        time.sleep(1)
    for r in rows:  # arXiv-only records (no DOI)
        if r["id"] not in out and "arxiv.org/abs/" in r["open_access_link"]:
            out[r["id"]] = [r["open_access_link"].replace("arxiv.org/abs/", "export.arxiv.org/pdf/")]
    return out


def fetch(url: str, dest: Path) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read(60_000_000)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        return f"error: {e}"
    if not data.startswith(b"%PDF"):
        return "not a pdf (landing page?)"
    dest.write_bytes(data)
    return f"ok {len(data) // 1024} KB"


def main() -> None:
    rows = list(csv.DictReader(open(LIST, encoding="utf-8-sig")))
    urls = openalex_repo_urls(rows)
    print(f"{len(urls)} of {len(rows)} papers have a repository copy", flush=True)
    if "--dry-run" in sys.argv:
        for i, u in urls.items():
            print(i, u)
        return
    DEST.mkdir(parents=True, exist_ok=True)
    log = []
    for r in rows:
        dest = DEST / f"{r['id']}.pdf"
        if dest.exists():
            log.append({"id": r["id"], "url": "", "result": "already present"})
            continue
        result, used = "no repository copy", ""
        for u in urls.get(r["id"], []):
            used = u
            result = fetch(u, dest)
            print(f"{r['id']}: {result} <- {u}", flush=True)
            time.sleep(PAUSE_S)
            if result.startswith("ok"):
                break
        log.append({"id": r["id"], "url": used, "result": result})
    with open(LOG, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "url", "result"])
        w.writeheader()
        w.writerows(log)
    print(sum(x["result"].startswith(("ok", "already")) for x in log), "PDFs in", DEST)


if __name__ == "__main__":
    main()
