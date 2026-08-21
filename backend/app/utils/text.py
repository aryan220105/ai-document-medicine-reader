from __future__ import annotations

import re
import unicodedata


WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text or "")
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def fold(text: str) -> str:
    return normalize_text(text).lower()


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9₹./:-]+", text)


def snippet(text: str, limit: int = 180) -> str:
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
