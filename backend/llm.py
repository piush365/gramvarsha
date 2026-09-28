"""Optional LLM polish of the rule-based advisory (Groq free tier).

Only active when GROQ_API_KEY is set. The LLM may reword, never change facts:
every number in the rule text must appear in the rewrite, otherwise the rule text
is used. Any error or timeout also falls back silently to the rule text.
"""
from __future__ import annotations

import logging
import os
import re

import requests

log = logging.getLogger("gramvarsha.llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
LANG_NAME = {"en": "English", "hi": "Hindi (Devanagari)", "mr": "Marathi (Devanagari)"}


def numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text)


def keeps_facts(original: str, rewrite: str) -> bool:
    """Every number in the original must still be present in the rewrite."""
    have = numbers(rewrite)
    return all(n in have for n in numbers(original))


def polish(rule_text: str, lang: str) -> str | None:
    """Return a friendlier 2-sentence version, or None to use the rule text."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    try:
        r = requests.post(GROQ_URL, timeout=8, headers={"Authorization": f"Bearer {key}"}, json={
            "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "temperature": 0.2,
            "max_tokens": 200,
            "messages": [
                {"role": "system", "content":
                    f"You rewrite farm weather advisories for small farmers in simple, warm, spoken "
                    f"{LANG_NAME[lang]}. Exactly 2 short sentences. Keep every number and every action "
                    f"exactly as given. Do not add advice, chemicals or numbers. No English words in "
                    f"Hindi/Marathi output. Output only the message."},
                {"role": "user", "content": rule_text},
            ],
        })
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        if not keeps_facts(rule_text, text):
            log.warning("LLM rewrite dropped/changed a number; using rule text")
            return None
        return text
    except Exception as e:  # never let the LLM break the advisory
        log.warning("LLM polish failed (%s); using rule text", e)
        return None
