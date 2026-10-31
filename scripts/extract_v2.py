"""Extraction to the revised coding form (plan.md §4, revised 28 Oct 2026).

Usage: python scripts/extract_v2.py PAPER.pdf OUT.json [--model gemini-3.1-flash-lite]
Per paper: 4 field-group calls (schema-constrained, one verbatim quote per answer), 1 checking call,
1 link-classification call. Text comes from pdf_prep (cleaned body + tables, references removed);
artifact links come from artifact_links (whole PDF incl. references). Computed fields
(visibility_tier, accuracy_only, code/data_released, dataset registry lookups) are added by derive(),
which vote_v2.py re-applies after the majority vote. Writes OUT.json (checked) and a draft file
(<paper>__<tag>draft_rN.json) like llm_extract_grouped.py.
"""
import argparse
import json
import re
import time
from pathlib import Path

from artifact_links import find_links
from dataset_registry import canonical
from llm_extract import call_gemini, norm, quote_found
from pdf_prep import clean, prepare

YN = ["yes", "no"]
SPLITS = ["random", "stratified_random", "per_packet", "host_grouped", "temporal", "cross_dataset",
          "not_applicable", "unclear"]

FIELDS = {  # name: (definition, value schema)
    "datasets_evaluated": (
        "every dataset the paper uses to train or test ITS OWN method (not datasets only cited or described). "
        "Name the data SOURCE as the paper describes it (e.g. 'CIC-IDS2017', 'traffic captured in a commercial "
        "sandbox', 'campus network traffic'), not the paper's internal split or subset labels (e.g. 'Train01', "
        "'Benign02'); one entry per source. Role train, test or train_and_test; quote = one verbatim passage "
        "that shows the dataset is used",
        {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "name": {"type": "STRING"},
            "role": {"type": "STRING", "enum": ["train", "test", "train_and_test", "unclear"]},
            "quote": {"type": "STRING"}}, "required": ["name", "role", "quote"]}}),
    "label_source": (
        "the signal used to decide which flows are malicious vs benign, NOT where the traffic came from. "
        "sandbox = every flow of a sandbox run labelled malicious; blocklist_cert / blocklist_ja3 = labels from a "
        "certificate or JA3 blocklist (e.g. SSLBL); ids_alerts = IDS/IPS alerts; dataset_provided = labels shipped "
        "with a public dataset; manual = human inspection; generated = attack traffic the authors generated "
        "themselves, labelled by construction; list every signal used",
        {"type": "ARRAY", "items": {"type": "STRING", "enum": [
            "sandbox", "blocklist_cert", "blocklist_ja3", "ids_alerts", "dataset_provided", "manual", "generated",
            "other", "unclear"]}}),
    "label_feature_overlap": (
        "yes if a classifier input uses the same signal the labels were derived from (e.g. certificate features "
        "with certificate-blocklist labels, JA3 features with JA3-blocklist labels); not_applicable if no "
        "classifier is trained",
        {"type": "STRING", "enum": ["yes", "no", "unclear", "not_applicable"]}),
    "features_used": (
        "the inputs of the paper's own classifier/detector, as short phrases in the paper's words (e.g. 'sizes "
        "and directions of the first 20 records', 'certificate size inferred from record lengths', 'cipher "
        "suites', 'JA3 hash'). Fields used only to filter, label or group flows do NOT count",
        {"type": "ARRAY", "items": {"type": "STRING"}}),
    "feature_groups": (
        "groups of the classifier inputs: G1 whole-flow statistics (duration, byte/packet totals, rates); G2 "
        "sequences of packet/record sizes, directions or timing; G3 ClientHello/ServerHello fields incl. SNI, "
        "ALPN, cipher suites, extensions; G4 certificate fields incl. certificate size; G5 JA3/JA4-style "
        "fingerprints",
        {"type": "ARRAY", "items": {"type": "STRING", "enum": ["G1", "G2", "G3", "G4", "G5"]}}),
    "cert_fields_read": (
        "yes if the classifier reads fields from the server Certificate message in cleartext (issuer, subject, "
        "validity, SAN, self-signed, chain length); no if certificate information is only INFERRED from "
        "encrypted record sizes or not used; not_applicable if no certificate information is used",
        {"type": "STRING", "enum": ["yes", "no", "not_applicable"]}),
    "fingerprints_used": (
        "TLS fingerprints the classifier uses as input; none if no fingerprint",
        {"type": "ARRAY", "items": {"type": "STRING", "enum": ["none", "JA3", "JA3S", "JA4", "JA4S", "other"]}}),
    "tls_versions_stated": (
        "TLS versions the paper STATES are present in its evaluation data; not_stated if the paper does not say. "
        "Never infer versions from a dataset's name or year",
        {"type": "ARRAY", "items": {"type": "STRING", "enum": ["1.0", "1.1", "1.2", "1.3", "not_stated"]}}),
    "ech_considered": (
        "yes if the paper evaluates, simulates or explicitly assumes Encrypted Client Hello (e.g. a threat model "
        "or feature design where ECH hides the SNI/inner ClientHello); no if ECH is only background or future work",
        {"type": "STRING", "enum": YN}),
    "model_family": (
        "ML/DL model types of the paper's OWN method (not baselines), short; none if no learned model",
        {"type": "STRING"}),
    "split_protocols": (
        "every way the paper splits training and test data in its own experiments: random (incl. k-fold "
        "cross-validation), stratified_random, per_packet (packets of one flow can land in train and test), "
        "host_grouped (no host/IP/capture/trace in both), temporal (test data collected strictly after training "
        "data; a TLS-version transfer alone is not temporal), cross_dataset (train on one dataset, test on "
        "another); not_applicable if no model is trained and tested",
        {"type": "ARRAY", "items": {"type": "STRING", "enum": SPLITS}}),
    "main_split": (
        "the split protocol of the main experiment, i.e. the one behind the paper's headline detection result "
        "(not side, sensitivity or ablation experiments)",
        {"type": "STRING", "enum": SPLITS}),
    "easy_vs_hard_reported": (
        "yes if the paper reports results for the same method under both a random split and a harder one "
        "(host_grouped, temporal or cross_dataset), so the drop can be seen; not_applicable if no model is trained",
        {"type": "STRING", "enum": ["yes", "no", "not_applicable"]}),
    "shortcut_check": (
        "checks the authors make that the model does not learn shortcuts: identifier_removal (IP, port, TTL or "
        "other testbed identifiers removed from the inputs), ablation (removing feature groups and reporting the "
        "effect), probe (a test for dataset-of-origin or environment artefacts); none if nothing like this",
        {"type": "ARRAY", "items": {"type": "STRING", "enum": [
            "none", "identifier_removal", "ablation", "probe", "other"]}}),
    "metrics": ("evaluation metrics reported for the paper's own method", {"type": "ARRAY", "items": {"type": "STRING"}}),
    "granularity": ("unit that is classified", {"type": "STRING", "enum": ["packet", "flow", "session", "host", "unclear"]}),
    "first_n_packets": (
        "if the method decides from only the first N packets or records of a flow, N with its unit (e.g. '20 "
        "records'); otherwise 'whole flow'",
        {"type": "STRING"}),
    "cost_reported": (
        "none; inference_only (only model inference time/throughput); end_to_end (feature extraction plus "
        "inference)", {"type": "STRING", "enum": ["none", "inference_only", "end_to_end", "unclear"]}),
    "hardware": (
        "only hardware used to MEASURE runtime/latency/throughput of the method; none if no timing results",
        {"type": "STRING"}),
}

