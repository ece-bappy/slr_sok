"""Venue-quality check for every search record (the low_venue exclusion criterion in plan.md §3).

Usage: python scripts/venue_check.py
Looks up each record's publication source in OpenAlex (is_core, is_retracted) and its DBLP key via
Semantic Scholar, then writes review/search/venue_check.csv with venue_ok and the rule that decided it:
  retracted   OpenAlex marks the work retracted, or the title says WITHDRAWN/RETRACTED  -> fail
  dblp        the paper is indexed in DBLP                                           -> ok
  indexed     the source is in OpenAlex's core set (CWTS curated, Scopus/WoS-like)   -> ok
  venue       not itself in DBLP/core, but another record from the same venue is
              (DBLP indexes recent proceedings late)                                -> ok
  arxiv       arXiv preprint (plan.md: peer-reviewed venues plus arXiv)               -> ok
  unindexed   anything else (other preprint servers, data/software deposits, theses,
              patents, unindexed journals and proceedings, unknown venue)             -> fail
"""
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from enrich_abstracts import user_env

ROOT = Path(__file__).resolve().parent.parent
SEARCH = ROOT / "review" / "search"


def get_json(url: str, data: bytes | None = None, headers: dict | None = None) -> dict:
    for wait in [0, 5, 15, 30, 60, 120]:
        time.sleep(wait)
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  {url[:60]}...: {e} (retrying)", flush=True)
    raise SystemExit(f"giving up on {url[:80]}")


def openalex(recs: list[dict]) -> dict:
    """id -> {source, source_type, is_core, retracted} for records with an OpenAlex id or DOI."""
    key = user_env("OPENALEX_API_KEY")
    out = {}
    for field, col in [("openalex", "openalex_id"), ("doi", "doi")]:
        todo = [r for r in recs if r["id"] not in out and r[col]]
        by_val = {r[col].rsplit("/", 1)[-1].lower() if field == "openalex" else r[col].lower(): r["id"] for r in todo}
        vals = list(by_val)
        for i in range(0, len(vals), 50):
            flt = f"{field}:" + "|".join(vals[i : i + 50])
            q = urllib.parse.urlencode({"filter": flt, "per-page": 100, "api_key": key,
                                        "select": "id,doi,is_retracted,primary_location,locations"})
            for w in get_json(f"https://api.openalex.org/works?{q}")["results"]:
                v = w["id"].rsplit("/", 1)[-1].lower() if field == "openalex" else (w["doi"] or "").replace("https://doi.org/", "").lower()
                if v not in by_val:
                    continue
                srcs = [loc.get("source") for loc in [w.get("primary_location") or {}] + (w.get("locations") or [])]
                srcs = [s for s in srcs if s]
                core = next((s for s in srcs if s.get("is_core")), None)
                s = core or (srcs[0] if srcs else {})
                out[by_val[v]] = {"oa_source": s.get("display_name", ""), "oa_source_type": s.get("type", ""),
                                  "oa_is_core": bool(core), "retracted": bool(w.get("is_retracted"))}
        print(f"openalex by {field}: {len(out)} records", flush=True)
    return out


def dblp_keys(recs: list[dict]) -> dict:
    """id -> DBLP key (or '') via the Semantic Scholar batch API."""
    key = user_env("S2_API_KEY")
    headers = {"Content-Type": "application/json", **({"x-api-key": key} if key else {})}
    ids = {}
    for r in recs:
        if r["s2_id"]:
            ids[r["s2_id"]] = r["id"]
        elif r["doi"]:
            ids[f"DOI:{r['doi']}"] = r["id"]
        elif r["arxiv_id"]:
            ids[f"ARXIV:{r['arxiv_id']}"] = r["id"]
    vals, out = list(ids), {}
    url = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=externalIds"
    for i in range(0, len(vals), 500):
        chunk = vals[i : i + 500]
        res = get_json(url, json.dumps({"ids": chunk}).encode(), headers)
        for q, p in zip(chunk, res):
            out[ids[q]] = ((p or {}).get("externalIds") or {}).get("DBLP", "")
        time.sleep(1.1)
    print(f"semantic scholar: {len(out)} records, {sum(bool(v) for v in out.values())} in DBLP", flush=True)
    return out


def venue_key(r: dict) -> str:
    """Venue name without years, ordinals and punctuation, so yearly editions compare equal."""
    name = (r["oa_source"] or r["venue"]).lower()
    return " ".join(re.sub(r"\b(19|20)\d\d\b|\b\d+(st|nd|rd|th)\b|[^a-z ]", " ", name).split())


def main() -> None:
    recs = list(csv.DictReader(open(SEARCH / "records.csv", encoding="utf-8")))
    oa, dblp = openalex(recs), dblp_keys(recs)
    rows = []
    for r in recs:
        o = oa.get(r["id"], {})
        t = r["title"].upper()
        if o.get("retracted") or t.startswith(("WITHDRAWN", "RETRACTED")):
            rule = "retracted"
        elif dblp.get(r["id"]):
            rule = "dblp"
        elif o.get("oa_is_core"):
            rule = "indexed"
        elif r["arxiv_id"] or "arxiv" in r["venue"].lower():
            rule = "arxiv"
        else:
            rule = "unindexed"
        rows.append({"id": r["id"], "venue": r["venue"], "type": r["type_norm"], "oa_source": o.get("oa_source", ""),
                     "oa_source_type": o.get("oa_source_type", ""), "oa_is_core": o.get("oa_is_core", ""),
                     "dblp_key": dblp.get(r["id"], ""), "venue_rule": rule,
                     "venue_ok": rule in ("dblp", "indexed", "arxiv")})
    # venue-level pass: a venue confirmed by any of its papers confirms the rest (never for repositories)
    good = {venue_key(r) for r in rows if r["venue_rule"] in ("dblp", "indexed")}
    for r in rows:
        k = venue_key(r)
        if r["venue_rule"] == "unindexed" and k and k in good and r["oa_source_type"] != "repository":
            r["venue_rule"], r["venue_ok"] = "venue", True
    with open(SEARCH / "venue_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(Counter(r["venue_rule"] for r in rows))


if __name__ == "__main__":
    main()
