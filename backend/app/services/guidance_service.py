from __future__ import annotations

import logging

from app.models.common import ALL_LANGUAGES, FieldType, GuidanceSource, Language
from app.models.fields import DetectedField
from app.models.guidance import (
    AskRequest,
    AskResponse,
    FieldGuidance,
    GuidanceRequest,
    LLMGuidancePayload,
    MultilingualFieldGuidance,
)
from app.models.ocr import OCRResult
from app.repositories.field_dictionary_repository import DictionaryEntry, FieldDictionaryRepository
from app.repositories.form_knowledge_repository import FormKnowledgeRepository
from app.services.field_semantics_service import FieldSemanticsService, SemanticMatch
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.services.translation_service import TranslationService
from app.utils.text_normalization import dominant_script, fold

logger = logging.getLogger(__name__)

# Minimum retrieval score accepted when the form itself is unknown. See _retrieved.
UNKNOWN_FORM_RETRIEVAL_FLOOR = 0.62

WHERE_TERMS = ("where", "location", "highlight", "कहाँ", "कहां", "स्थान", "ಎಲ್ಲಿ", "ಸ್ಥಳ", "کہاں", "مقام")
FILL_FOR_ME_TERMS = (
    "fill this",
    "my name",
    "what should i write as my",
    "enter my",
    "fill it for me",
    "भर दो",
    "मेरा नाम",
    "ಭರ್ತಿ ಮಾಡಿ",
    "ನನ್ನ ಹೆಸರು",
    "بھر دو",
    "میرا نام",
)


