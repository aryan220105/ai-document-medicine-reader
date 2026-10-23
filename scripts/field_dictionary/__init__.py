"""Source of truth for the multilingual common-field dictionary.

The runtime reads the generated ``backend/knowledge_base/common_fields.json``. Editing
happens here so that the four language columns for a field stay side by side and a
reviewer can see at a glance when one is missing.
"""

from __future__ import annotations

from typing import Any

LANGUAGES = ("en", "hi", "kn", "ur")


def t(en: str, hi: str, kn: str, ur: str) -> dict[str, str]:
    return {"en": en, "hi": hi, "kn": kn, "ur": ur}


def entry(
    field_id: str,
    field_type: str,
    aliases: dict[str, list[str]],
    simple_label: dict[str, str],
    what_to_enter: dict[str, str],
    why_needed: dict[str, str] | None = None,
    example: str | None = None,
    format_hint: dict[str, str] | None = None,
    validation: dict[str, Any] | None = None,
    keywords: dict[str, list[str]] | None = None,
    priority: float = 1.0,
) -> dict[str, Any]:
    for language in LANGUAGES:
        if language not in aliases:
            raise ValueError(f"{field_id}: aliases missing {language}")
        for label in (simple_label, what_to_enter):
            if language not in label:
                raise ValueError(f"{field_id}: text missing {language}")
    return {
        "id": field_id,
        "type": field_type,
        "aliases": aliases,
        "keywords": keywords or {},
        "simple_label": simple_label,
        "what_to_enter": what_to_enter,
        "why_needed": why_needed or {},
        "example": example,
        "format_hint": format_hint or {},
        "validation": validation or {"kind": "non_empty"},
        "priority": priority,
        "source_reference": "FormSathi common-field dictionary (general guidance, not official instructions)",
    }
