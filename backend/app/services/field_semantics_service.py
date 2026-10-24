from __future__ import annotations

from dataclasses import dataclass

from app.models.common import FieldType, Language
from app.models.fields import ValidationRule
from app.repositories.field_dictionary_repository import (
    Alias,
    DictionaryEntry,
    FieldDictionaryRepository,
    LabelPattern,
)
from app.utils.text_normalization import (
    contains_token_sequence,
    dominant_script,
    fold_for_match,
    fuzzy_sequence_match,
    language_for_script,
    match_tokens,
    similarity,
)

# Marks the boundary between "confident enough to present as dictionary guidance" and
# "show it but tell the user to verify".
CONFIDENT = 0.74
PLAUSIBLE = 0.52

FUZZY_FLOOR = 0.84

TYPE_MAP = {
    "text": FieldType.TEXT,
    "multiline": FieldType.MULTILINE,
    "date": FieldType.DATE,
    "checkbox": FieldType.CHECKBOX,
    "radio": FieldType.RADIO,
    "signature": FieldType.SIGNATURE,
    "table": FieldType.TABLE_CELL,
    "table_cell": FieldType.TABLE_CELL,
}

MARK_TYPES = {FieldType.CHECKBOX, FieldType.RADIO}


@dataclass
class SemanticMatch:
    entry: DictionaryEntry
    score: float
    matched_alias: str
    matched_language: Language
    how: str

    @property
    def confident(self) -> bool:
        return self.score >= CONFIDENT


@dataclass
class PatternMatch:
    pattern: LabelPattern
    score: float
    matched_marker: str
    matched_language: Language


