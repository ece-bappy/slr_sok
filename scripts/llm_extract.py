"""Fill the review extraction form for one paper with a local Ollama model or the Gemini API.

Usage: python scripts/llm_extract.py PAPER.(pdf|txt) OUT.json [--think | --no-think]
       [--backend ollama --model gemma4:26b --host http://172.16.0.239:11434]
       [--backend gemini --model gemini-3.1-flash-lite --thinking-level high]
The Gemini key is read from env GEMINI_API_KEY / Gemini_API_KEY (or the Windows user environment).

Every field comes back with a verbatim evidence quote; the script checks each
quote against the paper text so hallucinated support can be flagged.
"""
import argparse
import difflib
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

FIELDS = {
    "datasets": "names of all datasets used for training or testing",
    "dataset_public": "yes/no/partly: are the datasets publicly available",
    "label_source": "one of sandbox, blacklist_cert, blacklist_ja3, ids_alert, manual, synthetic_attack, unknown (semicolon list allowed)",
    "label_feature_overlap": "yes/no/unclear: does any classifier feature use the same signal the labels were derived from (e.g. certificate features with certificate-blacklist labels)",
    "feature_groups": "semicolon list of G1 flow statistics, G2 packet size/timing sequences, G3 handshake fields, G4 certificate fields, G5 fingerprints (JA3/JA4)",
    "feature_visibility_tier": (
        "one of tls12, tls13, tls13_ech, decided by the features the proposed method uses, applying the first rule that matches: "
        "(1) any field read from the server Certificate message (issuer, subject, validity, SAN, self-signed, chain length, "
        "certificate read in cleartext) -> tls12, because TLS 1.3 encrypts certificates; "
        "(2) otherwise any ClientHello/ServerHello field, SNI, ALPN, or JA3/JA4/JA3S/JA4S fingerprint -> tls13, because ECH hides the inner ClientHello; "
        "(3) otherwise only packet or record sizes, directions, counts, timing or flow statistics (including a certificate size "
        "INFERRED from encrypted record lengths) -> tls13_ech"
    ),
    "model_family": "ML/DL model types of the paper's own method (not baselines from other papers), or none if no learned model",
    "split_protocol": (
        "one of random, temporal, host_grouped, cross_dataset, mixed, unclear, not_applicable. "
        "Use not_applicable when no model is trained and then tested (e.g. a measurement or fingerprint analysis)"
    ),
    "host_grouped": "yes/no/unclear/not_applicable: are train/test splits grouped so the same host/IP/capture is never in both",
    "cross_dataset": "yes/no/not_applicable: a model trained on one dataset is tested on a different dataset",
    "temporal": (
        "yes/no/unclear/not_applicable: yes ONLY if a trained model is tested on data collected strictly after its training data. "
        "Comparing statistics between time periods without training and testing a model is not_applicable"
    ),
    "granularity": "one of packet, flow, session, host",
    "early_detection": "yes/no/not_applicable: the method decides before the flow ends using only its first packets or records",
    "first_n_packets": "number of packets/records used if limited, else none",
    "cost_reported": "one of none, inference_only, end_to_end",
    "hardware": "hardware used for timing/cost measurements, else none",
    "tls_versions": "TLS versions present in the evaluation data",
    "ech_considered": "yes/no: is Encrypted Client Hello evaluated or simulated",
    "ja4_used": "yes/no",
    "metrics": "evaluation metrics reported",
    "best_reported_score": "headline best result with metric name",
    "code_released": "yes/no",
    "data_released": (
        "yes/no/partly: did THESE authors publish data they created (captures, labels, features)? "
        "Merely using an existing public dataset is no"
    ),
}

PROMPT = """You are coding a research paper for a systematic review of malicious TLS traffic detection.
Read the paper and fill every field. Rules:
- Use only what the paper states. If it is not stated, use "unclear" (or "none" where that fits).
- For each field give "value" and "evidence": a short VERBATIM quote (max 40 words) copied exactly from the paper that supports the value, or "" if there is none.
- Output a single JSON object: {{"<field>": {{"value": ..., "evidence": "..."}}, ...}}.

Fields:
{fields}

PAPER TEXT:
<<<
{text}
>>>"""