class GuidanceService:
    """Produces field guidance for known and unknown forms alike.

    Resolution order, highest trust first:

    1. the seeded knowledge base for a recognised form;
    2. the multilingual common-field dictionary, matched on the printed label in any
       supported script (this is what carries unknown forms);
    3. vector retrieval over both of the above;
    4. a label-pattern heuristic that describes the *shape* of the answer and says
       plainly that it was inferred;
    5. an optional LLM reading of the printed label only;
    6. an honest unavailable state.

    Steps 1 to 4 and 6 need no network, so an unknown form in any supported language is
    fully usable with the LLM switched off.
    """

    def __init__(
        self,
        knowledge: FormKnowledgeRepository,
        dictionary: FieldDictionaryRepository,
        semantics: FieldSemanticsService,
        retrieval: RetrievalService,
        llm: LLMService,
        translation: TranslationService,
        common_threshold: float,
        retrieval_threshold: float,
    ) -> None:
        self.knowledge = knowledge
        self.dictionary = dictionary
        self.semantics = semantics
        self.retrieval = retrieval
        self.llm = llm
        self.translation = translation
        self.common_threshold = common_threshold
        self.retrieval_threshold = retrieval_threshold

    # --- single language -------------------------------------------------------

    def for_field(
        self,
        field: DetectedField,
        request: GuidanceRequest,
        form_id: str | None,
        ocr_pages: list[OCRResult],
        interpreted=None,
        classified=None,
    ) -> FieldGuidance:
        bundle = self.bundle_for_field(
            field,
            form_id,
            ocr_pages,
            languages=[request.language],
            allow_external_ai=request.allow_external_ai,
            category=request.category,
            interpreted=interpreted,
            classified=classified,
        )
        return bundle.languages[request.language]

    # --- all languages at once -------------------------------------------------

    def bundle_for_field(
        self,
        field: DetectedField,
        form_id: str | None,
        ocr_pages: list[OCRResult],
        languages: list[Language] | None = None,
        allow_external_ai: bool = False,
        category=None,
        interpreted=None,
        classified=None,
    ) -> MultilingualFieldGuidance:
        wanted = list(languages or ALL_LANGUAGES)
        highlights = [field.input_box, *field.label_boxes]

        resolved = self._resolve(
            field, form_id, ocr_pages, wanted, allow_external_ai, category, interpreted, classified
        )
        built: dict[Language, FieldGuidance] = {}
        for language in wanted:
            built[language] = resolved.render(self, field, language, highlights)

        return MultilingualFieldGuidance(
            field_id=field.id,
            semantic_id=resolved.semantic_id,
            label_language=self.semantics.label_language(field.label) if field.label else None,
            source=resolved.source,
            confidence=resolved.confidence,
            requires_verification=resolved.requires_verification,
            inferred=resolved.inferred,
            languages=built,
        )

    def _resolve(
        self,
        field: DetectedField,
        form_id: str | None,
        ocr_pages: list[OCRResult],
        wanted: list[Language],
        allow_external_ai: bool,
        category,
        interpreted=None,
        classified=None,
    ) -> "_Resolution":
        known = self._known(field, form_id)
        if known is not None:
            return known
        # A reading of this blank in the context of its own page outranks any lexical
        # match, because it is the only source that knows which column the caption sat
        # under and whose details the row is about.
        if interpreted is not None:
            return _InterpretedResolution(interpreted, classified)
        if classified is not None and classified.concept:
            entry = self.dictionary.get(classified.concept)
            if entry is not None:
                return _ConceptResolution(entry, classified)
        if classified is not None and not classified.concept:
            # The page was read and no concept fits this blank. Matching its wording
            # against the dictionary now would undo that judgement, and the word match is
            # exactly what gets this wrong: "AC Number (previous roll)" lexically
            # resembles an account number, and the stock text tells the user to copy it
            # from a passbook.
            #
            # The classifier still understood the blank, though, even if the four-language
            # step later failed for it. Keeping that reading is what stops two identical
            # "AC Number" cells in one row being explained differently -- one as the
            # relative's constituency number, the other as "the printed label asks for a
            # number or code".
            if (classified.what_to_enter or "").strip():
                return _ClassifiedTextResolution(
                    classified, self.semantics.match_pattern(field.label, field.field_type)
                )
            pattern = self.semantics.match_pattern(field.label, field.field_type)
            if pattern is not None:
                return _PatternResolution(pattern)
            return _UnavailableResolution(labelled=bool((field.label or "").strip()))
        match = self.semantics.resolve(field.label, field.field_type)
        if match is not None and match.confident:
            return _DictionaryResolution(match)
        if match is not None:
            # Plausible but not confident: still far better than nothing, and the
            # interface marks it for verification. A direct match on the printed wording
            # beats a vector hit, which is why this is tried before retrieval.
            return _DictionaryResolution(match)
        retrieved = self._retrieved(field, form_id, wanted)
        if retrieved is not None:
            return retrieved
        if allow_external_ai:
            ai = self._llm(field, ocr_pages, wanted, category)
            if ai is not None:
                return ai
        pattern = self.semantics.match_pattern(field.label, field.field_type)
        if pattern is not None:
            return _PatternResolution(pattern)
        return _UnavailableResolution(labelled=bool((field.label or "").strip()))

    # --- resolution sources ----------------------------------------------------

    def _known(self, field: DetectedField, form_id: str | None) -> "_KnownResolution | None":
        if not form_id:
            return None
        match = self.knowledge.find_field(
            form_id, [field.label, field.id, field.known_field_id or ""], Language.ENGLISH
        )
        if not match:
            return None
        return _KnownResolution(match["field"])

    def _retrieved(
        self, field: DetectedField, form_id: str | None, wanted: list[Language]
    ) -> "_RetrievedResolution | None":
        query = field.label or field.id
        # On an unknown form the bar is higher. The vector store falls back to lexical
        # scoring, which returns *something* for almost any query, so a loose threshold
        # would let a weak hit be presented as dictionary guidance for a label the
        # dictionary does not actually cover. An honest "inferred from the wording"
        # answer is better than a confident wrong one.
        threshold = self.retrieval_threshold if form_id else max(self.retrieval_threshold, UNKNOWN_FORM_RETRIEVAL_FLOOR)
        per_language: dict[Language, dict] = {}
        score = 0.0
        for language in wanted:
            hits = self.retrieval.retrieve(query, language, form_id)
            if not hits:
                continue
            top = hits[0]
            if top["score"] < threshold:
                continue
            per_language[language] = top["metadata"]
            score = max(score, top["score"])
        if not per_language:
            return None
        return _RetrievedResolution(per_language, score)

    def _llm(
        self,
        field: DetectedField,
        ocr_pages: list[OCRResult],
        wanted: list[Language],
        category,
    ) -> "_LLMResolution | None":
        nearby = self._nearby_text(field, ocr_pages)
        codes = ", ".join(language.value for language in wanted)
        prompt = (
            f"Languages required: {codes}\n"
            f"Category: {getattr(category, 'value', None) or 'other'}\n"
            f"Printed label: {field.label}\n"
            f"Detected type: {field.field_type.value}\n"
            f"Label script: {field.label_script or 'unknown'}\n"
            f"Nearby printed text: {nearby}\n"
            "Describe only what this printed field asks for. Do not invent personal "
            "answers, official rules, or required documents. Provide every requested "
            "language key. Return JSON only."
        )
        payload = self.llm.interpret_field_multilingual(prompt, wanted)
        if payload is None:
            return None
        rendered = {language: payload.for_language(language) for language in wanted}
        if not any(rendered.values()):
            return None
        return _LLMResolution(rendered)

    # --- ask -------------------------------------------------------------------

    def ask(
        self,
        field: DetectedField,
        request: AskRequest,
        form_id: str | None,
        ocr_pages: list[OCRResult],
    ) -> AskResponse:
        question = fold(request.question)
        if any(term in question for term in WHERE_TERMS):
            return AskResponse(
                answer=self.translation.message("region_answer", request.language),
                source=GuidanceSource.FORM_TEXT,
                highlights=[field.input_box, *field.label_boxes],
                refused=False,
            )
        if any(term in question for term in FILL_FOR_ME_TERMS):
            return AskResponse(
                answer=self.translation.message("no_invented_value", request.language),
                source=GuidanceSource.UNAVAILABLE,
                highlights=[field.input_box],
                refused=True,
            )
        guidance = self.for_field(
            field,
            GuidanceRequest(
                field_id=field.id,
                language=request.language,
                allow_external_ai=request.allow_external_ai,
            ),
            form_id,
            ocr_pages,
        )
        return AskResponse(
            answer=guidance.what_to_enter,
            source=guidance.source,
            highlights=[field.input_box, *field.label_boxes],
            llm_used=guidance.source == GuidanceSource.GENERAL_AI,
            refused=False,
        )

    def prompt_contains_user_answer(self, prompt: str, answers: list[str]) -> bool:
        folded = fold(prompt)
        return any(value and fold(value) in folded for value in answers if len(value.strip()) >= 3)

    def _nearby_text(self, field: DetectedField, ocr_pages: list[OCRResult]) -> str:
        words = []
        for page in ocr_pages:
            if page.page_index != field.page_index:
                continue
            for word in page.words:
                if abs(word.box.y - field.input_box.y) < 0.08:
                    words.append(word)
        words.sort(key=lambda item: (item.box.y, item.box.x))
        return " ".join(word.text for word in words[:40])[:400]


