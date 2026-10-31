"""Map dataset names as written in papers to canonical registry entries (review/dataset_registry.json).

canonical(name) -> registry entry dict, or {"name": name, "public": "unknown", "status": "not_in_registry"}.
Unknown names are collected so the registry can be extended by hand; they are never guessed.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent.parent / "review" / "dataset_registry.json"


@lru_cache(maxsize=1)
def _entries() -> list[dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))["datasets"]
    for d in data:
        d["_rx"] = [re.compile(a, re.I) for a in d["aliases"]]
    return data


def canonical(name: str) -> dict:
    for d in _entries():  # registry order: specific names before the catch-all "own / private" entry
        if any(rx.search(name) for rx in d["_rx"]):
            return {k: v for k, v in d.items() if not k.startswith("_")}
    return {"name": name, "public": "unknown", "tls": "", "status": "not_in_registry"}