GROUPS = {
    "data and labels": ["datasets_evaluated", "label_source", "label_feature_overlap"],
    "features and TLS visibility": ["features_used", "feature_groups", "cert_fields_read", "fingerprints_used",
                                    "tls_versions_stated", "ech_considered"],
    "evaluation protocol": ["model_family", "split_protocols", "main_split", "easy_vs_hard_reported",
                            "shortcut_check", "metrics"],
    "deployment": ["granularity", "first_n_packets", "cost_reported", "hardware"],
}

QUOTE_RULES = """- "evidence" is ONE contiguous passage (max 40 words) copied character-for-character from the paper.
  Never join separate sentences, never use "..." and never paraphrase. If the support is spread over several
  places, quote the single most decisive passage.
- "evidence_source": "text", "table" or "figure" (for a table or figure, copy the caption or the row), or "none"
  with evidence "" if nothing in the paper supports the value.
- Answer ONLY from this paper. Do not use your own knowledge of datasets, tools or other papers."""

EXTRACT_PROMPT = """You are coding one research paper for a systematic review of machine-learning detection of
malicious TLS traffic. This request covers only the "{group}" part of the coding form.
- Code what the paper states about ITS OWN method and experiments (not related work or baselines from other papers).
- If the paper does not say, use "unclear" (or "none"/"not_applicable"/"not_stated" where the definition allows).
{quote_rules}

Fields:
{fields}

PAPER TEXT (related work and references removed; tables appended at the end):
<<<
{text}
>>>"""