# --- resolution strategies -----------------------------------------------------
#
# Each strategy knows how to render itself into any requested language. Keeping that in
# one object per source is what lets a single resolution fill all four language columns
# without re-running the match.


class _Resolution:
    source = GuidanceSource.UNAVAILABLE
    confidence = 0.2
    requires_verification = True
    inferred = False
    semantic_id: str | None = None

    def render(self, service, field, language, highlights) -> FieldGuidance:  # pragma: no cover - interface
        raise NotImplementedError

    @staticmethod
    def _base(field, language, highlights, **kwargs) -> FieldGuidance:
        return FieldGuidance(field_id=field.id, language=language, highlights=highlights, **kwargs)


class _InterpretedResolution(_Resolution):
    """The model's own four-language description of this blank, read in page context."""

    source = GuidanceSource.PAGE_INTERPRETATION
    # Not "inferred": this was read from the page, with the column headings and the
    # document's own glossary in hand. Badging it as a guess alongside a confidence of
    # 88% told the user two contradictory things about the same answer. It still asks to
    # be verified, as everything here does.
    inferred = False

    def __init__(self, interpreted, classified=None) -> None:
        self.interpreted = interpreted
        self.classified = classified
        self.confidence = round(min(0.88, 0.45 + 0.45 * float(interpreted.confidence or 0.5)), 3)
        self.requires_verification = True
        self.semantic_id = getattr(classified, "concept", None)

    def render(self, service, field, language, highlights) -> FieldGuidance:
        code = language.value
        what = (self.interpreted.what_to_enter.get(code) or "").strip()
        if not what:
            # The model did not produce this language in its own script, and a silent
            # fall back to another language would read as a broken translation.
            return _UnavailableResolution(labelled=True).render(service, field, language, highlights)
        label = (self.interpreted.label.get(code) or "").strip()
        rule = {"kind": self.interpreted.validation} if self.interpreted.validation else {}
        guidance = self._base(
            field,
            language,
            highlights,
            simple_label=label or field.display_label or field.label or "Field",
            what_to_enter=what,
            why_needed=(self.interpreted.why_needed.get(code) or "").strip() or None,
            example=self.interpreted.example_for(language),
            format_hint=(self.interpreted.format_hint.get(code) or "").strip() or None,
            validation_rule=service.semantics.validation_rule(rule),
            source=self.source,
            source_reference="page_interpretation",
            confidence=self.confidence,
            requires_verification=True,
            inferred=False,
            verify_notice=service.translation.verify_notice(language),
        )
        return guidance


