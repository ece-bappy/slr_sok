"""Apply the user's adjudication of second-coder disagreements to the verified coding.

Input:  todo/second_coder_disagreements.csv (adjudicated_value, who_was_right, note)
Target: review/coding/core_67_papers_verification.csv (verified_value = coder 1)

Rule: for single-choice and list fields, verified_value becomes adjudicated_value whenever
the adjudicated answer differs from coder 1 (who_was_right = coder2/neither, or "both" with a
changed set). Free-text fields change only when who_was_right = coder2/neither (a real content
difference); "both" and "coder1" free-text rows only reword the same content, so coder 1 stays.
Every change is logged in review/coding/adjudication_changes.csv. Kappa is not recomputed:
it is reported before adjudication.
"""
import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADJ = ROOT / "todo" / "second_coder_disagreements.csv"
VER = ROOT / "review" / "coding" / "core_67_papers_verification.csv"
LOG = ROOT / "review" / "coding" / "adjudication_changes.csv"
FINAL = ROOT / "review" / "coding" / "second_coder_disagreements.csv"
SPLITS = "random|stratified_random|per_packet|host_grouped|temporal|cross_dataset|not_applicable|unclear"


def read(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        return list(rd), rd.fieldnames


def norm_list(v):
    items = [t.strip().lower() for t in v.replace(",", ";").split(";") if t.strip()]
    return "; ".join(items)


def main():
    adj, _ = read(ADJ)
    ver, vf = read(VER)
    idx = {(r["paper_id"], r["field"]): r for r in ver}
    changes = []
    for a in adj:
        who = a["who_was_right"].strip()
        kind = a["kind"].strip()
        new = a["adjudicated_value"].strip()
        key = (a["paper_id"], a["field"])
        if key not in idx:
            raise SystemExit(f"not in verification sheet: {key}")
        row = idx[key]
        old = row["verified_value"]
        av = row["allowed_values"].replace(" (list)", "")
        if a["field"] in {"main_split", "split_protocols"}:  # save_result.py allows "unclear" for both
            av = SPLITS
        canon = {t.strip().lower(): t.strip() for t in av.split("|")} if "|" in av else None
        if kind in {"list", "single"}:
            items = norm_list(new).split("; ")
            if canon:
                bad = [t for t in items if t not in canon]
                if bad:
                    raise SystemExit(f"{key}: {bad} not in allowed {sorted(canon.values())}")
                items = [canon[t] for t in items]
            if kind == "single" and len(items) != 1:
                raise SystemExit(f"{key}: single field got {items}")
            new = "; ".join(items)
            change = sorted(norm_list(old).split("; ")) != sorted(norm_list(new).split("; "))
        else:  # free_text
            change = who in {"coder2", "neither"}
        if not change:
            continue
        row["verified_value"] = new
        note = f"adjudicated 8 Nov 2026 ({who}): {a['note'].strip()}"
        row["recheck_note"] = (row.get("recheck_note", "").strip() + " | " + note).strip(" |")
        changes.append({"paper_id": key[0], "field": key[1], "kind": kind, "who_was_right": who,
                        "old_verified": old, "new_verified": new, "note": a["note"].strip()})

    with open(VER, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=vf)
        w.writeheader()
        w.writerows(ver)
    with open(LOG, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(changes[0].keys()))
        w.writeheader()
        w.writerows(changes)
    shutil.copyfile(ADJ, FINAL)
    print(f"{len(changes)} verified values changed; log -> {LOG.relative_to(ROOT)}")
    for c in changes:
        print(f"  {c['paper_id']} {c['field']}: {c['old_verified'][:50]!r} -> {c['new_verified'][:60]!r}")


if __name__ == "__main__":
    main()