class FieldSemanticsService:
    """Resolves a printed label, in any supported script, to a dictionary field.

    Matching is deliberately layered: an exact wording wins outright, a contained wording
    scores by how much of the label it explains, and only then does character similarity
    get a say -- that last layer is what carries noisy scans, and it is capped below the
    exact-match band so a smudged guess can never outrank a clean reading.
    """

    def __init__(self, dictionary: FieldDictionaryRepository) -> None:
        self.dictionary = dictionary

    def resolve(self, label: str, field_type: FieldType | None = None) -> SemanticMatch | None:
        folded = fold_for_match(label)
        if not folded:
            return None
        label_tokens = match_tokens(label)
        best: SemanticMatch | None = None
        for entry in self.dictionary.entries:
            candidate = self._score_entry(entry, folded, label_tokens, field_type)
            if candidate is None:
                continue
            if best is None or self._better(candidate, best):
                best = candidate
        if best is None or best.score < PLAUSIBLE or best.how == "weak_token":
            # A lone generic word such as "name" or "کام" does not identify the field.
            # The pattern layer describes the shape of the answer without naming the wrong one.
            return None
        return best

    @staticmethod
    def _better(candidate: SemanticMatch, incumbent: SemanticMatch) -> bool:
        if abs(candidate.score - incumbent.score) > 0.02:
            return candidate.score > incumbent.score
        # Near-equal scores: the wording that explains more of the label wins, so
        # "bank name" does not lose to the bare alias "name".
        return len(match_tokens(candidate.matched_alias)) > len(match_tokens(incumbent.matched_alias))

    def _score_entry(
        self,
        entry: DictionaryEntry,
        folded: str,
        label_tokens: list[str],
        field_type: FieldType | None,
    ) -> SemanticMatch | None:
        best: tuple[float, Alias, str] | None = None
        for alias in entry.aliases:
            score, how = self._score_alias(alias, folded, label_tokens)
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, alias, how)
        if best is None:
            keyword = self._score_keywords(entry, label_tokens)
            if keyword is None:
                return None
            best = keyword
        score = min(1.0, best[0] * entry.priority)
        score = self._apply_type_agreement(score, entry, field_type)
        return SemanticMatch(
            entry=entry,
            score=round(score, 4),
            matched_alias=best[1].text,
            matched_language=best[1].language,
            how=best[2],
        )

    def _score_alias(self, alias: Alias, folded: str, label_tokens: list[str]) -> tuple[float, str]:
        if alias.folded == folded:
            return 1.0, "exact"
        if contains_token_sequence(folded, alias.text):
            # A single generic token inside a longer label explains almost nothing:
            # "bank" sits inside "bank account number", and "name" inside "brother name".
            # Treating those as confident hits would hand the user the wrong definition,
            # so they are demoted below the plausible floor and the label-pattern
            # heuristic answers instead -- it describes the shape of the answer without
            # claiming to know which field it is.
            if alias.length == 1 and len(label_tokens) >= 2:
                return 0.50, "weak_token"
            coverage = alias.length / max(len(label_tokens), 1)
            return min(0.95, 0.58 + 0.37 * min(coverage, 1.0)), "contains"
        if contains_token_sequence(alias.text, folded) and len(label_tokens) >= 2:
            return 0.74, "contained_by"
        # Token-aligned fuzzy match: this is the layer that carries noisy scans, where
        # Tesseract substitutes a character or two per word.
        aligned = fuzzy_sequence_match(label_tokens, list(alias.tokens))
        if aligned > 0:
            coverage = alias.length / max(len(label_tokens), 1)
            return 0.58 + 0.14 * (aligned - 0.80) / 0.20 + 0.04 * min(coverage, 1.0), "fuzzy_tokens"
        # Deliberately no whole-string fuzzy layer below this point. Comparing the label
        # and the alias as single run-together strings judges "acnumber" to be close
        # enough to "accountnumber", so an Assembly Constituency number on an electoral
        # form resolved to a bank account and the user was told to copy it from their
        # passbook. Token alignment above already absorbs the per-word substitutions that
        # real OCR makes, and it refuses this one because "ac" and "account" differ by
        # five characters.
        return 0.0, ""

    def _score_keywords(self, entry: DictionaryEntry, label_tokens: list[str]) -> tuple[float, Alias, str] | None:
        if not entry.keywords or not label_tokens:
            return None
        present = set(label_tokens)
        for keyword in entry.keywords:
            if not keyword.tokens:
                continue
            if all(token in present for token in keyword.tokens):
                return 0.56, keyword, "keyword"
            # A single noisy keyword token still counts, at a lower score.
            if len(keyword.tokens) == 1 and any(similarity(token, keyword.tokens[0]) >= 0.9 for token in label_tokens):
                return 0.53, keyword, "keyword_fuzzy"
        return None

    @staticmethod
    def _apply_type_agreement(score: float, entry: DictionaryEntry, field_type: FieldType | None) -> float:
        if field_type is None:
            return score
        expected = TYPE_MAP.get(entry.field_type, FieldType.TEXT)
        if expected == field_type:
            return min(1.0, score + 0.04)
        # Geometry saw a tick box but the dictionary row is free text, or the reverse.
        # Treat that as evidence against the row without discarding it.
        if (field_type in MARK_TYPES) != (expected in MARK_TYPES):
            return score - 0.08
        if {field_type, expected} <= {FieldType.TEXT, FieldType.MULTILINE, FieldType.DATE}:
            return score - 0.01
        return score - 0.04

    def match_pattern(self, label: str, field_type: FieldType | None = None) -> PatternMatch | None:
        """Last offline resort: recognise the shape of the answer from the wording alone.

        `field_type` is accepted so callers can treat this like `resolve`; the printed
        wording alone decides a pattern, because the geometry has already been consulted
        by the time we fall this far.
        """
        del field_type
        folded = fold_for_match(label)
        if not folded:
            return None
        label_tokens = match_tokens(label)
        best: PatternMatch | None = None
        for item in self.dictionary.patterns:
            for marker in item.markers:
                hit = 0.0
                if marker.folded == folded:
                    hit = 0.72
                elif contains_token_sequence(folded, marker.text):
                    hit = 0.60 + 0.08 * min(marker.length / max(len(label_tokens), 1), 1.0)
                elif marker.length == 1 and any(similarity(token, marker.folded) >= 0.9 for token in label_tokens):
                    hit = 0.52
                if hit <= 0:
                    continue
                score = min(0.9, hit * item.weight)
                if best is None or score > best.score:
                    best = PatternMatch(
                        pattern=item,
                        score=round(score, 4),
                        matched_marker=marker.text,
                        matched_language=marker.language,
                    )
        return best

    def field_type_for(self, entry_type: str, detected: FieldType) -> FieldType:
        """Geometry decides tick boxes; the dictionary decides everything else.

        A detected checkbox is a checkbox whatever the wording says, because a mark was
        actually measured on the page. For free-text regions the printed wording is the
        better signal, so a box labelled 'Date of birth' becomes a date field.
        """
        expected = TYPE_MAP.get(entry_type, FieldType.TEXT)
        if detected in MARK_TYPES:
            return detected
        if expected in MARK_TYPES:
            return detected
        return expected

    @staticmethod
    def validation_rule(raw: dict) -> ValidationRule | None:
        if not raw:
            return None
        return ValidationRule(
            kind=str(raw.get("kind", "non_empty")),
            pattern=raw.get("pattern"),
            message=raw.get("message"),
            format=raw.get("format"),
            optional=bool(raw.get("optional", False)),
            min_value=raw.get("min"),
            max_value=raw.get("max"),
            max_length=raw.get("max_length"),
        )

    def label_language(self, label: str) -> Language:
        """Which language the printed label is written in. Used to pick a sensible default
        explanation language -- never to translate the form itself."""
        code = language_for_script(dominant_script(label))
        try:
            return Language(code)
        except ValueError:
            return Language.ENGLISH
