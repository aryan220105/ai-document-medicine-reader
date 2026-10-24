from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from typing import Any

from app.config import Settings
from app.models.common import ALL_LANGUAGES, Language
from app.utils.text_normalization import fold_for_match, match_tokens


@dataclass(frozen=True)
class Alias:
    """One printed wording for a field, pre-folded so matching does no work per request."""

    text: str
    folded: str
    tokens: tuple[str, ...]
    language: Language

    @property
    def length(self) -> int:
        return len(self.tokens)


@dataclass
class DictionaryEntry:
    id: str
    field_type: str
    priority: float
    aliases: tuple[Alias, ...]
    keywords: tuple[Alias, ...]
    simple_label: dict[str, str]
    what_to_enter: dict[str, str]
    why_needed: dict[str, str] = dataclass_field(default_factory=dict)
    example: str | None = None
    example_by_language: dict[str, str] = dataclass_field(default_factory=dict)
    format_hint: dict[str, str] = dataclass_field(default_factory=dict)
    validation: dict[str, Any] = dataclass_field(default_factory=dict)
    source_reference: str = ""

    def text(self, key: str, language: Language) -> str | None:
        mapping = getattr(self, key, None) or {}
        return mapping.get(language.value) or mapping.get(Language.ENGLISH.value) or None

    def example_for(self, language: Language) -> str | None:
        """The worked example, in the reader's own script where that matters.

        A date or a PIN code reads the same in every language, so one string serves. A
        person's name does not: showing "Ananya Rao" in Latin letters beside Kannada
        guidance asks the reader to switch script mid-sentence for no reason.
        """
        localised = (self.example_by_language or {}).get(language.value)
        return localised or self.example


@dataclass
class LabelPattern:
    id: str
    field_type: str
    weight: float
    markers: tuple[Alias, ...]
    what_to_enter: dict[str, str]
    validation: dict[str, Any]
    format_hint: dict[str, str]

    def text(self, key: str, language: Language) -> str | None:
        mapping = getattr(self, key, None) or {}
        return mapping.get(language.value) or mapping.get(Language.ENGLISH.value) or None


def _aliases(raw: dict[str, list[str]]) -> tuple[Alias, ...]:
    built: list[Alias] = []
    for language in ALL_LANGUAGES:
        for text in raw.get(language.value, []) or []:
            folded = fold_for_match(text)
            if not folded:
                continue
            built.append(Alias(text=text, folded=folded, tokens=tuple(match_tokens(text)), language=language))
    # Longest first so a specific wording is tried before a generic one.
    built.sort(key=lambda item: -item.length)
    return tuple(built)


class FieldDictionaryRepository:
    """Loads the generated multilingual common-field dictionary and label patterns."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.entries: list[DictionaryEntry] = []
        self.patterns: list[LabelPattern] = []
        self.inferred_note: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self.entries = [self._entry(raw) for raw in self._load("common_fields.json", [])]
        payload = self._load("label_patterns.json", {})
        self.inferred_note = payload.get("inferred_note", {}) if isinstance(payload, dict) else {}
        raw_patterns = payload.get("patterns", []) if isinstance(payload, dict) else []
        self.patterns = [self._pattern(raw) for raw in raw_patterns]

    def _load(self, name: str, default: Any) -> Any:
        path = self.settings.knowledge_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _entry(raw: dict[str, Any]) -> DictionaryEntry:
        aliases = raw.get("aliases", {})
        # Tolerate the pre-multilingual flat alias list so an older knowledge base still loads.
        if isinstance(aliases, list):
            aliases = {Language.ENGLISH.value: aliases}
        keywords = raw.get("keywords", {}) or {}
        if isinstance(keywords, list):
            keywords = {Language.ENGLISH.value: keywords}
        return DictionaryEntry(
            id=raw["id"],
            field_type=raw.get("type", "text"),
            priority=float(raw.get("priority", 1.0)),
            aliases=_aliases(aliases),
            keywords=_aliases(keywords),
            simple_label=raw.get("simple_label", {}) or {},
            what_to_enter=raw.get("what_to_enter", {}) or {},
            why_needed=raw.get("why_needed", {}) or {},
            example=raw.get("example"),
            example_by_language=raw.get("example_by_language", {}) or {},
            format_hint=raw.get("format_hint", {}) or {},
            validation=raw.get("validation", {}) or {},
            source_reference=raw.get("source_reference", ""),
        )

    @staticmethod
    def _pattern(raw: dict[str, Any]) -> LabelPattern:
        return LabelPattern(
            id=raw["id"],
            field_type=raw.get("type", "text"),
            weight=float(raw.get("weight", 1.0)),
            markers=_aliases(raw.get("markers", {}) or {}),
            what_to_enter=raw.get("what_to_enter", {}) or {},
            validation=raw.get("validation", {}) or {},
            format_hint=raw.get("format_hint", {}) or {},
        )

    def get(self, entry_id: str) -> DictionaryEntry | None:
        return next((entry for entry in self.entries if entry.id == entry_id), None)

    def pattern(self, pattern_id: str) -> LabelPattern | None:
        return next((item for item in self.patterns if item.id == pattern_id), None)

    def note(self, language: Language) -> str:
        return self.inferred_note.get(language.value) or self.inferred_note.get(Language.ENGLISH.value, "")

    def chunks(self) -> list[dict[str, Any]]:
        """Dictionary rows as retrieval chunks, so the vector store covers unknown forms
        too and not only the four seeded known forms."""
        chunks: list[dict[str, Any]] = []
        for entry in self.entries:
            for language in ALL_LANGUAGES:
                aliases = [alias.text for alias in entry.aliases if alias.language == language]
                what = entry.text("what_to_enter", language) or ""
                why = entry.text("why_needed", language) or ""
                label = entry.text("simple_label", language) or entry.id
                chunks.append(
                    {
                        "id": f"common:{entry.id}:{language.value}",
                        "text": " ".join([label, " ".join(aliases), what, why]).strip(),
                        "metadata": {
                            "form_id": "",
                            "display_name": "Common field dictionary",
                            "field_id": entry.id,
                            "language": language.value,
                            "category": "other",
                            "source": "common_field_dictionary",
                            "source_reference": entry.source_reference,
                            "simple_label": label,
                            "what_to_enter": what,
                            "why_needed": why,
                            "example": entry.example,
                            "type": entry.field_type,
                        },
                    }
                )
        return chunks
