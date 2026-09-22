from __future__ import annotations

import re
import unicodedata


WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text or "")
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def fold(text: str) -> str:
    return normalize_text(text).lower()


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))