def clean_text(raw: str, max_chars: int) -> str:
    # Drop the reference list and collapse whitespace to save context.
    m = re.search(r"\n\s*(REFERENCES|References|Bibliography)\s*\n", raw)
    body = raw[: m.start()] if m and m.start() > len(raw) * 0.4 else raw
    body = re.sub(r"-\n(\w)", r"\1", body)
    body = re.sub(r"\s+", " ", body)
    return body[:max_chars]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def quote_found(quote: str, text_norm: str) -> float:
    """1.0 if the quote occurs verbatim (after normalisation), else best fuzzy ratio."""
    q = norm(quote)
    if not q:
        return 0.0
    if q in text_norm:
        return 1.0
    m = difflib.SequenceMatcher(None, text_norm, q, autojunk=False)
    blk = m.find_longest_match(0, len(text_norm), 0, len(q))
    start = max(0, blk.a - blk.b)
    window = text_norm[start : start + len(q) + 20]
    return round(difflib.SequenceMatcher(None, window, q).ratio(), 3)


def call_ollama(host: str, model: str, prompt: str, think: bool, num_ctx: int, options: dict) -> dict:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "think": think,
        "options": {"num_ctx": num_ctx, **options},
    }
    req = urllib.request.Request(
        f"{host}/api/generate", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=3600) as r:
        return json.loads(r.read())


GEMINI_MIN_GAP_S = 4.2  # free tier: 15 requests/minute, shared across processes via a timestamp file
_GEMINI_STAMP = Path(tempfile.gettempdir()) / "tlssok_gemini_last_call"