class _ClassifiedTextResolution(_Resolution):
    """What the classifier understood, when the four-language step did not run for it.

    The classification pass reads every blank in page context and almost always succeeds;
    the per-language pass is the one that can fail for a batch. Falling all the way back
    to a shape heuristic in that case throws away a correct reading and produces the worst
    kind of inconsistency -- two identical cells in one row, one explained precisely and
    the other generically.

    English carries the classifier's own sentence. The other languages carry the shape
    description in their own script, which is honest rather than a machine translation of
    something nobody checked, and the whole thing is marked for verification.
    """

    source = GuidanceSource.PAGE_INTERPRETATION
    inferred = True
    requires_verification = True

    def __init__(self, classified, pattern=None) -> None:
        self.classified = classified
        self.pattern = pattern
        self.confidence = round(min(0.8, 0.4 + 0.4 * float(classified.confidence or 0.5)), 3)
        self.semantic_id = None

    def render(self, service, field, language, highlights) -> FieldGuidance:
        english = language is Language.ENGLISH
        if english:
            text = self.classified.what_to_enter.strip()
            label = self.classified.label.strip() or field.display_label or field.label
        elif self.pattern is not None:
            text = (self.pattern.pattern.text("what_to_enter", language) or "").strip()
            label = field.display_label or field.label or ""
        else:
            text = service.translation.unavailable_message(language)
            label = field.display_label or field.label or ""
        if not text:
            text = service.translation.unavailable_message(language)
        rule = {"kind": self.classified.validation} if self.classified.validation else {}
        return self._base(
            field,
            language,
            highlights,
            simple_label=label or "Field",
            what_to_enter=text,
            validation_rule=service.semantics.validation_rule(rule),
            source=self.source,
            source_reference="page_interpretation",
            confidence=self.confidence,
            requires_verification=True,
            inferred=True,
            verify_notice=service.translation.verify_notice(language),
        )


class _ConceptResolution(_Resolution):
    """A dictionary concept chosen by reading the page, rather than by matching words.

    The authored four-language text is used as written, because the blank is an ordinary
    one about the applicant's own details and the stock description fits it exactly. A
    blank the page qualifies -- a parent's record, an office block -- never reaches here.
    """

    source = GuidanceSource.COMMON_DICTIONARY

    def __init__(self, entry: DictionaryEntry, classified) -> None:
        self.entry = entry
        self.classified = classified
        self.semantic_id = entry.id
        self.confidence = round(min(0.9, 0.5 + 0.4 * float(classified.confidence or 0.5)), 3)
        self.requires_verification = self.confidence < 0.8

    def render(self, service, field, language, highlights) -> FieldGuidance:
        entry = self.entry
        return self._base(
            field,
            language,
            highlights,
            simple_label=entry.text("simple_label", language) or field.label or entry.id,
            what_to_enter=entry.text("what_to_enter", language) or service.translation.unavailable_message(language),
            why_needed=entry.text("why_needed", language),
            example=entry.example_for(language),
            format_hint=entry.text("format_hint", language) or entry.validation.get("format"),
            validation_rule=service.semantics.validation_rule(entry.validation),
            source=self.source,
            source_reference=entry.source_reference or entry.id,
            confidence=self.confidence,
            requires_verification=self.requires_verification,
            verify_notice=service.translation.verify_notice(language),
        )


