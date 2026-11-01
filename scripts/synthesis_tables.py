"""Synthesis tables for the 67-paper core set (one table per research question), from the verified coding.

Usage: python scripts/synthesis_tables.py
Reads review/coding/core_67_papers_verification.csv (verified_value = final answer), re-applies the computed fields of
plan.md Â§4 (canonical dataset, dataset public, visibility tier, accuracy only) and writes:
  review/synthesis/papers.csv          one row per paper, all fields (the master table)
  review/synthesis/datasets.csv        dataset x papers (canonical names, public, TLS content)
  review/synthesis/unmapped_datasets.csv  dataset names not in the registry, for extending it by hand
  review/synthesis/SUMMARY.md          counts per field, grouped by RQ
"""
import ast
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from dataset_registry import canonical

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "review" / "synthesis"
LIST_FIELDS = {"label_source", "features_used", "feature_groups", "fingerprints_used", "tls_versions_stated",
               "split_protocols", "shortcut_check", "metrics", "model_family"}
EMPTY = {"", "none", "not_stated", "not stated", "not_applicable", "unclear", "n/a"}


def dataset_names(v: str) -> list[str]:
    """Verified datasets are '; '-joined items, each a dict repr or 'name (role)'."""
    names = []
    for m in re.finditer(r"\{'name':.*?'quote':\s*(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\s*\}", v, re.S):
        try:
            names.append(ast.literal_eval(m.group(0))["name"])
        except (ValueError, SyntaxError):
            names.append(re.search(r"'name':\s*'([^']*)'", m.group(0)).group(1))
    rest = re.sub(r"\{'name':.*?'quote':\s*(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\s*\}", "", v, flags=re.S)
    for item in rest.split(";"):
        item = re.sub(r"\((train|test|train_and_test|unclear)\)\s*$", "", item.strip()).strip()
        if item and item.lower() not in EMPTY:
            names.append(item)
    return names


def items(field: str, v: str) -> list[str]:
    if field not in LIST_FIELDS:
        return [v.strip()]
    parts = [p.strip() for p in re.split(r";(?![^()]*\))", v)]
    return [p for p in parts if p and p.lower() not in ("none",)] or ["none"]


METRIC_NAMES = [(r"^f1|f-?measure|f-?score", "f1"), (r"macro.?f1", "macro_f1"), (r"pr.?auc|average precision|auprc", "pr_auc"),
                 (r"roc|^auc", "roc_auc"), (r"accura", "accuracy"), (r"^prec", "precision"),
                 (r"^recall|tpr|true positive rate|detection rate|detection_rate|sensitivity", "recall/tpr"),
                 (r"fpr|false positive|false alarm", "fpr"), (r"fnr|false negative", "fnr"), (r"mcc|matthews", "mcc"),
                 (r"confusion", "confusion_matrix"), (r"specificity|tnr|true negative rate", "specificity"),
                 (r"time|speed|latency|throughput", "time/cost")]


def metric(m: str) -> str:
    m = m.strip().lower()
    if re.search(r"macro.*f1", m):
        return "macro_f1"
    return next((name for rx, name in METRIC_NAMES if re.search(rx, m)), m)


def prefix(v: str) -> str:
    v = v.lower()
    if "whole" in v or "full" in v:
        return "whole flow"
    if v in EMPTY:
        return "unclear"
    n = re.search(r"\d+", v)
    return f"first N: {'<=10' if int(n.group()) <= 10 else '11-50' if int(n.group()) <= 50 else '>50'}" if n else "other"


def visibility(p: dict) -> str:
    groups = set(p["feature_groups"])
    fps = {f for f in p["fingerprints_used"] if f.lower() not in EMPTY}
    if p["cert_fields_read"][0].lower() == "yes":
        return "tls12"
    if groups & {"G3", "G5"} or fps:
        return "tls13"
    return "tls13_ech" if groups & {"G1", "G2", "G4"} else "unclear"


def pct(n: int, total: int) -> str:
    return f"{n} ({100 * n / total:.0f}%)"


