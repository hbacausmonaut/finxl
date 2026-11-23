"""
llm_extract.py
--------------
Optional AI fallback for statements the free parser can't read cleanly.
Two free options:
  - Gemini API  (free tier key from https://aistudio.google.com/apikey)
  - Ollama      (runs Gemma / Qwen / Llama locally, no key, no internet)

Both get the statement's text and return the same JSON shape that
ar_extract.parse_statement() returns, so the rest of the pipeline doesn't care.
"""

import base64
import json
import re
import time
import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Google retires model names over time and the free tier is often busy (503/429).
# "-latest" aliases don't get retired; the others are backups tried in order.
GEMINI_MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-flash-lite-latest"]
RETRYABLE = (429, 500, 503, 504)
OLLAMA_URL = "http://localhost:11434/api/chat"

PROMPT = """You are extracting a financial statement from an Indian company's annual report.
Statement: {kind_name} ({scope}). Report for financial year ending March {fy}.

You get an image of each statement page plus the text extracted from the PDF,
line by line. The text may have extraction errors (missing digits, garbled words);
when the text and the image disagree, trust the image.
Return ONLY JSON in this exact shape:
{{
  "unit": "crore" | "lakh" | "million" | "thousand" | null,
  "years": [<4-digit fiscal year of each value column, current year first>],
  "rows": [
    {{"label": "<line item, without note numbers or (a)/(i) prefixes>",
      "level": <0 for main items, 1 for sub-items, 2 for sub-sub-items>,
      "is_header": <true if the line is a section heading with no amounts>,
      "values": [<number or null for each year in "years">]}}
  ]
}}
Rules:
- Keep every line item in the original order, including totals and section headings.
- Numbers in brackets (1,234.56) are negative. "-" means null.
- Do NOT include the "Note" reference column as a value.
- Do not invent or compute numbers; copy them exactly.

STATEMENT TEXT:
{text}
"""


def _parse_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    return json.loads(s)


def _normalise(data):
    years = [int(y) for y in data.get("years", []) if str(y).isdigit()]
    rows = []
    for r in data.get("rows", []):
        vals = list(r.get("values") or [])
        vals = [(float(v) if isinstance(v, (int, float)) else None) for v in vals]
        vals = (vals + [None] * len(years))[:len(years)]
        rows.append({
            "label": str(r.get("label", "")).strip(),
            "level": int(r.get("level", 0) or 0),
            "is_header": bool(r.get("is_header")) or all(v is None for v in vals),
            "values": vals,
        })
    return {"unit": data.get("unit"), "years": years, "ncols": len(years),
            "rows": [r for r in rows if r["label"]]}


def _gemini_once(prompt, api_key, model, images=(), timeout=300):
    parts = [{"inline_data": {"mime_type": "image/png", "data": base64.b64encode(img).decode()}}
             for img in images]
    parts.append({"text": prompt})
    r = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        err = RuntimeError(f"Gemini error {r.status_code} ({model}): {r.text[:300]}")
        err.retryable = r.status_code in RETRYABLE or r.status_code == 404  # 404 = model retired
        raise err
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def call_gemini(prompt, api_key, model=None, images=(), timeout=300, log=print):
    """Try the requested model, then the backups; retry once per model when Google is busy."""
    models = [model] + [m for m in GEMINI_MODELS if m != model] if model else GEMINI_MODELS
    last = None
    for m in models:
        for attempt in range(2):
            try:
                return _gemini_once(prompt, api_key, m, images, timeout)
            except requests.exceptions.RequestException as e:  # timeout / connection drop
                last = e
            except RuntimeError as e:
                last = e
                if not getattr(e, "retryable", False):
                    raise
                if "404" in str(e):
                    break
            log(f"      Gemini {m} busy/unavailable, {'retrying' if attempt == 0 else 'trying next model'}")
            time.sleep(10 if attempt == 0 else 0)
    raise RuntimeError(f"All Gemini models failed; last error: {last}")


def call_ollama(prompt, model, images=(), url=OLLAMA_URL):
    msg = {"role": "user", "content": prompt}
    if images:  # vision models only (gemma3, qwen2.5vl, llama3.2-vision ...)
        msg["images"] = [base64.b64encode(img).decode() for img in images]
    r = requests.post(
        url,
        json={
            "model": model,
            "messages": [msg],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 16384},
        },
        timeout=900,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Ollama error {r.status_code}: {r.text[:300]}")
    return r.json()["message"]["content"]


def extract_with_llm(text, kind_name, scope, fy, backend, api_key=None, model=None, images=()):
    """backend: 'gemini' or 'ollama'. images: PNG bytes of the statement pages. Returns parsed statement dict."""
    prompt = PROMPT.format(kind_name=kind_name, scope=scope, fy=fy, text=text[:60000])
    if backend == "gemini":
        raw = call_gemini(prompt, api_key, model, images)
    elif backend == "ollama":
        raw = call_ollama(prompt, model or "gemma3:12b", images)
    else:
        raise ValueError(f"unknown backend {backend}")
    return _normalise(_parse_json(raw))


def check_backend(backend, api_key=None, model=None):
    """Quick connectivity test used by the UI. Returns (ok, message)."""
    try:
        if backend == "gemini":
            if not api_key:
                return False, "No Gemini API key"
            call_gemini('Reply with {"ok": true}', api_key, model, timeout=120, log=lambda *_: None)
            return True, "Gemini reachable"
        if backend == "ollama":
            tags = requests.get(OLLAMA_URL.replace("/api/chat", "/api/tags"), timeout=5).json()
            names = [m["name"] for m in tags.get("models", [])]
            if model and not any(n.startswith(model.split(":")[0]) for n in names):
                return False, f"Ollama is running but '{model}' isn't pulled. Run: ollama pull {model}"
            return True, f"Ollama running ({', '.join(names[:5]) or 'no models'})"
    except Exception as e:
        return False, str(e)
    return False, "No backend"