# Known-form ids that are the same concept as a dictionary entry under another name.
_KNOWN_DICTIONARY_IDS = {
    "contact_number": "mobile_number",
    "nominee": "nominee_name",
    "relationship": "nominee_relation",
    "institution": "institution_name",
    "marks": "marks_percentage",
    "declaration": "declaration_consent",
    "acknowledgement": "declaration_consent",
    "policyholder_name": "full_name",
}

_SCRIPT_FOR_LANGUAGE = {
    Language.ENGLISH: "latin",
    Language.HINDI: "devanagari",
    Language.KANNADA: "kannada",
    Language.URDU: "arabic",
}


def _in_script(text: str, language: Language) -> bool:
    return bool(text) and dominant_script(text) == _SCRIPT_FOR_LANGUAGE[language]


class _KnownResolution(_Resolution):
    source = GuidanceSource.KNOWN_FORM
    confidence = 0.93
    requires_verification = False

    def __init__(self, item: dict) -> None:
        self.item = item
        self.semantic_id = item.get("field_id")

    def render(self, service, field, language, highlights) -> FieldGuidance:
        item = self.item
        code = language.value
        what = item.get("what_to_enter", {}) or {}
        why = item.get("why_needed", {}) or {}
        labels = item.get("simple_label", {}) or {}
        local_text = (what.get(code) or "").strip()
        local_why = (why.get(code) or "").strip()
        local_label = (labels.get(code) or "").strip()
        # Known-form files were authored in English, with Hindi and Kannada stored in
        # Latin letters. Reading those with an Urdu, Hindi, or Kannada voice sounds like
        # the wrong language. Prefer a sentence that is actually in the requested script.
        field_id = str(item.get("field_id") or "")
        entry = service.dictionary.get(field_id) or service.dictionary.get(_KNOWN_DICTIONARY_IDS.get(field_id, ""))
        text = local_text if _in_script(local_text, language) else ""
        why_text = local_why if _in_script(local_why, language) else ""
        label = local_label if _in_script(local_label, language) else ""
        if entry is not None:
            if not text:
                candidate = (entry.what_to_enter.get(code) or "").strip()
                if _in_script(candidate, language):
                    text = candidate
            if not why_text:
                candidate = (entry.why_needed.get(code) or "").strip()
                if _in_script(candidate, language):
                    why_text = candidate
            if not label:
                candidate = (entry.simple_label.get(code) or "").strip()
                if _in_script(candidate, language):
                    label = candidate
        if not text:
            text = local_text or (what.get(Language.ENGLISH.value) or "").strip() or service.translation.unavailable_message(language)
        if not why_text:
            why_text = local_why or (why.get(Language.ENGLISH.value) or "").strip()
        if not label:
            label = local_label or field.label or field_id
        example = (item.get("example") or "").strip()
        if entry is not None and not _in_script(example, language):
            candidate = (entry.example_for(language) or "").strip()
            if candidate and (language is Language.ENGLISH or _in_script(candidate, language)):
                example = candidate
        return self._base(
            field,
            language,
            highlights,
            simple_label=label,
            what_to_enter=text,
            why_needed=why_text or None,
            example=example or None,
            format_hint=item.get("validation", {}).get("format"),
            validation_rule=service.semantics.validation_rule(item.get("validation", {})),
            source=self.source,
            source_reference=item.get("source_reference"),
            confidence=self.confidence,
            requires_verification=False,
        )


class _DictionaryResolution(_Resolution):
    source = GuidanceSource.COMMON_DICTIONARY

    def __init__(self, match: SemanticMatch) -> None:
        self.match = match
        self.entry: DictionaryEntry = match.entry
        self.semantic_id = match.entry.id
        # The dictionary text itself is authored and trustworthy; the confidence here
        # reports how sure we are that this row is the right one for the printed label.
        self.confidence = round(min(0.92, 0.55 + 0.37 * match.score), 3)
        self.requires_verification = not match.confident

    def render(self, service, field, language, highlights) -> FieldGuidance:
        entry = self.entry
        return self._base(
            field,
            language,
            highlights,
            simple_label=entry.text("simple_label", language) or field.label or entry.id,
            what_to_enter=entry.text("what_to_enter", language) or service.translation.unavailable_message(language),
            why_needed=entry.text("why_needed", language),
            example=entry.example_for(language),
            format_hint=entry.text("format_hint", language) or entry.validation.get("format"),
            validation_rule=service.semantics.validation_rule(entry.validation),
            source=self.source,
            source_reference=entry.source_reference or entry.id,
            confidence=self.confidence,
            requires_verification=self.requires_verification,
            verify_notice=service.translation.verify_notice(language),
        )