def gemini_key() -> str:
    for name in ("GEMINI_API_KEY", "Gemini_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    if os.name == "nt":  # setx writes the user environment, which running shells may not see yet
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            for name in ("GEMINI_API_KEY", "Gemini_API_KEY"):
                try:
                    return winreg.QueryValueEx(k, name)[0]
                except FileNotFoundError:
                    pass
    raise SystemExit("Gemini API key not found (GEMINI_API_KEY / Gemini_API_KEY)")


def call_gemini(model: str, prompt: str, thinking_level: str | None, temperature: float | None) -> dict:
    """Call generateContent and return a dict shaped like Ollama's response."""
    gen = {"responseMimeType": "application/json"}
    if temperature is not None:
        gen["temperature"] = temperature
    if thinking_level:
        gen["thinkingConfig"] = {"thinkingLevel": thinking_level, "includeThoughts": True}
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": gemini_key()}

    for attempt in range(6):
        last = float(_GEMINI_STAMP.read_text()) if _GEMINI_STAMP.exists() else 0.0
        wait = GEMINI_MIN_GAP_S - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _GEMINI_STAMP.write_text(str(time.time()))
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code in (429, 500, 503) and attempt < 5:
                m = re.search(r'"retryDelay":\s*"(\d+)', detail)
                time.sleep(int(m.group(1)) + 1 if m else 15 * (attempt + 1))
                continue
            raise SystemExit(f"Gemini HTTP {e.code}: {detail[:500]}")

    cand = (data.get("candidates") or [{}])[0]
    parts = cand.get("content", {}).get("parts", [])
    usage = data.get("usageMetadata", {})
    return {
        "response": "".join(p.get("text", "") for p in parts if not p.get("thought")),
        "thinking": "".join(p.get("text", "") for p in parts if p.get("thought")),
        "done_reason": cand.get("finishReason"),
        "prompt_eval_count": usage.get("promptTokenCount"),
        "eval_count": (usage.get("candidatesTokenCount") or 0) + (usage.get("thoughtsTokenCount") or 0),
        "thought_tokens": usage.get("thoughtsTokenCount"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paper")
    ap.add_argument("out")
    ap.add_argument("--think", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--backend", choices=["ollama", "gemini"], default="ollama")
    ap.add_argument("--model", default=None, help="default gemma4:26b (ollama) / gemini-3.1-flash-lite (gemini)")
    ap.add_argument("--thinking-level", default="high", help="gemini only: minimal/low/medium/high")
    ap.add_argument("--host", default="http://172.16.0.239:11434")
    ap.add_argument("--max-chars", type=int, default=90000)
    # Default: sized to the prompt plus the output budget, since a larger context pushes model
    # layers off the GPU and slows everything down.
    ap.add_argument("--num-ctx", type=int, default=None)
    # Greedy decoding (temperature 0) makes Gemma's reasoning loop ("Wait, <field>..." until the
    # context is full), so reasoning runs use Google's recommended sampling instead.
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--num-predict", type=int, default=None)
    a = ap.parse_args()
    if a.model is None:
        a.model = "gemini-3.1-flash-lite" if a.backend == "gemini" else "gemma4:26b"
    if a.temperature is None:
        a.temperature = 1.0 if a.think else 0.0
    if a.num_predict is None:
        a.num_predict = 16000 if a.think else 3000
    options = {"temperature": a.temperature, "num_predict": a.num_predict}
    if a.think:
        options.update(top_k=64, top_p=0.95)

    dropped = []
    if a.paper.lower().endswith(".pdf"):
        import fitz  # PyMuPDF

        from pdf_sections import extract as extract_sections

        with fitz.open(a.paper) as doc:
            raw = "\n".join(page.get_text() for page in doc)
        body, report = extract_sections(a.paper)
        dropped = [h for act, h, _ in report if act == "drop"]
    else:
        raw = Path(a.paper).read_text(errors="replace")
        body = raw
    text = clean_text(body, a.max_chars)
    fields = "\n".join(f"- {k}: {v}" for k, v in FIELDS.items())
    prompt = PROMPT.format(fields=fields, text=text)
    if a.num_ctx is None:
        need = len(prompt) / 3.3 + a.num_predict + 512
        a.num_ctx = int(-(-need // 2048) * 2048)
    t0 = time.time()
    if a.backend == "gemini":
        # Gemini's defaults (temperature 1.0) are what Google recommends for thinking models.
        resp = call_gemini(a.model, prompt, a.thinking_level if a.think else "minimal", None)
        options = {"thinking_level": a.thinking_level if a.think else "minimal"}
        a.num_ctx = None
    else:
        resp = call_ollama(a.host, a.model, prompt, a.think, a.num_ctx, options)
    elapsed = time.time() - t0

    try:
        answer = json.loads(resp.get("response", ""))
    except json.JSONDecodeError:
        answer = {"_parse_error": resp.get("response", "")[:2000]}

    text_norm = norm(raw)
    for k, v in answer.items():
        if isinstance(v, dict):
            v["quote_match"] = quote_found(str(v.get("evidence", "")), text_norm)

    out = {
        "paper": a.paper,
        "backend": a.backend,
        "model": a.model,
        "think": a.think,
        "elapsed_s": round(elapsed, 1),
        "done_reason": resp.get("done_reason"),
        "num_ctx": a.num_ctx,
        "options": options,
        "prompt_tokens": resp.get("prompt_eval_count"),
        "output_tokens": resp.get("eval_count"),
        "thinking_chars": len(resp.get("thinking", "") or ""),
        "chars_sent": len(text),
        "sections_dropped": dropped,
        "missing_fields": [k for k in FIELDS if k not in answer],
        "fields": answer,
    }
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    if resp.get("thinking"):
        Path(a.out).with_suffix(".thinking.txt").write_text(resp["thinking"], encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("paper", "think", "elapsed_s", "done_reason", "num_ctx", "prompt_tokens",
                                           "output_tokens", "thinking_chars", "missing_fields")}))


if __name__ == "__main__":
    main()
