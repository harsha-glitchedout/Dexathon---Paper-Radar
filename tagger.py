"""Step 2b: the LLM reads a paper and tags each question with a syllabus topic.

Important design rule from the deck: the LLM only READS and TAGS.
Counting happens in analyzer.py with plain pandas. The LLM can only choose
topics from the official syllabus list; anything else becomes UNMAPPED.
"""
import json
import os
import re

from syllabus import topic_to_unit

MODEL = os.getenv("PAPER_RADAR_MODEL", "claude-haiku-5-5")
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


def _get_client():
    from anthropic import Anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("No ANTHROPIC_API_KEY found. Put it in .env or the sidebar box.")
    return Anthropic(api_key=key)


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


def tag_paper(paper_text, syllabus, client=None):
    """Returns a list of dicts: q_no, question, marks, topic, unit."""
    client = client or _get_client()
    t2u = topic_to_unit(syllabus)
    allowed_lower = {t.lower(): t for t in t2u}
    topic_list = "\n".join(f"- {t}" for t in t2u)

    user_msg = (
        f"Subject: {syllabus.get('subject', '')}\n"
        f"Allowed topics:\n{topic_list}\n\n"
        f"Question paper text:\n{paper_text[:MAX_CHARS]}"
    )

    items = None
    for attempt in range(2):  # one retry if JSON is broken
        resp = client.messages.create(
            model=MODEL, max_tokens=6000, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        try:
            items = _parse_json_array(resp.content[0].text)
            break
        except (ValueError, json.JSONDecodeError):
            if attempt == 1:
                raise RuntimeError("Could not read the model's answer as JSON. Try again.")

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
