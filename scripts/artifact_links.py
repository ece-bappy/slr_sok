"""Find a paper's code/data links deterministically (plan.md §4, extraction input rule 1).

find_links(paper) scans the whole cleaned PDF text, references included, for repository and download
URLs, and resolves body sentences such as "our code is available at [47]" to reference entry 47.
Each link comes with the context the LLM needs to classify it (own code / own data / third party):
the surrounding text, and for a resolved citation the citing sentence plus the reference entry.
Also returns "upon request" / "will be released" statements, which do not count as released.
"""
import re

from pdf_prep import Paper

URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'()\]}⟩〉]+|(?<![\w/.])(?:github\.com|gitlab\.com|zenodo\.org|"
                 r"figshare\.com|osf\.io|kaggle\.com|huggingface\.co|bitbucket\.org)/[^\s<>\"'()\]}⟩〉]+|"
                 r"(?:doi:\s*|(?<![\w/.])doi\.org/)(10\.\d{4,9}/[^\s<>\"'()\]}⟩〉]+)", re.I)
# PDF line breaks split long URLs: "https://github.com/ Carlos/repo" -> join the continuation
BROKEN_URL = re.compile(r"((?:https?://|www\.)[^\s<>\"'()⟩〉]*[/\-_])\s+([A-Za-z0-9][\w\-./#?=%~]*)")
ARTIFACT_WORDS = r"(code|source|implementation|tool|prototype|script|dataset|data\s?set|data|captures?|pcaps?|" \
                 r"artifacts?|artefacts?|features|labels|model)"
AVAILABLE_WORDS = r"(available|released?|publish|open[- ]sourc|share[ds]?|provided?|download|repository|online)"
CITE = re.compile(r"\[(\d{1,3}(?:\s*[,–-]\s*\d{1,3})*)\]")
NOT_RELEASED = re.compile(r"(upon|on)\s+(reasonable\s+)?request|will\s+be\s+(made\s+)?(publicly\s+)?(available|released)|"
                          r"available\s+(from\s+the\s+authors?|on\s+demand)", re.I)
SKIP_HOSTS = ("doi.org", "dx.doi.org", "creativecommons.org", "orcid.org", "crossmark", "ieeexplore", "dl.acm.org",
              "sciencedirect", "springer.com", "elsevier", "wiley.com", "mdpi.com", "arxiv.org/abs", "acm.org/doi",
              "usenix.org/conference", "ndss-symposium.org/ndss-paper", "w3.org", "ietf.org/rfc", "rfc-editor")
DATA_REPOS = ("zenodo", "10.5281", "figshare", "10.6084", "mendeley", "10.17632", "osf.io", "10.17605", "dataverse")


def _should_skip(url: str) -> bool:
    low = url.lower()
    if any(repo in low for repo in DATA_REPOS):
        return False
    return any(h in low for h in SKIP_HOSTS)


def _cite_numbers(s: str) -> list[int]:
    out = []
    for part in re.split(r"\s*,\s*", s):
        m = re.match(r"(\d+)\s*[–-]\s*(\d+)", part)
        out += list(range(int(m.group(1)), int(m.group(2)) + 1)) if m else [int(part)]
    return out


def _tidy(url: str) -> str:
    url = url.rstrip(".,;:")
    if re.match(r"^10\.\d{4,9}/", url):
        return "https://doi.org/" + url
    m = re.match(r"^doi:\s*(10\.\d{4,9}/\S+)", url, re.I)
    if m:
        return "https://doi.org/" + m.group(1).rstrip(".,;:")
    return url if url.lower().startswith("http") else "https://" + url


BROKEN_DOMAIN = re.compile(r"((?:https?://|www\.)[^\s<>\"'()⟩〉]*\.)\s+((?:com|org|io|net|edu|co|ai)\b[\w\-./#?=%~]*)")


def _join_urls(s: str) -> str:
    for _ in range(3):
        s = BROKEN_DOMAIN.sub(r"\1\2", BROKEN_URL.sub(r"\1\2", s))
    return s


def find_links(p: Paper) -> dict:
    links = {}
    full = _join_urls(p.full.replace("\n", " "))
    p.refs = {n: _join_urls(e) for n, e in p.refs.items()}
    ref_start = max((m.end() for m in re.finditer(r"\s(references|bibliography)\s", full, re.I)), default=len(full))
    # 1. URLs anywhere (body, footnotes, availability statements, appendices); references handled in 2
    for m in URL.finditer(full[:ref_start]):
        url = _tidy(m.group(0))
        if _should_skip(url):
            continue
        ctx = full[max(0, m.start() - 300) : m.end() + 150]
        links.setdefault(url, {"url": url, "found_in": "text", "context": ctx})
    # 2. body sentences that point to a numbered reference for code/data
    sentences = re.split(r"(?<=[.!?])\s+", full[:ref_start])
    pat = re.compile(rf"{ARTIFACT_WORDS}.{{0,120}}{AVAILABLE_WORDS}|{AVAILABLE_WORDS}.{{0,120}}{ARTIFACT_WORDS}", re.I)
    for s in sentences:
        if not pat.search(s):
            continue
        for c in CITE.finditer(s):
            for n in _cite_numbers(c.group(1)):
                entry = p.refs.get(n, "")
                for m in URL.finditer(entry):
                    url = _tidy(m.group(0))
                    if _should_skip(url):
                        continue
                    links.setdefault(url, {"url": url, "found_in": f"reference [{n}]",
                                           "context": f"CITING SENTENCE: {s.strip()} || REFERENCE [{n}]: {entry}"})
    # 3. repository URLs inside other reference entries (often third-party datasets or tools)
    for n, entry in p.refs.items():
        for m in URL.finditer(entry):
            url = _tidy(m.group(0))
            if url in links or _should_skip(url):
                continue
            if re.search(r"github|gitlab|zenodo|figshare|osf\.io|kaggle|huggingface|bitbucket|10\.5281|10\.17632|10\.6084|10\.17605|mendeley", url, re.I):
                links[url] = {"url": url, "found_in": f"reference [{n}] (not cited as code/data)",
                              "context": f"REFERENCE [{n}]: {entry}"}
    statements = sorted({s.strip()[:300] for s in sentences
                         if NOT_RELEASED.search(s) and re.search(ARTIFACT_WORDS, s, re.I)})
    return {"links": list(links.values()), "not_released_statements": statements}


if __name__ == "__main__":
    import json
    import sys

    from pdf_prep import prepare

    for f in sys.argv[1:]:
        r = find_links(prepare(f))
        print(f"== {f}: {len(r['links'])} links")
        for x in r["links"]:
            print("  ", x["found_in"], "|", x["url"])
        for s in r["not_released_statements"]:
            print("   NOT RELEASED:", s[:150])
