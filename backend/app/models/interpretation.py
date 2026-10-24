"""Schema for a model's reading of a form page.

Kept separate from the guidance models because this is the *raw* interpretation: what the
model said about each blank, before FormSathi decides whether to trust it, which language
columns survive the script check, and how it is presented.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.models.common import ALL_LANGUAGES, Language

# The validation kinds the interpreter is allowed to choose from. Anything else is
# treated as plain text rather than trusted, so a hallucinated rule cannot reject a
# user's perfectly good answer.
ALLOWED_VALIDATION = {
    "person_name",
    "text",
    "multiline",
    "date",
    "year",
    "integer",
    "decimal",
    "amount",
    "mobile_in",
    "phone",
    "email",
    "pincode_in",
    "aadhaar_in",
    "pan_in",
    "ifsc_in",
    "bank_account",
    "alphanumeric",
    "choice",
    "signature",
    "attachment",
    "office_use",
    "non_empty",
}


class FilledBy(str, Enum):
    APPLICANT = "applicant"
    OFFICE = "office"
    EITHER = "either"


class FormContext(BaseModel):
    """What this document is, read once before any field is described.

    A field's meaning often depends on the document it sits in, not on its own caption.
    "AC No." is an Assembly Constituency number on an electoral form and an account number
    on a bank form; the caption is identical in both. Establishing the document's subject
    and its abbreviations first is what makes the difference.
    """

    title: str = ""
    authority: str = ""
    purpose: str = ""
    # Abbreviation -> what it stands for on *this* form.
    glossary: dict[str, str] = Field(default_factory=dict)
    # Instructions that change how a field should be filled, in the form's own terms.
    notes: list[str] = Field(default_factory=list)
    # Parts the applicant does not fill.
    office_sections: list[str] = Field(default_factory=list)
    # Where any web-sourced background came from, so it can be shown rather than implied.
    web_sources: list[str] = Field(default_factory=list)
    confidence: float = 0.5

    @field_validator("confidence")
    @classmethod
    def _bounded(cls, value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("glossary", mode="before")
    @classmethod
    def _flat_glossary(cls, value: object) -> object:
        # Models sometimes answer with a list of {term, meaning} objects.
        if isinstance(value, list):
            flat = {}
            for item in value:
                if isinstance(item, dict):
                    term = item.get("term") or item.get("abbreviation") or item.get("name")
                    meaning = item.get("meaning") or item.get("expansion") or item.get("definition")
                    if term and meaning:
                        flat[str(term)] = str(meaning)
            return flat
        return value if isinstance(value, dict) else {}

    def merge_web(self, web: "WebContext") -> None:
        """Fold in web findings without letting them overrule the paper.

        The document in the user's hands is the authority on itself. A search result may
        be about a different edition of the form, or a different form with a similar
        name, so it only fills gaps: an abbreviation the pages never expanded, a name or
        an issuing body the pages did not state.
        """
        if not web.useful:
            return
        for term, meaning in web.glossary.items():
            self.glossary.setdefault(term, meaning)
        if not self.authority and web.authority:
            self.authority = web.authority
        if not self.title and web.official_name:
            self.title = web.official_name
        if not self.purpose and web.summary:
            self.purpose = web.summary
        self.web_sources = list(web.sources)[:5]

    def summary(self) -> str:
        """A compact briefing to prepend to every per-field request."""
        parts = []
        if self.title:
            parts.append(f"Form: {self.title}")
        if self.authority:
            parts.append(f"Issued by: {self.authority}")
        if self.purpose:
            parts.append(f"Purpose: {self.purpose}")
        if self.glossary:
            terms = "; ".join(f"{k} = {v}" for k, v in list(self.glossary.items())[:20])
            parts.append(f"Abbreviations used on this form: {terms}")
        if self.office_sections:
            parts.append("Filled by the office, not the applicant: " + "; ".join(self.office_sections[:6]))
        for note in self.notes[:6]:
            parts.append(f"Instruction: {note}")
        return "\n".join(parts)


class WebContext(BaseModel):
    """Background on the form found by searching the web.

    Strictly supplementary. It may name the form and expand the initialisms an authority
    uses; it must never carry rules, checklists, fees, deadlines or procedure, because
    those differ between editions of a form and between applicants, and the printed page
    in hand is the only trustworthy source for them.
    """

    official_name: str = ""
    authority: str = ""
    summary: str = ""
    glossary: dict[str, str] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("confidence")
    @classmethod
    def _bounded(cls, value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("glossary", mode="before")
    @classmethod
    def _flat_glossary(cls, value: object) -> object:
        if isinstance(value, list):
            flat = {}
            for item in value:
                if isinstance(item, dict):
                    term = item.get("term") or item.get("abbreviation") or item.get("name")
                    meaning = item.get("meaning") or item.get("expansion") or item.get("definition")
                    if term and meaning:
                        flat[str(term)] = str(meaning)
            return flat
        return value if isinstance(value, dict) else {}

    @property
    def useful(self) -> bool:
        return bool(self.glossary or self.official_name or self.summary)


class ClassifiedField(BaseModel):
    """Stage one: what this blank is, in English only.

    Deliberately compact. Asking for every field in four languages in one reply overruns
    the model's output budget and the JSON comes back truncated, so the expensive
    multilingual step is reserved for the few fields the authored dictionary cannot cover.
    """

    id: str
    is_field: bool = True
    fill_by: FilledBy = FilledBy.APPLICANT
    concept: str | None = None
    needs_detail: bool = False
    label: str = ""
    what_to_enter: str = ""
    validation: str = "text"
    confidence: float = 0.5

    @field_validator("validation")
    @classmethod
    def _known_validation(cls, value: str) -> str:
        cleaned = (value or "").strip().lower()
        return cleaned if cleaned in ALLOWED_VALIDATION else "text"

    @field_validator("confidence")
    @classmethod
    def _bounded_confidence(cls, value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("concept", mode="before")
    @classmethod
    def _blank_concept_is_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "unknown"}:
            return None
        return value

    @field_validator("fill_by", mode="before")
    @classmethod
    def _tolerant_fill_by(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {item.value for item in FilledBy}:
            return value.strip().lower()
        return FilledBy.APPLICANT


class ClassifiedPage(BaseModel):
    fields: list[ClassifiedField] = Field(default_factory=list)

    def by_id(self) -> dict[str, ClassifiedField]:
        return {item.id: item for item in self.fields}


class InterpretedField(BaseModel):
    id: str
    is_field: bool = True
    fill_by: FilledBy = FilledBy.APPLICANT
    label: dict[str, str] = Field(default_factory=dict)
    what_to_enter: dict[str, str] = Field(default_factory=dict)
    why_needed: dict[str, str] = Field(default_factory=dict)
    # A worked example per language. A date or a code reads the same everywhere, but a
    # name does not: Latin letters beside Kannada guidance ask the reader to switch
    # script mid-sentence. A plain string is still accepted and used for every language.
    example: dict[str, str] = Field(default_factory=dict)
    format_hint: dict[str, str] = Field(default_factory=dict)
    validation: str = "text"
    confidence: float = 0.5

    @field_validator("validation")
    @classmethod
    def _known_validation(cls, value: str) -> str:
        cleaned = (value or "").strip().lower()
        return cleaned if cleaned in ALLOWED_VALIDATION else "text"

    @field_validator("confidence")
    @classmethod
    def _bounded_confidence(cls, value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("fill_by", mode="before")
    @classmethod
    def _tolerant_fill_by(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {item.value for item in FilledBy}:
            return value.strip().lower()
        return FilledBy.APPLICANT

    @field_validator("example", mode="before")
    @classmethod
    def _example_per_language(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            return {language.value: text for language in ALL_LANGUAGES} if text else {}
        return value if isinstance(value, dict) else {}

    def example_for(self, language: Language) -> str | None:
        return (self.example or {}).get(language.value) or (self.example or {}).get(Language.ENGLISH.value)

    def languages_present(self) -> list[Language]:
        return [language for language in ALL_LANGUAGES if (self.what_to_enter.get(language.value) or "").strip()]


class InterpretedPage(BaseModel):
    fields: list[InterpretedField] = Field(default_factory=list)

    def by_id(self) -> dict[str, InterpretedField]:
        return {item.id: item for item in self.fields}