def main() -> None:
    rows = list(csv.DictReader(open(ROOT / "review" / "coding" / "core_67_papers_verification.csv", encoding="utf-8-sig")))
    papers: dict[str, dict] = defaultdict(dict)
    for r in rows:
        p = papers[r["paper_id"]]
        p.update(paper_id=r["paper_id"], year=r["year"], kind=r["kind"], venue=r["venue"], title=r["title"])
        p[r["field"]] = dataset_names(r["verified_value"]) if r["field"] == "datasets_evaluated" else items(r["field"], r["verified_value"])

    unmapped = Counter()
    for p in papers.values():
        regs = [canonical(n) for n in p["datasets_evaluated"]]
        for n, g in zip(p["datasets_evaluated"], regs):
            if g["status"] == "not_in_registry":
                unmapped[n] += 1
        canon = {}
        for g in regs:
            canon.setdefault(g["name"], g)
        p["datasets_canonical"] = sorted(canon)
        p["_registry"] = canon
        p["any_public_dataset"] = "yes" if any(g["public"] == "yes" for g in canon.values()) else "no"
        p["only_own_or_private"] = "yes" if canon and all(g["public"] != "yes" for g in canon.values()) else "no"
        p["visibility_tier"] = visibility(p)
        p["metrics"] = sorted({metric(x) for x in p["metrics"] if x.lower() not in EMPTY}) or ["none"]
        p["accuracy_only"] = "yes" if p["metrics"] == ["accuracy"] else "no"
        p["reports_fpr_or_pr_auc"] = "yes" if {"fpr", "pr_auc"} & set(p["metrics"]) else "no"
        p["first_n_bucket"] = prefix(p["first_n_packets"][0])
        p["main_split"] = ["unclear" if p["main_split"][0] == "not_stated" else p["main_split"][0]]

    OUT.mkdir(parents=True, exist_ok=True)
    order = ["paper_id", "year", "kind", "venue", "title", "datasets_canonical", "any_public_dataset", "only_own_or_private",
             "label_source", "label_feature_overlap", "feature_groups", "cert_fields_read", "fingerprints_used",
             "tls_versions_stated", "ech_considered", "visibility_tier", "model_family", "split_protocols", "main_split",
             "easy_vs_hard_reported", "shortcut_check", "metrics", "accuracy_only", "reports_fpr_or_pr_auc", "granularity",
             "first_n_packets", "first_n_bucket", "cost_reported", "hardware", "code_released", "data_released", "features_used",
             "datasets_evaluated"]
    with open(OUT / "papers.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(order)
        for p in sorted(papers.values(), key=lambda p: p["paper_id"]):
            w.writerow(["; ".join(p[k]) if isinstance(p[k], list) else p[k] for k in order])

    ds = defaultdict(list)
    for p in papers.values():
        for name, g in p["_registry"].items():
            ds[name].append((p["paper_id"], g))
    with open(OUT / "datasets.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "papers", "public", "tls_content", "in_registry", "paper_ids"])
        for name, ps in sorted(ds.items(), key=lambda kv: -len(kv[1])):
            g = ps[0][1]
            w.writerow([name, len(ps), g["public"], g.get("tls", ""), g["status"] != "not_in_registry",
                        " ".join(sorted(x for x, _ in ps))])
    with open(OUT / "unmapped_datasets.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["name_as_coded", "papers"])
        w.writerows(unmapped.most_common())

    n = len(papers)
    ps = list(papers.values())

    def count(field: str, multi: bool) -> list[str]:
        c = Counter()
        for p in ps:
            vals = p[field] if isinstance(p[field], list) else [p[field]]
            for v in (set(vals) if multi else vals[:1]):
                c[re.sub(r"\s*\(.*", "", v) if field == "label_source" else v] += 1
        return [f"| {k} | {pct(v, n)} |" for k, v in c.most_common(15)]

    sections = [
        ("Datasets (RQ1)", [("any_public_dataset", False), ("only_own_or_private", False)]),
        ("Labels (RQ1/RQ2)", [("label_source", True), ("label_feature_overlap", False)]),
        ("Evaluation protocol (RQ1)", [("main_split", False), ("split_protocols", True), ("easy_vs_hard_reported", False),
                                       ("shortcut_check", True)]),
        ("Metrics (RQ1)", [("accuracy_only", False), ("reports_fpr_or_pr_auc", False), ("metrics", True)]),
        ("Features and TLS visibility (RQ2/RQ5)", [("visibility_tier", False), ("feature_groups", True),
                                                   ("cert_fields_read", False), ("fingerprints_used", True),
                                                   ("tls_versions_stated", True), ("ech_considered", False)]),
        ("Deployment (RQ3/RQ4)", [("granularity", False), ("first_n_bucket", False), ("cost_reported", False)]),
        ("Reproducibility", [("code_released", False), ("data_released", False)]),
    ]
    md = [f"# Core-set synthesis ({n} papers)", "",
          "Generated by `scripts/synthesis_tables.py` from the verified coding. Multi-valued fields count papers per value, "
          "so their percentages can sum past 100%. Do not edit by hand.", "",
          "## Papers per year", "", "| Year | Papers |", "|---|---|"]
    md += [f"| {y} | {c} |" for y, c in sorted(Counter(p["year"] for p in ps).items())]
    for title, fields in sections:
        md += ["", f"## {title}"]
        for field, multi in fields:
            md += ["", f"**{field}**", "", "| Value | Papers |", "|---|---|"] + count(field, multi)
    md += ["", "## Datasets used by 3 or more papers", "", "| Dataset | Papers | Public |", "|---|---|---|"]
    md += [f"| {k} | {len(v)} | {v[0][1]['public']} |" for k, v in sorted(ds.items(), key=lambda kv: -len(kv[1])) if len(v) >= 3]
    md += ["", f"Dataset names not in the registry: {sum(unmapped.values())} mentions of {len(unmapped)} names "
           "(`unmapped_datasets.csv`)."]
    (OUT / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{n} papers -> {OUT}; unmapped dataset names: {len(unmapped)}")


if __name__ == "__main__":
    main()
