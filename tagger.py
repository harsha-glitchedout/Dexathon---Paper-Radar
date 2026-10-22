"""Step 2b: an LLM reads a paper and tags each question with a syllabus topic.

Important design rule from the deck: the LLM only READS and TAGS.
Counting happens in analyzer.py with plain pandas. The LLM can only choose
topics from the official syllabus list; anything else becomes UNMAPPED.

Two providers are supported:
  - Anthropic (keys start with sk-ant-)       -> tag_paper(...)
  - OpenRouter (keys start with sk-or-)       -> tag_paper_openrouter(...)
"""
import json
import os
import re
import urllib.error
import urllib.request

from syllabus import topic_to_unit

def _anthropic_model():
    return os.getenv("PAPER_RADAR_MODEL", "claude-haiku-5-5")


def _openrouter_model():
    # set PAPER_RADAR_OPENROUTER_MODEL to a model id such as one ending in :free; default lets OpenRouter pick
    return os.getenv("PAPER_RADAR_OPENROUTER_MODEL", "openrouter/auto")
MAX_CHARS = 40000  # a question paper is short, this is just a safety limit
UNMAPPED = "UNMAPPED"

SYSTEM_PROMPT = """You extract exam questions from past question paper text.
Return ONLY a JSON array, no explanation, no markdown fences.
Each item must look like:
{"q_no": "1a", "question": "full question text", "marks": 2, "topic": "<exact topic from the allowed list>"}
Rules:
- Include every question and sub-question you can find.
- marks must be a number. If the paper does not show marks, use 0.
- topic MUST be copied exactly from the allowed topic list. Pick the closest one.
- If no allowed topic fits at all, use "UNMAPPED".
- Do not invent questions that are not in the text."""


def _parse_json_array(text):
    text = text.strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("Model did not return a JSON array.")
    return json.loads(text[start:end + 1])


def _clean_topic(raw, allowed_lower):
    """Match the model's topic to the official list, ignoring case/spacing."""
    key = re.sub(r"\s+", " ", str(raw)).strip().lower()
    return allowed_lower.get(key, UNMAPPED)


def _user_message(paper_text, syllabus, t2u):
    topic_list = "\n".join(f"- {t}" for t in t2u)
    return (
        f"Subject: {syllabus.get('subject', '')}\n"
        f"Allowed topics:\n{topic_list}\n\n"
        f"Question paper text:\n{paper_text[:MAX_CHARS]}"
    )


def _ask_until_json(ask):
    """ask() returns the model's text. One retry if the JSON is broken."""
    for attempt in range(2):
        try:
            return _parse_json_array(ask())
        except (ValueError, json.JSONDecodeError):
            if attempt == 1:
                raise RuntimeError("Could not read the model's answer as JSON. Try again.")


def _to_rows(items, t2u):
    allowed_lower = {t.lower(): t for t in t2u}
    rows = []
    for it in items:
        topic = _clean_topic(it.get("topic", ""), allowed_lower)
        try:
            marks = float(it.get("marks", 0) or 0)
        except (TypeError, ValueError):
            marks = 0.0
        rows.append({
            "q_no": str(it.get("q_no", "")),
            "question": str(it.get("question", "")).strip(),
            "marks": marks,
            "topic": topic,
            "unit": t2u.get(topic, UNMAPPED),  # unit comes from code, not the LLM
        })
    return rows


def _get_anthropic_client():
    from anthropic import Anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("No ANTHROPIC_API_KEY found. Put it in .env or the sidebar box.")
    return Anthropic(api_key=key)


def tag_paper(paper_text, syllabus, client=None):
    """Anthropic version. Returns a list of dicts: q_no, question, marks, topic, unit."""
    client = client or _get_anthropic_client()
    t2u = topic_to_unit(syllabus)
    user_msg = _user_message(paper_text, syllabus, t2u)

    def ask():
        resp = client.messages.create(
            model=_anthropic_model(), max_tokens=6000, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return resp.content[0].text

    return _to_rows(_ask_until_json(ask), t2u)


def tag_paper_openrouter(paper_text, syllabus, api_key):
    """OpenRouter version (keys start with sk-or-). Same output as tag_paper."""
    t2u = topic_to_unit(syllabus)
    user_msg = _user_message(paper_text, syllabus, t2u)
    payload = json.dumps({
        "model": _openrouter_model(),
        "max_tokens": 6000,
        "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user_msg}],
    }).encode("utf-8")

    def ask():
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=payload, method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "X-Title": "Paper Radar"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            hint = {401: "the key was rejected", 402: "the account has no credits",
                    429: "too many requests, wait a moment"}.get(e.code, "request failed")
            raise RuntimeError(f"OpenRouter error {e.code}: {hint}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Could not reach OpenRouter ({e.reason}). Check the internet connection.")
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("OpenRouter sent an answer in an unexpected shape.")
        if isinstance(content, list):  # some models return a list of text parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not content or not content.strip():
            raise RuntimeError("The model returned an empty answer (a reasoning model may have used all its "
                               "tokens thinking). Try another model.")
        return content

    return _to_rows(_ask_until_json(ask), t2u)