CHECK_PROMPT = """You are the second coder in a systematic review of machine-learning detection of malicious TLS
traffic. Below are draft answers for one paper with their supporting quotes, then the paper.
For EVERY field verify the value against the paper and the field definition.
- Keep the draft (check = "kept", value and evidence unchanged) unless you can quote a passage of the paper that
  contradicts it or shows it violates the definition.
- Only then return the corrected value, that passage as evidence, check = "changed" and a one-sentence reason.
  Do not change an answer just because another reading is possible, and do not replace a main-experiment answer
  with one from a side experiment.
{quote_rules}

Field definitions:
{fields}

DRAFT ANSWERS:
{draft}

PAPER TEXT:
<<<
{text}
>>>"""

LINK_PROMPT = """For a systematic review we must know whether the authors of this paper released THEIR OWN code
or data. Below are links found in the paper (body, footnotes, availability statements and reference entries),
each with the text around it. Classify every link:
- own_code / own_data / own_code_and_data: the authors' own artifact for this paper, available now
- own_promised: the authors' own artifact that is only promised ("will be released"), or available on request
- third_party_tool / third_party_dataset: someone else's software or dataset that the paper uses or cites
- cited_work: a link to another paper or web page
- other
A link marked "SAME AUTHORS" points to a reference written by one of this paper's own authors: if the paper
presents it as its own pipeline, tool, code or dataset (e.g. "publicly available ... pipeline [20]", "our
dataset [25]"), it is own_*, even when it was published as a separate item.
evidence = one verbatim passage from the given context that supports the class.

THIS PAPER'S AUTHORS: {authors}

PAPER TITLE AND START:
{head}

LINKS:
{links}"""

LINK_SCHEMA = {"type": "OBJECT", "properties": {"links": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "url": {"type": "STRING"},
    "kind": {"type": "STRING", "enum": ["own_code", "own_data", "own_code_and_data", "own_promised",
                                         "third_party_tool", "third_party_dataset", "cited_work", "other"]},
    "evidence": {"type": "STRING"}}, "required": ["url", "kind", "evidence"]}}}, "required": ["links"]}

QUOTE_MATCH_FLAG = 0.9


def field_schema(names: list[str], check: bool = False) -> dict:
    props = {}
    for n in names:
        p = {"value": FIELDS[n][1], "evidence": {"type": "STRING"},
             "evidence_source": {"type": "STRING", "enum": ["text", "table", "figure", "none"]}}
        req = ["value", "evidence", "evidence_source"]
        if check:
            p.update(check={"type": "STRING", "enum": ["kept", "changed"]}, reason={"type": "STRING"})
            req += ["check", "reason"]
        props[n] = {"type": "OBJECT", "properties": p, "required": req}
    return {"type": "OBJECT", "properties": props, "required": names}


def describe(names: list[str]) -> str:
    return "\n".join(f"- {n}: {FIELDS[n][0]}" for n in names)


def parse(resp: dict) -> dict:
    try:
        return json.loads(resp.get("response", ""))
    except json.JSONDecodeError:
        return {"_parse_error": resp.get("response", "")[:2000]}


def merge_parts(answers: list[dict]) -> dict:
    """Combine group answers from several text parts: lists are unioned, scalars take the first informative value."""
    out = {}
    for ans in answers:
        for k, v in ans.items():
            if k not in out:
                out[k] = v
                continue
            if isinstance(v.get("value"), list) and isinstance(out[k].get("value"), list):
                seen = {json.dumps(x, sort_keys=True) for x in out[k]["value"]}
                out[k]["value"] += [x for x in v["value"] if json.dumps(x, sort_keys=True) not in seen]
            elif str(out[k].get("value")).lower() in ("unclear", "none", "not_applicable", "not_stated", ""):
                out[k] = v
    return out


