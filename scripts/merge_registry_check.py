"""Merge the user's registry check (todo/04a, todo/04b) into review/dataset_registry.json.

04a: the 9 entries added by Claude. your_public / your_tls replace the claimed values when
     ok_or_fix = fix (and are copied anyway when ok, since they then equal the claim);
     status -> ok, source_url recorded.
04b: unmapped names as the papers wrote them. Each becomes an anchored, case-insensitive
     alias (^name$), so it cannot match anything else:
       maps_to_registry_name        -> alias on that entry
       or_new_dataset_name = own_capture   -> alias on the "own / private capture" entry
       or_new_dataset_name = not_a_dataset -> alias on a "not a dataset" entry
       any other new name           -> new entry (or alias on an earlier new entry of that name)
New entries go before the catch-all "own / private capture" entry, which must stay last.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "review" / "dataset_registry.json"
A = ROOT / "todo" / "04a_registry_check.csv"
B = ROOT / "todo" / "04b_unmapped_datasets.csv"
OWN = "own / private capture"
NOT_DS = "Not a dataset (no traffic source)"
PUBLIC = {"yes", "on_request", "no", "n/a"}


def read(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def alias(name):
    return "^" + re.escape(name.strip()) + "$"


def main():
    reg = json.loads(REG.read_text(encoding="utf-8"))
    ds = reg["datasets"]
    by_name = {d["name"]: d for d in ds}
    if ds[-1]["name"] != OWN:
        raise SystemExit("catch-all entry is not last")

    for r in read(A):
        d = ds[int(r["index"])]
        if d["name"] != r["name"]:
            raise SystemExit(f"index {r['index']}: {d['name']!r} != {r['name']!r}")
        pub = r["your_public"].strip()
        if pub not in PUBLIC:
            raise SystemExit(f"{r['name']}: public {pub!r}")
        d["public"], d["tls"] = pub, r["your_tls"].strip()
        d["source_url"] = r["source_url"].strip()
        d["status"] = "ok"
        d["checked"] = f"human 8 Nov 2026 ({r['ok_or_fix'].strip()}): {r['note'].strip()}"

    new_entries = []
    for r in read(B):
        name = r["name_as_coded"].strip()
        target = r["maps_to_registry_name"].strip()
        new = r["or_new_dataset_name"].strip()
        if target:
            if target not in by_name:
                raise SystemExit(f"{name}: maps to unknown entry {target!r}")
            by_name[target]["aliases"].append(alias(name))
        elif new == "own_capture":
            by_name[OWN]["aliases"].append(alias(name))
        elif new == "not_a_dataset":
            if NOT_DS not in by_name:
                e = {"name": NOT_DS, "aliases": [], "public": "n/a",
                     "tls": "not a traffic dataset (literature citation, payload strings, or missing value)",
                     "status": "ok"}
                by_name[NOT_DS] = e
                new_entries.append(e)
            by_name[NOT_DS]["aliases"].append(alias(name))
        elif new:
            if new in by_name:
                by_name[new]["aliases"].append(alias(name))
                continue
            pub = r["public"].strip()
            if pub not in PUBLIC:
                raise SystemExit(f"{name}: public {pub!r}")
            e = {"name": new, "aliases": [alias(name)], "public": pub, "tls": r["tls"].strip(),
                 "source_url": r["source_url"].strip(), "status": "ok",
                 "checked": f"human 8 Nov 2026: {r['note'].strip()}"}
            by_name[new] = e
            new_entries.append(e)
        else:
            raise SystemExit(f"{name}: neither mapped nor named")

    reg["datasets"] = ds[:-1] + new_entries + ds[-1:]
    reg["_note"] += (" 8 Nov 2026: the 9 Claude-added entries were checked by the human (todo/04a) and"
                     " 26 unmapped names were mapped or added (todo/04b); anchored ^name$ aliases come"
                     " from that check.")
    REG.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(new_entries)} new entries; {len(reg['datasets'])} total; "
          f"unverified left: {sum(d['status'] not in ('ok', 'rule') for d in reg['datasets'])}")


if __name__ == "__main__":
    main()
