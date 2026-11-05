from pydantic import BaseModel, Field

from app.models.common import DocumentCategory, GuidanceSource, Language, NormalizedBoundingBox
from app.models.fields import ValidationRule


class FieldGuidance(BaseModel):
    field_id: str
    language: Language
    simple_label: str
    what_to_enter: str
    why_needed: str | None = None
    example: str | None = None
    format_hint: str | None = None
    validation_rule: ValidationRule | None = None
    source: GuidanceSource
    source_reference: str | None = None
    confidence: float
    requires_verification: bool = False
    highlights: list[NormalizedBoundingBox] = Field(default_factory=list)

    # Set when the description was inferred from the printed wording rather than looked
    # up, so the interface can say so instead of presenting a guess as a definition.
    inferred: bool = False
    verify_notice: str | None = None

    @property
    def direction(self) -> str:
        return self.language.direction


class MultilingualFieldGuidance(BaseModel):
    """Guidance for one field in every supported language at once.

    The frontend holds the whole bundle, so switching explanation language is instant and
    needs no further request. Nothing here describes the uploaded form's own text, which
    is never translated.
    """

    field_id: str
    semantic_id: str | None = None
    label_language: Language | None = None
    source: GuidanceSource
    confidence: float
    requires_verification: bool = False
    inferred: bool = False
    languages: dict[Language, FieldGuidance] = Field(default_factory=dict)

    @property
    def available(self) -> list[Language]:
        return list(self.languages)


class GuidanceRequest(BaseModel):
    field_id: str
    language: Language = Language.ENGLISH
    allow_external_ai: bool = False
    category: DocumentCategory | None = None


class GuidanceBundleRequest(BaseModel):
    """Ask for several fields in several languages in one call."""

    field_ids: list[str] | None = None
    languages: list[Language] | None = None
    allow_external_ai: bool = False
    category: DocumentCategory | None = None


class GuidanceBundleResponse(BaseModel):
    document_id: str
    bundles: list[MultilingualFieldGuidance] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    llm_used: bool = False


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    field_id: str | None = None
    language: Language = Language.ENGLISH
    allow_external_ai: bool = False


class AskResponse(BaseModel):
    answer: str
    source: GuidanceSource
    highlights: list[NormalizedBoundingBox] = Field(default_factory=list)
    llm_used: bool = False
    refused: bool = False


class LLMGuidancePayload(BaseModel):
    simple_label: str
    what_to_enter: str
    why_needed: str | None = None
    example: str | None = None
    format_hint: str | None = None
    requires_verification: bool = True


class LLMMultilingualPayload(BaseModel):
    """One LLM call describes a field in every requested language, so the four language
    columns come from a single reading of the printed label and stay consistent."""

    simple_label: dict[str, str] = Field(default_factory=dict)
    what_to_enter: dict[str, str] = Field(default_factory=dict)
    why_needed: dict[str, str] = Field(default_factory=dict)
    example: str | None = None
    format_hint: dict[str, str] = Field(default_factory=dict)
    requires_verification: bool = True

    def for_language(self, language: Language) -> LLMGuidancePayload | None:
        what = self.what_to_enter.get(language.value)
        if not what or not what.strip():
            return None
        return LLMGuidancePayload(
            simple_label=self.simple_label.get(language.value) or "",
            what_to_enter=what,
            why_needed=self.why_needed.get(language.value) or None,
            example=self.example,
            format_hint=self.format_hint.get(language.value) or None,
            requires_verification=self.requires_verification,
        )
