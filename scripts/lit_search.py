#!/usr/bin/env python3
"""
scripts/lit_search.py
Harvests literature search results from OpenAlex, arXiv, and Semantic Scholar APIs for systematic review.
Standard library only (Python 3.11+).
"""

import argparse
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Search concept: 4 AND-groups of OR-terms
SEARCH_GROUPS = [
    ["TLS", "HTTPS", "SSL", "encrypted traffic"],
    ["malicious", "malware", "command and control", "C2", "botnet", "intrusion", "attack"],
    ["machine learning", "deep learning", "classifier", "fingerprint", "JA3", "JA4"],
    # v2 (2026-10-26): + detect/identify/identification; v1 missed abstracts saying "detect ..."
    ["detection", "classification", "detect", "identify", "identification"],
]


class QueryTimeoutError(Exception):
    """Raised when an API query times out with HTTP 504 query_timeout."""
    pass


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


def clean_doi(doi: str | None) -> str:
    """Normalize DOI by stripping URL prefix and converting to lowercase."""
    if not doi:
        return ""
    val = doi.strip()
    val = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", val, flags=re.IGNORECASE)
    return val.strip().lower()


def extract_arxiv_id(text: str | None) -> str:
    """Extract clean arXiv ID without version from URL, text, or DOI."""
    if not text:
        return ""
    val = text.strip()
    m = re.search(
        r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:|\barxiv\.)([a-zA-Z\-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?",
        val,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    m2 = re.search(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b", val)
    if m2:
        return m2.group(1)
    if "/abs/" in val:
        tail = val.split("/abs/")[-1]
        return re.sub(r"v\d+$", "", tail).strip()
    tail = val.split("/")[-1]
    return re.sub(r"v\d+$", "", tail).strip()


def sanitize_secrets(text: str) -> str:
    """Remove sensitive API keys from URL or error strings."""
    if not text:
        return ""
    text = re.sub(r"([?&])api_key=[^&]*(&|$)", r"\1", text)
    return re.sub(r"[?&](\s|$)", r"\1", text).strip()


def check_query_timeout(err: urllib.error.HTTPError) -> bool:
    """Check if an HTTPError represents a 504 query_timeout."""
    if err.code != 504:
        return False
    reason = str(getattr(err, "reason", "") or "").lower()
    if "query_timeout" in reason:
        return True
    try:
        if hasattr(err, "fp") and err.fp is not None:
            body = err.read()
            err.fp = io.BytesIO(body)
            if b"query_timeout" in body.lower():
                return True
    except Exception:
        pass
    return False


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Rebuild text from OpenAlex abstract_inverted_index."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    pos_words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        if isinstance(positions, list):
            for pos in positions:
                pos_words.append((pos, word))
    pos_words.sort(key=lambda x: x[0])
    return " ".join(w for _, w in pos_words)


def fetch_url(
    url: str,
    headers: dict[str, str] | None = None,
    max_retries: int = 3,
    backoff: float = 1.0,
) -> bytes:
    """Fetch URL with retries on HTTP 429 and 5xx."""
    req_headers = {"User-Agent": "LitSearchBot/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if check_query_timeout(e):
                raise QueryTimeoutError(f"HTTP 504 query_timeout: {e.reason}") from e
            if (e.code == 429 or 500 <= e.code < 600) and attempt < max_retries:
                wait_sec = backoff * (2**attempt)
                time.sleep(wait_sec)
                continue
            raise
        except urllib.error.URLError:
            if attempt < max_retries:
                wait_sec = backoff * (2**attempt)
                time.sleep(wait_sec)
                continue
            raise
    safe_url = sanitize_secrets(url)
    raise RuntimeError(f"Failed to fetch {safe_url} after {max_retries} retries")


def build_openalex_filter() -> str:
    """Construct OpenAlex filter string for title_and_abstract and year range."""
    clauses = []
    for grp in SEARCH_GROUPS:
        terms = [f'"{t}"' if " " in t else t for t in grp]
        clauses.append(f"({' OR '.join(terms)})")
    bool_query = " AND ".join(clauses)
    return f"title_and_abstract.search:{bool_query},publication_year:2019-2026"


def fetch_openalex_page(url: str) -> tuple[dict | None, str | None]:
    """Fetch a single OpenAlex page, retrying up to 3 times on 504 query_timeout with 10 s backoff."""
    for timeout_attempt in range(4):
        try:
            raw = fetch_url(url)
            return json.loads(raw.decode("utf-8")), None
        except QueryTimeoutError:
            if timeout_attempt < 3:
                print(
                    f"[OpenAlex] HTTP 504 query_timeout. Retrying in 10 s "
                    f"(attempt {timeout_attempt + 1}/3)..."
                )
                time.sleep(10)
                continue
            else:
                msg = "HTTP 504 query_timeout after 3 retries"
                print(f"[OpenAlex] Stopped early: {msg}.")
                return None, msg
        except Exception as e:
            safe_err = sanitize_secrets(str(e))
            msg = f"Request error: {safe_err}"
            print(f"[OpenAlex] {msg}")
            return None, msg
    return None, "HTTP 504 query_timeout after 3 retries"


def fetch_openalex(
    max_records: int = 5000,
    api_key: str = "",
) -> tuple[list[dict], int, str, str | None]:
    """Harvest records from OpenAlex API using cursor pagination."""
    filter_val = build_openalex_filter()
    encoded_filter = urllib.parse.quote(filter_val)
    base_url = "https://api.openalex.org/works"
    select_fields = (
        "id,doi,title,publication_year,type,primary_location,authorships,"
        "abstract_inverted_index,cited_by_count,open_access,best_oa_location,ids"
    )
    query_sent = f"{base_url}?filter={filter_val}&select={select_fields}&per-page=200&cursor=*"

    if not api_key or not api_key.strip():
        print("[OpenAlex] WARNING: No API key provided (--openalex-key or OPENALEX_API_KEY). Skipping OpenAlex.")
        return [], 0, query_sent, "Skipped: No API key provided"

    clean_key = api_key.strip()
    encoded_key = urllib.parse.quote(clean_key)
    records: list[dict] = []
    total_hits = 0
    error_msg: str | None = None

    probe_url = f"{base_url}?filter={encoded_filter}&per-page=1&api_key={encoded_key}"
    data, err = fetch_openalex_page(probe_url)
    if err:
        return records, total_hits, query_sent, err
    if data:
        total_hits = data.get("meta", {}).get("count", 0)
    print(f"[OpenAlex] Total hits reported: {total_hits}")

    cursor = "*"
    while cursor and len(records) < max_records:
        page_size = min(200, max_records - len(records))
        page_url = (
            f"{base_url}?filter={encoded_filter}&select={select_fields}"
            f"&per-page={page_size}&cursor={urllib.parse.quote(cursor)}"
            f"&api_key={encoded_key}"
        )
        page_data, err = fetch_openalex_page(page_url)
        if err:
            error_msg = err
            break
        if not page_data:
            break

        results = page_data.get("results", [])
        if not results:
            break

        for item in results:
            venue = ""
            prim_loc = item.get("primary_location")
            if isinstance(prim_loc, dict):
                src = prim_loc.get("source")
                if isinstance(src, dict):
                    venue = src.get("display_name") or ""

            authors_list: list[str] = []
            for a in item.get("authorships") or []:
                if isinstance(a, dict):
                    auth_obj = a.get("author")
                    name = auth_obj.get("display_name") if isinstance(auth_obj, dict) else ""
                    if not name:
                        name = a.get("raw_author_name") or ""
                    if name:
                        authors_list.append(name.strip())
            if len(authors_list) > 6:
                authors_str = "; ".join(authors_list[:6]) + " et al."
            else:
                authors_str = "; ".join(authors_list)

            oa_url = ""
            best_oa = item.get("best_oa_location")
            if isinstance(best_oa, dict):
                oa_url = best_oa.get("pdf_url") or best_oa.get("landing_page_url") or ""

            raw_doi = item.get("doi") or ""
            doi = clean_doi(raw_doi)

            ids_obj = item.get("ids") or {}
            arxiv_id = ""
            if isinstance(ids_obj, dict) and ids_obj.get("arxiv"):
                arxiv_id = extract_arxiv_id(ids_obj["arxiv"])
            if not arxiv_id and "arxiv" in raw_doi.lower():
                arxiv_id = extract_arxiv_id(raw_doi)
            if not arxiv_id and oa_url and "arxiv.org" in oa_url.lower():
                arxiv_id = extract_arxiv_id(oa_url)

            openalex_id = item.get("id") or (ids_obj.get("openalex") if isinstance(ids_obj, dict) else "") or ""
            abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
            title = re.sub(r"\s+", " ", item.get("title") or "").strip()

            records.append({
                "openalex_id": openalex_id,
                "arxiv_id": arxiv_id,
                "doi": doi,
                "title": title,
                "authors": authors_str,
                "year": str(item.get("publication_year") or ""),
                "venue": venue,
                "type": item.get("type") or "",
                "cited_by": item.get("cited_by_count", 0),
                "oa_url": oa_url,
                "abstract": abstract,
                "source": "openalex",
            })
            if len(records) >= max_records:
                break

        next_cursor = page_data.get("meta", {}).get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.2)

    print(f"[OpenAlex] Retrieved {len(records)} records.")
    return records, total_hits, query_sent, error_msg


def build_arxiv_query() -> str:
    """Construct arXiv API search_query with abs: prefix and date window."""
    clauses = []
    for grp in SEARCH_GROUPS:
        terms = [f'abs:"{t}"' for t in grp]
        clauses.append(f"({' OR '.join(terms)})")
    date_clause = "submittedDate:[201901010000 TO 202612312359]"
    return f"{' AND '.join(clauses)} AND {date_clause}"


def fetch_arxiv(max_records: int = 5000) -> tuple[list[dict], int, str, str | None]:
    """Harvest records from arXiv API using Atom XML paging."""
    query_str = build_arxiv_query()
    base_url = "http://export.arxiv.org/api/query"
    records: list[dict] = []
    start = 0
    total_hits = 0
    query_sent = f"{base_url}?search_query={query_str}&max_results=200"
    error_msg: str | None = None

    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    first_page = True
    while len(records) < max_records:
        page_size = min(200, max_records - len(records))
        params = {
            "search_query": query_str,
            "start": str(start),
            "max_results": str(page_size),
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        try:
            raw_xml = fetch_url(url)
            root = ET.fromstring(raw_xml)
        except Exception as e:
            error_msg = f"Request error at start={start}: {e}"
            print(f"[arXiv] {error_msg}")
            break

        if first_page:
            tot_el = root.find("opensearch:totalResults", namespaces)
            if tot_el is not None and tot_el.text:
                try:
                    total_hits = int(tot_el.text.strip())
                except ValueError:
                    total_hits = 0
            print(f"[arXiv] Total hits reported: {total_hits}")
            first_page = False

        entries = root.findall("atom:entry", namespaces)
        if not entries:
            break

        for entry in entries:
            raw_id = entry.findtext("atom:id", default="", namespaces=namespaces).strip()
            arxiv_id = extract_arxiv_id(raw_id)

            title_raw = entry.findtext("atom:title", default="", namespaces=namespaces)
            title = re.sub(r"\s+", " ", title_raw).strip()

            summary_raw = entry.findtext("atom:summary", default="", namespaces=namespaces)
            abstract = re.sub(r"\s+", " ", summary_raw).strip()

            pub_raw = entry.findtext("atom:published", default="", namespaces=namespaces).strip()
            year = pub_raw[:4] if len(pub_raw) >= 4 else ""

            author_names: list[str] = []
            for auth in entry.findall("atom:author", namespaces=namespaces):
                name = auth.findtext("atom:name", default="", namespaces=namespaces).strip()
                if name:
                    author_names.append(name)
            if len(author_names) > 6:
                authors_str = "; ".join(author_names[:6]) + " et al."
            else:
                authors_str = "; ".join(author_names)

            doi = clean_doi(entry.findtext("arxiv:doi", default="", namespaces=namespaces))
            pdf_url = ""
            for link in entry.findall("atom:link", namespaces=namespaces):
                title_attr = link.attrib.get("title", "")
                mime = link.attrib.get("type", "")
                href = link.attrib.get("href", "")
                if title_attr == "doi" and not doi:
                    doi = clean_doi(href)
                if title_attr == "pdf" or mime == "application/pdf":
                    pdf_url = href.strip()

            if not pdf_url and arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            prim_cat = ""
            cat_el = entry.find("arxiv:primary_category", namespaces=namespaces)
            if cat_el is not None:
                prim_cat = cat_el.attrib.get("term", "")
            if not prim_cat:
                cat_el = entry.find("atom:category", namespaces=namespaces)
                if cat_el is not None:
                    prim_cat = cat_el.attrib.get("term", "")

            journal_ref = entry.findtext("arxiv:journal_ref", default="", namespaces=namespaces).strip()
            venue = journal_ref if journal_ref else "arXiv"

            records.append({
                "arxiv_id": arxiv_id,
                "openalex_id": "",
                "doi": doi,
                "title": title,
                "authors": authors_str,
                "year": year,
                "venue": venue,
                "type": "preprint",
                "cited_by": 0,
                "oa_url": pdf_url,
                "abstract": abstract,
                "primary_category": prim_cat,
                "source": "arxiv",
            })
            if len(records) >= max_records:
                break

        start += len(entries)
        if total_hits > 0 and start >= total_hits:
            break
        time.sleep(3.5)

    print(f"[arXiv] Retrieved {len(records)} records.")
    return records, total_hits, query_sent, error_msg


def build_semanticscholar_query() -> str:
    """Construct Semantic Scholar bulk search boolean query from SEARCH_GROUPS."""
    clauses = []
    for grp in SEARCH_GROUPS:
        terms = [f'"{t}"' for t in grp]
        clauses.append(f"({' | '.join(terms)})")
    return " + ".join(clauses)


def fetch_s2_page(url: str, headers: dict[str, str]) -> tuple[dict | None, str | None]:
    """Fetch Semantic Scholar page with 429 backoff (the shared keyless pool is often saturated)."""
    backoffs = [10, 30, 60, 120, 240, 300, 300]
    backoff_idx = 0
    req = urllib.request.Request(url, headers=headers)
    while True:
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if backoff_idx < len(backoffs):
                    wait_sec = backoffs[backoff_idx]
                    print(
                        f"[SemanticScholar] HTTP 429 Too Many Requests. "
                        f"Backing off {wait_sec} s (attempt {backoff_idx + 1}/{len(backoffs)})..."
                    )
                    time.sleep(wait_sec)
                    backoff_idx += 1
                    continue
                else:
                    msg = f"HTTP 429 rate limit exceeded after backoff retries {backoffs} s"
                    print(f"[SemanticScholar] Stopped early: {msg}.")
                    return None, msg
            elif 500 <= e.code < 600 and backoff_idx < 3:
                time.sleep(2.0 * (2**backoff_idx))
                backoff_idx += 1
                continue
            else:
                msg = f"HTTP {e.code}: {e.reason}"
                print(f"[SemanticScholar] Request error: {msg}")
                return None, msg
        except urllib.error.URLError as e:
            if backoff_idx < 3:
                time.sleep(2.0 * (2**backoff_idx))
                backoff_idx += 1
                continue
            msg = f"URLError: {e}"
            print(f"[SemanticScholar] Request error: {msg}")
            return None, msg
        except Exception as e:
            msg = f"Request error: {e}"
            print(f"[SemanticScholar] Request error: {msg}")
            return None, msg


def fetch_semanticscholar(
    max_records: int = 5000,
    s2_key: str = "",
) -> tuple[list[dict], int, str, str | None]:
    """Harvest records from Semantic Scholar bulk search API."""
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    query_str = build_semanticscholar_query()
    fields_str = (
        "title,abstract,year,venue,publicationVenue,externalIds,authors,"
        "citationCount,openAccessPdf,publicationTypes,url"
    )
    headers = {"User-Agent": "LitSearchBot/1.0"}
    if s2_key and s2_key.strip():
        headers["x-api-key"] = s2_key.strip()

    query_sent = f"{base_url}?query={query_str}&year=2019-2026&fields={fields_str}"
    records: list[dict] = []
    token: str | None = None
    total_hits = 0
    first_request = True
    error_msg: str | None = None

    while len(records) < max_records:
        params: dict[str, str] = {
            "query": query_str,
            "year": "2019-2026",
            "fields": fields_str,
        }
        if token:
            params["token"] = token

        url = f"{base_url}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
        data, err = fetch_s2_page(url, headers)
        if err:
            error_msg = err
            break
        if not data:
            break

        if first_request:
            try:
                total_hits = int(data.get("total") or 0)
            except (ValueError, TypeError):
                total_hits = 0
            print(f"[SemanticScholar] Total hits reported: {total_hits}")
            first_request = False

        items = data.get("data") or []
        if not items:
            break

        for item in items:
            s2_id = str(item.get("paperId") or "").strip()

            ext_ids = item.get("externalIds") or {}
            raw_doi = ext_ids.get("DOI") if isinstance(ext_ids, dict) else ""
            doi = clean_doi(raw_doi)

            arxiv_raw = ext_ids.get("ArXiv") if isinstance(ext_ids, dict) else ""
            arxiv_id = extract_arxiv_id(arxiv_raw)
            if not arxiv_id and raw_doi and "arxiv" in raw_doi.lower():
                arxiv_id = extract_arxiv_id(raw_doi)
            url_val = item.get("url") or ""
            if not arxiv_id and url_val and "arxiv.org" in url_val.lower():
                arxiv_id = extract_arxiv_id(url_val)

            venue = item.get("venue") or ""
            if not venue:
                pub_venue = item.get("publicationVenue")
                if isinstance(pub_venue, dict):
                    venue = pub_venue.get("name") or ""
            venue = str(venue).strip()

            pub_types = item.get("publicationTypes") or []
            if isinstance(pub_types, list):
                rec_type = ";".join(str(pt).strip() for pt in pub_types if pt)
            elif pub_types:
                rec_type = str(pub_types).strip()
            else:
                rec_type = ""

            authors_list: list[str] = []
            for a in item.get("authors") or []:
                if isinstance(a, dict):
                    name = a.get("name") or ""
                    if name:
                        authors_list.append(name.strip())
                elif isinstance(a, str) and a.strip():
                    authors_list.append(a.strip())
            if len(authors_list) > 6:
                authors_str = "; ".join(authors_list[:6]) + " et al."
            else:
                authors_str = "; ".join(authors_list)

            citation_count = item.get("citationCount")
            try:
                cited_by = int(citation_count) if citation_count is not None else 0
            except (ValueError, TypeError):
                cited_by = 0

            oa_pdf = item.get("openAccessPdf")
            oa_url = ""
            if isinstance(oa_pdf, dict):
                oa_url = (oa_pdf.get("url") or "").strip()

            abstract = re.sub(r"\s+", " ", item.get("abstract") or "").strip()
            title = re.sub(r"\s+", " ", item.get("title") or "").strip()
            year = str(item.get("year") or "").strip()

            records.append({
                "s2_id": s2_id,
                "doi": doi,
                "arxiv_id": arxiv_id,
                "openalex_id": "",
                "title": title,
                "authors": authors_str,
                "year": year,
                "venue": venue,
                "type": rec_type,
                "cited_by": cited_by,
                "oa_url": oa_url,
                "abstract": abstract,
                "source": "semanticscholar",
            })
            if len(records) >= max_records:
                break

        token = data.get("token")
        if not token or len(records) >= max_records:
            break

        time.sleep(1.1)

    print(f"[SemanticScholar] Retrieved {len(records)} records.")
    return records, total_hits, query_sent, error_msg


def normalize_title(title: str) -> str:
    """Normalize title to lowercase non-alphanumeric characters."""
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def merge_records(
    openalex_records: list[dict],
    arxiv_records: list[dict],
    s2_records: list[dict] | None = None,
) -> list[dict]:
    """Union and deduplicate records on DOI, arXiv ID, or normalized title."""
    combined = list(openalex_records) + list(arxiv_records) + list(s2_records or [])
    if not combined:
        return []

    parent = list(range(len(combined)))

    def find(i: int) -> int:
        path = []
        while parent[i] != i:
            path.append(i)
            i = parent[i]
        for p in path:
            parent[p] = i
        return i

    def union(i: int, j: int) -> None:
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    doi_map: dict[str, int] = {}
    arxiv_map: dict[str, int] = {}
    title_map: dict[str, int] = {}

    for idx, rec in enumerate(combined):
        d = clean_doi(rec.get("doi"))
        if d:
            if d in doi_map:
                union(idx, doi_map[d])
            else:
                doi_map[d] = idx

        arx = (rec.get("arxiv_id") or "").lower().strip()
        if arx:
            if arx in arxiv_map:
                union(idx, arxiv_map[arx])
            else:
                arxiv_map[arx] = idx

        nt = normalize_title(rec.get("title") or "")
        if len(nt) >= 5:
            if nt in title_map:
                union(idx, title_map[nt])
            else:
                title_map[nt] = idx

    groups: dict[int, list[dict]] = {}
    for idx, rec in enumerate(combined):
        root = find(idx)
        groups.setdefault(root, []).append(rec)

    def peer_score(r: dict) -> int:
        src = r.get("source", "")
        t = (r.get("type") or "").lower()
        v = (r.get("venue") or "").lower()
        if src in ("openalex", "semanticscholar"):
            if "preprint" not in t and "posted-content" not in t and "arxiv" not in v and v:
                return 3
            if v and "arxiv" not in v:
                return 2
            return 1
        return 0

    merged_list: list[dict] = []
    for grp in groups.values():
        grp.sort(key=peer_score, reverse=True)
        primary = grp[0]

        venue = primary.get("venue") or ""
        doi = primary.get("doi") or ""
        rec_type = primary.get("type") or ""

        if not venue:
            for g in grp[1:]:
                if g.get("venue"):
                    venue = g["venue"]
                    break
        if not doi:
            for g in grp[1:]:
                if g.get("doi"):
                    doi = g["doi"]
                    break
        if not rec_type:
            for g in grp[1:]:
                if g.get("type"):
                    rec_type = g["type"]
                    break

        title = primary.get("title") or ""
        if not title:
            for g in grp[1:]:
                if g.get("title"):
                    title = g["title"]
                    break

        authors = primary.get("authors") or ""
        if not authors:
            for g in grp[1:]:
                if g.get("authors"):
                    authors = g["authors"]
                    break

        year = primary.get("year") or ""
        if not year:
            for g in grp[1:]:
                if g.get("year"):
                    year = g["year"]
                    break

        abstract = primary.get("abstract") or ""
        if not abstract:
            for g in grp[1:]:
                if g.get("abstract"):
                    abstract = g["abstract"]
                    break

        oa_url = primary.get("oa_url") or ""
        if not oa_url:
            for g in grp[1:]:
                if g.get("oa_url"):
                    oa_url = g["oa_url"]
                    break

        arxiv_id = ""
        for g in grp:
            if g.get("arxiv_id"):
                arxiv_id = g["arxiv_id"]
                break

        openalex_id = ""
        for g in grp:
            if g.get("openalex_id"):
                openalex_id = g["openalex_id"]
                break

        s2_id = ""
        for g in grp:
            if g.get("s2_id"):
                s2_id = g["s2_id"]
                break

        max_cited = 0
        for g in grp:
            try:
                c = int(g.get("cited_by") or 0)
                if c > max_cited:
                    max_cited = c
            except (ValueError, TypeError):
                pass

        source_order = {"openalex": 0, "arxiv": 1, "semanticscholar": 2}
        unique_sources = sorted(
            list({g.get("source") for g in grp if g.get("source")}),
            key=lambda s: source_order.get(s, 99),
        )
        sources_str = ";".join(unique_sources)

        merged_list.append({
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "type": rec_type,
            "doi": doi,
            "arxiv_id": arxiv_id,
            "openalex_id": openalex_id,
            "s2_id": s2_id,
            "cited_by": max_cited,
            "oa_url": oa_url,
            "abstract": abstract,
            "sources": sources_str,
        })

    def sort_order(r: dict) -> tuple[int, str]:
        y_str = r.get("year") or ""
        try:
            y = int(y_str)
        except ValueError:
            y = 0
        return (-y, (r.get("title") or "").lower())

    merged_list.sort(key=sort_order)
    for idx, r in enumerate(merged_list, start=1):
        r["id"] = f"S{idx:04d}"

    return merged_list


def write_csv(filepath: Path | str, fieldnames: list[str], records: list[dict]) -> None:
    """Write list of dictionaries to CSV with UTF-8 encoding."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def main() -> None:
    """Parse CLI options, harvest literature from sources, and write results."""
    parser = argparse.ArgumentParser(
        description="Harvest literature search results from OpenAlex, arXiv, and Semantic Scholar."
    )
    parser.add_argument(
        "--out",
        default="review/search",
        help="Output directory (default: review/search)",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=5000,
        help="Max records per source (default: 5000)",
    )
    parser.add_argument(
        "--sources",
        default="openalex,arxiv,semanticscholar",
        help="Comma-separated sources: openalex,arxiv,semanticscholar (default: openalex,arxiv,semanticscholar)",
    )
    parser.add_argument(
        "--openalex-key",
        default=user_env("OPENALEX_API_KEY"),
        help="OpenAlex API key (default: env OPENALEX_API_KEY)",
    )
    parser.add_argument(
        "--s2-key",
        default=user_env("S2_API_KEY"),
        help="Semantic Scholar API key (default: env S2_API_KEY)",
    )
    parser.add_argument(
        "--reuse-raw",
        action="store_true",
        help="For sources not in --sources, load <source>_raw.csv and its log entry from --out and include them in the merge",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    prev_log = {}
    if args.reuse_raw and (out_dir / "search_log.json").exists():
        prev_log = json.loads((out_dir / "search_log.json").read_text(encoding="utf-8")).get("sources", {})

    def reuse(name: str) -> tuple[list[dict], int, str, str | None]:
        path = out_dir / f"{name}_raw.csv"
        if not (args.reuse_raw and path.exists()):
            return [], 0, "", None
        with open(path, encoding="utf-8") as f:
            recs = list(csv.DictReader(f))
        p = prev_log.get(name, {})
        print(f"[{name}] reused {len(recs)} records from {path}")
        return recs, p.get("hits_reported", 0), p.get("query", ""), p.get("error_message")

    sources_to_run = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    openalex_records: list[dict] = []
    openalex_hits = 0
    openalex_query = ""
    openalex_error: str | None = None

    arxiv_records: list[dict] = []
    arxiv_hits = 0
    arxiv_query = ""
    arxiv_error: str | None = None

    s2_records: list[dict] = []
    s2_hits = 0
    s2_query = ""
    s2_error: str | None = None

    if "openalex" in sources_to_run:
        openalex_records, openalex_hits, openalex_query, openalex_error = fetch_openalex(
            max_records=args.max_records,
            api_key=args.openalex_key,
        )
        openalex_fields = [
            "openalex_id", "doi", "arxiv_id", "title", "authors", "year",
            "venue", "type", "cited_by", "oa_url", "abstract", "source"
        ]
        write_csv(out_dir / "openalex_raw.csv", openalex_fields, openalex_records)
    else:
        openalex_records, openalex_hits, openalex_query, openalex_error = reuse("openalex")

    if "arxiv" in sources_to_run:
        arxiv_records, arxiv_hits, arxiv_query, arxiv_error = fetch_arxiv(
            max_records=args.max_records
        )
        arxiv_fields = [
            "arxiv_id", "doi", "title", "authors", "year", "venue",
            "type", "cited_by", "oa_url", "abstract", "primary_category", "source"
        ]
        write_csv(out_dir / "arxiv_raw.csv", arxiv_fields, arxiv_records)
    else:
        arxiv_records, arxiv_hits, arxiv_query, arxiv_error = reuse("arxiv")

    if "semanticscholar" in sources_to_run:
        s2_records, s2_hits, s2_query, s2_error = fetch_semanticscholar(
            max_records=args.max_records,
            s2_key=args.s2_key,
        )
        s2_fields = [
            "s2_id", "doi", "arxiv_id", "title", "authors", "year",
            "venue", "type", "cited_by", "oa_url", "abstract", "source"
        ]
        if s2_records or not (out_dir / "semanticscholar_raw.csv").exists():
            write_csv(out_dir / "semanticscholar_raw.csv", s2_fields, s2_records)
        else:
            print("[SemanticScholar] fetch returned nothing; keeping existing semanticscholar_raw.csv out of the merge")
    else:
        s2_records, s2_hits, s2_query, s2_error = reuse("semanticscholar")

    merged = merge_records(openalex_records, arxiv_records, s2_records)
    merged_fields = [
        "id", "title", "authors", "year", "venue", "type",
        "doi", "arxiv_id", "openalex_id", "s2_id", "cited_by", "oa_url", "abstract", "sources"
    ]
    write_csv(out_dir / "merged.csv", merged_fields, merged)

    total_retrieved = len(openalex_records) + len(arxiv_records) + len(s2_records)
    sources_log = {}
    for src_name, hits, recs, err, q in [
        ("openalex", openalex_hits, openalex_records, openalex_error, openalex_query),
        ("arxiv", arxiv_hits, arxiv_records, arxiv_error, arxiv_query),
        ("semanticscholar", s2_hits, s2_records, s2_error, s2_query),
    ]:
        sources_log[src_name] = {
            "hits_reported": hits,
            "records_retrieved": len(recs),
            "error_message": err,
            "error": err,
            "query": q,
        }

    log_data = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources_log,
        "queries": {
            "openalex": openalex_query,
            "arxiv": arxiv_query,
            "semanticscholar": s2_query,
        },
        "hit_counts_reported": {
            "openalex": openalex_hits,
            "arxiv": arxiv_hits,
            "semanticscholar": s2_hits,
        },
        "records_retrieved": {
            "openalex": len(openalex_records),
            "arxiv": len(arxiv_records),
            "semanticscholar": len(s2_records),
            "total": total_retrieved,
        },
        "errors": {
            "openalex": openalex_error,
            "arxiv": arxiv_error,
            "semanticscholar": s2_error,
        },
        "records_after_dedup": len(merged),
    }

    log_path = out_dir / "search_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

    print("\n--- Literature Search Summary ---")
    if "openalex" in sources_to_run:
        msg = f"OpenAlex:        {openalex_hits} hits reported, {len(openalex_records)} retrieved"
        if openalex_error:
            msg += f" ({openalex_error})"
        print(msg)
    if "arxiv" in sources_to_run:
        msg = f"arXiv:           {arxiv_hits} hits reported, {len(arxiv_records)} retrieved"
        if arxiv_error:
            msg += f" ({arxiv_error})"
        print(msg)
    if "semanticscholar" in sources_to_run:
        msg = f"SemanticScholar: {s2_hits} hits reported, {len(s2_records)} retrieved"
        if s2_error:
            msg += f" ({s2_error})"
        print(msg)
    print(f"Merged deduplicated records: {len(merged)}")
    print(f"Output files saved to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