def flag_quotes(ans: dict, full_norm: str) -> None:
    for name, v in ans.items():
        if not isinstance(v, dict):
            continue
        quotes = [str(v.get("evidence", ""))]
        if name == "datasets_evaluated" and isinstance(v.get("value"), list):
            quotes += [str(d.get("quote", "")) for d in v["value"] if isinstance(d, dict)]
        scores = [quote_found(clean(q), full_norm) for q in quotes if q.strip()]
        v["quote_match"] = min(scores) if scores else None
        flags = []
        if scores and min(scores) < QUOTE_MATCH_FLAG:
            flags.append("quote_not_verbatim")
        if any("..." in q or "…" in q for q in quotes):
            flags.append("spliced_quote")
        if v.get("check") == "changed":
            flags.append("changed_by_check")
        v["review_flags"] = flags


def derive(fields: dict, link_info: dict) -> dict:
    """Computed fields (plan.md §4): registry lookups, visibility tier, accuracy_only, artifact release."""
    val = lambda k: (fields.get(k) or {}).get("value")
    out = {}
    ds = val("datasets_evaluated") or []
    reg = [canonical(d.get("name", "")) for d in ds if isinstance(d, dict)]
    for d, r in zip([d for d in ds if isinstance(d, dict)], reg):
        d["canonical"] = r["name"]
    out["datasets_canonical"] = {"value": sorted({r["name"] for r in reg}), "source": "registry"}
    out["dataset_public"] = {"value": {r["name"]: r["public"] for r in reg}, "source": "registry",
                             "review_flags": ["dataset_not_in_registry"] if any(r["status"] == "not_in_registry" for r in reg) else []}
    groups = set(val("feature_groups") or [])
    fps = set(val("fingerprints_used") or []) - {"none"}
    if val("cert_fields_read") == "yes":
        tier, why = "tls12", "reads certificate fields in cleartext (encrypted in TLS 1.3)"
    elif groups & {"G3", "G5"} or fps:
        tier, why = "tls13", "uses ClientHello/ServerHello fields or fingerprints (hidden by ECH)"
    elif groups:
        tier, why = "tls13_ech", "only sizes, directions, timing or flow statistics"
    else:
        tier, why = "unclear", "no feature groups coded"
    out["visibility_tier"] = {"value": tier, "source": "computed", "reason": why}
    metrics = [str(m).lower() for m in (val("metrics") or [])]
    out["accuracy_only"] = {"value": "yes" if metrics and all("accura" in m for m in metrics) else "no",
                            "source": "computed"}
    kinds = [l.get("kind") for l in link_info.get("classified", [])]
    own = [l for l in link_info.get("classified", []) if str(l.get("kind", "")).startswith("own_") and l["kind"] != "own_promised"]
    out["code_released"] = {"value": "yes" if {"own_code", "own_code_and_data"} & set(kinds) else "no",
                            "source": "link scan + LLM", "evidence": [l["url"] for l in own],
                            "review_flags": ["no_link_found"] if not link_info.get("classified") else []}
    out["data_released"] = {"value": "yes" if {"own_data", "own_code_and_data"} & set(kinds) else "no",
                            "source": "link scan + LLM", "evidence": [l["url"] for l in own]}
    if "own_promised" in kinds:
        for k in ("code_released", "data_released"):
            out[k].setdefault("review_flags", []).append("release_only_promised")
    if str(val("cost_reported")).lower() == "none":
        out["hardware"] = {"value": "none", "evidence": "", "evidence_source": "none",
                           "source": "computed (cost_reported is none)", "votes": "3/3"}
    return out


def paper_authors(pdf_path: str) -> list[str]:
    """Authors from the search records when the PDF is named by record id (papers/core/S1234.pdf)."""
    m = re.match(r"(S\d{4})", Path(pdf_path).stem)
    if not m:
        return []
    import csv
    recs = Path(__file__).resolve().parent.parent / "review" / "search" / "records.csv"
    for r in csv.DictReader(open(recs, encoding="utf-8")):
        if r["id"] == m.group(1):
            return [a.strip() for a in r["authors"].split(";") if a.strip()]
    return []


def same_authors(authors: list[str], context: str) -> list[str]:
    """Surnames of this paper's authors that appear in a reference entry of the link's context."""
    ref = context.split("REFERENCE", 1)[1] if "REFERENCE" in context else ""
    surnames = {a.split()[-1] for a in authors if len(a.split()[-1]) > 2}
    return sorted(s for s in surnames if re.search(rf"\b{re.escape(s)}\b", ref, re.I))