class _RetrievedResolution(_Resolution):
    source = GuidanceSource.COMMON_DICTIONARY
    requires_verification = True

    def __init__(self, per_language: dict[Language, dict], score: float) -> None:
        self.per_language = per_language
        self.confidence = round(min(0.84, 0.5 + score / 2), 3)
        first = next(iter(per_language.values()))
        self.semantic_id = first.get("field_id")
        if first.get("source") == "known_form_knowledge_base":
            self.source = GuidanceSource.KNOWN_FORM

    def render(self, service, field, language, highlights) -> FieldGuidance:
        metadata = self.per_language.get(language) or next(iter(self.per_language.values()))
        return self._base(
            field,
            language,
            highlights,
            simple_label=metadata.get("simple_label") or field.label or metadata.get("field_id", "Field"),
            what_to_enter=metadata.get("what_to_enter") or service.translation.unavailable_message(language),
            why_needed=metadata.get("why_needed") or None,
            example=metadata.get("example"),
            validation_rule=service.semantics.validation_rule(metadata.get("validation") or {}),
            source=self.source,
            source_reference=metadata.get("source_reference"),
            confidence=self.confidence,
            requires_verification=True,
            verify_notice=service.translation.verify_notice(language),
        )


class _PatternResolution(_Resolution):
    source = GuidanceSource.LABEL_HEURISTIC
    requires_verification = True
    inferred = True

    def __init__(self, match) -> None:
        self.match = match
        self.pattern = match.pattern
        self.confidence = round(min(0.6, 0.35 + 0.3 * match.score), 3)
        self.label_pattern_id = match.pattern.id

    def render(self, service, field, language, highlights) -> FieldGuidance:
        note = service.dictionary.note(language)
        body = self.pattern.text("what_to_enter", language) or service.translation.unavailable_message(language)
        return self._base(
            field,
            language,
            highlights,
            simple_label=field.label or self.pattern.id,
            what_to_enter=f"{body} {note}".strip(),
            format_hint=self.pattern.text("format_hint", language),
            validation_rule=service.semantics.validation_rule(self.pattern.validation),
            source=self.source,
            source_reference=f"label_pattern:{self.pattern.id}",
            confidence=self.confidence,
            requires_verification=True,
            inferred=True,
            verify_notice=service.translation.verify_notice(language),
        )


class _LLMResolution(_Resolution):
    source = GuidanceSource.GENERAL_AI
    confidence = 0.58
    requires_verification = True
    inferred = True

    def __init__(self, rendered: dict[Language, LLMGuidancePayload | None]) -> None:
        self.rendered = rendered

    def render(self, service, field, language, highlights) -> FieldGuidance:
        payload = self.rendered.get(language)
        if payload is None:
            # The model skipped this language. Say so rather than show another language's
            # text under this language's heading.
            return _UnavailableResolution(labelled=True).render(service, field, language, highlights)
        return self._base(
            field,
            language,
            highlights,
            simple_label=payload.simple_label or field.label,
            what_to_enter=payload.what_to_enter,
            why_needed=payload.why_needed,
            example=payload.example,
            format_hint=payload.format_hint,
            source=self.source,
            source_reference="groq",
            confidence=self.confidence,
            requires_verification=True,
            inferred=True,
            verify_notice=service.translation.verify_notice(language),
        )


class _UnavailableResolution(_Resolution):
    def __init__(self, labelled: bool) -> None:
        self.labelled = labelled

    def render(self, service, field, language, highlights) -> FieldGuidance:
        text = (
            service.translation.unavailable_message(language)
            if self.labelled
            else service.translation.unlabelled_message(language)
        )
        return self._base(
            field,
            language,
            highlights,
            simple_label=field.label or "Field",
            what_to_enter=text,
            source=GuidanceSource.UNAVAILABLE,
            confidence=0.2,
            requires_verification=True,
            validation_rule=None if field.field_type != FieldType.SIGNATURE else None,
        )
