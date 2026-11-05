"""Source of truth for the multilingual common-field dictionary.

The runtime reads the generated ``backend/knowledge_base/common_fields.json``. Editing
happens here so that the core four language columns for a field stay side by side and a
reviewer can see at a glance when one is missing; additional Indian languages are filled
from ``extra_locales.py`` at build time.
"""

from __future__ import annotations

from typing import Any

from .extra_locales import EXTRA
from .pattern_extras import INFERRED_NOTE as PATTERN_INFERRED_NOTE
from .pattern_extras import MARKERS as PATTERN_MARKERS
from .pattern_extras import PATTERN_WHAT

LANGUAGES = ("en", "hi", "kn", "ur", "bn", "te", "mr", "ta", "gu", "ml", "or", "pa", "as")
CORE_LANGUAGES = ("en", "hi", "kn", "ur")


def t(en: str, hi: str, kn: str, ur: str) -> dict[str, str]:
    return {"en": en, "hi": hi, "kn": kn, "ur": ur}


def _merge_list(existing: list[str] | None, extra: list[str] | None) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in (existing or []) + (extra or []):
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item.strip())
    return merged


def fill_text_map(mapping: dict[str, str]) -> dict[str, str]:
    for lang in LANGUAGES:
        if not (mapping.get(lang) or "").strip():
            mapping[lang] = PATTERN_INFERRED_NOTE.get(lang) or mapping.get("en") or ""
    return mapping


def fill_missing_languages(item: dict[str, Any]) -> dict[str, Any]:
    """Ensure every supported language is present on dictionary entries and patterns."""
    field_id = item.get("id", "")
    extra_root = EXTRA.get(field_id, {})
    is_pattern = "markers" in item
    why = item.get("why_needed") or {}
    needs_why = bool(why)
    pattern_what = PATTERN_WHAT.get(field_id, {}) if is_pattern else {}
    pattern_markers = PATTERN_MARKERS.get(field_id, {}) if is_pattern else {}

    for lang in LANGUAGES:
        extra_lang = extra_root.get(lang, {})

        if not is_pattern:
            for key in ("simple_label", "what_to_enter"):
                bucket = item.setdefault(key, {})
                if not (bucket.get(lang) or "").strip():
                    native = (extra_lang.get(key) or "").strip()
                    bucket[lang] = native or (bucket.get("en") or "")

        if "what_to_enter" in item and is_pattern:
            bucket = item.setdefault("what_to_enter", {})
            if not (bucket.get(lang) or "").strip() or (
                lang not in CORE_LANGUAGES and bucket.get(lang) == bucket.get("en")
            ):
                native = (pattern_what.get(lang) or extra_lang.get("what_to_enter") or "").strip()
                if native:
                    bucket[lang] = native
                elif not (bucket.get(lang) or "").strip():
                    bucket[lang] = bucket.get("en") or ""

        if item.get("format_hint") is not None or extra_lang.get("format_hint"):
            bucket = item.setdefault("format_hint", {})
            if not (bucket.get(lang) or "").strip():
                native = (extra_lang.get("format_hint") or "").strip()
                bucket[lang] = native or (bucket.get("en") or "")

        if needs_why:
            bucket = item.setdefault("why_needed", {})
            if not (bucket.get(lang) or "").strip():
                native = (extra_lang.get("why_needed") or "").strip()
                bucket[lang] = native or (bucket.get("en") or "")

        if "aliases" in item:
            aliases = item.setdefault("aliases", {})
            native_aliases = extra_lang.get("aliases")
            if not aliases.get(lang):
                # Prefer authored regional aliases. Only fall back to English when none exist.
                aliases[lang] = _merge_list(native_aliases, None) if native_aliases else list(aliases.get("en") or [])
            else:
                aliases[lang] = _merge_list(aliases.get(lang), native_aliases)

        if "keywords" in item:
            keywords = item.setdefault("keywords", {})
            native_keywords = extra_lang.get("keywords")
            if not keywords.get(lang):
                keywords[lang] = list(native_keywords or [])
            else:
                keywords[lang] = _merge_list(keywords.get(lang), native_keywords)

        if "markers" in item:
            markers = item.setdefault("markers", {})
            native_markers = pattern_markers.get(lang) or extra_lang.get("markers")
            if native_markers:
                markers[lang] = list(native_markers)
            elif not markers.get(lang):
                markers[lang] = list(markers.get("en") or [])

    return item


def entry(
    field_id: str,
    field_type: str,
    aliases: dict[str, list[str]],
    simple_label: dict[str, str],
    what_to_enter: dict[str, str],
    why_needed: dict[str, str] | None = None,
    example: str | None = None,
    example_by_language: dict[str, str] | None = None,
    format_hint: dict[str, str] | None = None,
    validation: dict[str, Any] | None = None,
    keywords: dict[str, list[str]] | None = None,
    priority: float = 1.0,
) -> dict[str, Any]:
    for language in CORE_LANGUAGES:
        if language not in aliases:
            raise ValueError(f"{field_id}: aliases missing {language}")
        for label in (simple_label, what_to_enter):
            if language not in label:
                raise ValueError(f"{field_id}: text missing {language}")
    built = {
        "id": field_id,
        "type": field_type,
        "aliases": aliases,
        "keywords": keywords or {},
        "simple_label": simple_label,
        "what_to_enter": what_to_enter,
        "why_needed": why_needed or {},
        "example": example,
        "example_by_language": example_by_language or {},
        "format_hint": format_hint or {},
        "validation": validation or {"kind": "non_empty"},
        "priority": priority,
        "source_reference": "FormSathi common-field dictionary (general guidance, not official instructions)",
    }
    return fill_missing_languages(built)