def classify_links(model: str, thinking: str, paper, links: dict) -> list[dict]:
    if not links["links"]:
        return []
    authors = paper_authors(paper.path)
    rows = []
    for i, l in enumerate(links["links"], 1):
        overlap = same_authors(authors, l["context"])
        l["same_authors"] = overlap
        mark = f" SAME AUTHORS ({', '.join(overlap)})" if overlap else ""
        rows.append(f"[{i}] {l['url']} (found in {l['found_in']}){mark}\nCONTEXT: {l['context']}")
    prompt = LINK_PROMPT.format(authors="; ".join(authors) or "unknown", head=paper.body[:1500], links="\n\n".join(rows))
    resp = call_gemini(model, prompt, thinking, None, LINK_SCHEMA)
    got = parse(resp).get("links", [])
    found = {l["url"]: l for l in links["links"]}
    for g in got:
        g["found_in"] = found.get(g.get("url"), {}).get("found_in", "?")
    return got


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paper")
    ap.add_argument("out")
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument("--thinking-level", default="high")
    a = ap.parse_args()

    t0 = time.time()
    paper = prepare(a.paper)
    full_norm = norm(paper.full)
    links = find_links(paper)
    calls = []

    draft: dict = {}
    for group, names in GROUPS.items():
        answers = []
        for part in paper.parts:
            resp = call_gemini(a.model, EXTRACT_PROMPT.format(group=group, fields=describe(names), text=part,
                                                              quote_rules=QUOTE_RULES),
                               a.thinking_level, None, field_schema(names))
            answers.append({k: v for k, v in parse(resp).items() if k in names})
            calls.append({"call": group, "done_reason": resp.get("done_reason")})
        draft.update(merge_parts(answers))

    names = list(FIELDS)
    draft_view = json.dumps({k: draft.get(k, {"value": "MISSING", "evidence": ""}) for k in names}, indent=1,
                            ensure_ascii=False)
    checked_parts = []
    for part in paper.parts:
        resp = call_gemini(a.model, CHECK_PROMPT.format(fields=describe(names), draft=draft_view, text=part,
                                                        quote_rules=QUOTE_RULES),
                           a.thinking_level, None, field_schema(names, check=True))
        checked_parts.append(parse(resp))
        calls.append({"call": "check", "done_reason": resp.get("done_reason")})
    checked = checked_parts[0] if len(checked_parts) == 1 else merge_parts(checked_parts)
    if "_parse_error" in checked:  # keep the draft rather than lose the paper
        checked = {k: dict(v, check="check_failed") for k, v in draft.items()}

    classified = classify_links(a.model, a.thinking_level, paper, links)
    calls.append({"call": "links", "n": len(links["links"])})
    link_info = {"found": links["links"], "classified": classified,
                 "not_released_statements": links["not_released_statements"]}

    for ans in (draft, checked):
        flag_quotes(ans, full_norm)
    meta = {"paper": a.paper, "model": a.model, "method": "v2: grouped+schema+check, link scan, registry, derived",
            "elapsed_s": round(time.time() - t0, 1), "calls": calls, "input_log": paper.log,
            "chars_sent": sum(len(p) for p in paper.parts), "parts": len(paper.parts), "links": link_info}
    out = Path(a.out)
    m = re.match(r"(.+__)([^_]+)(_r\d+\.json)$", out.name)
    draft_out = out.with_name(f"{m.group(1)}{m.group(2)}draft{m.group(3)}") if m else out.with_suffix(".draft.json")
    for path, stage, ans in ((draft_out, "draft", draft), (out, "checked", checked)):
        fields = {k: ans[k] for k in names if k in ans}
        fields.update(derive(fields, link_info))
        path.write_text(json.dumps({**meta, "stage": stage, "missing_fields": [k for k in names if k not in ans],
                                    "fields": fields}, indent=2, ensure_ascii=False), encoding="utf-8")
    flagged = {k: v.get("review_flags") for k, v in checked.items() if isinstance(v, dict) and v.get("review_flags")}
    print(json.dumps({"paper": Path(a.paper).name, "elapsed_s": meta["elapsed_s"], "parts": len(paper.parts),
                      "links": len(links["links"]), "review_flags": flagged}, ensure_ascii=False))


if __name__ == "__main__":
    main()
