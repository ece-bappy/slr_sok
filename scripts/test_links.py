"""Run only the link scan + link classification of extract_v2 on some PDFs and print the result.

Usage: python scripts/test_links.py PAPER.pdf [PAPER.pdf ...]
"""
import sys

from artifact_links import find_links
from extract_v2 import classify_links, derive
from pdf_prep import prepare

for f in sys.argv[1:]:
    p = prepare(f)
    links = find_links(p)
    got = classify_links("gemini-3.1-flash-lite", "high", p, links)
    same = {l["url"]: l.get("same_authors") for l in links["links"]}
    d = derive({}, {"classified": got})
    print(f"== {f}: code_released={d['code_released']['value']} data_released={d['data_released']['value']}")
    for g in got:
        print(f"   {g['kind']:20} {g['url'][:70]}  same_authors={same.get(g['url'])}")
