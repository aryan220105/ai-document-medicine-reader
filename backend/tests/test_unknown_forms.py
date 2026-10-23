"""Tests for the unknown-form flow.

These exercise everything below the OCR engine with synthetic OCR results, so they run
without Tesseract installed and so that a label can be perturbed exactly the way a noisy
scan perturbs it. The real engine is covered separately by
``scripts/evaluate_unknown_flow.py``.
"""

from __future__ import annotations

import pytest

from app.models.common import (
    ALL_LANGUAGES,
    DocumentCategory,
    FieldType,
    GuidanceSource,
    Language,
    PixelBoundingBox,
)
from app.models.fields import DetectedField, FieldAnswer
from app.models.guidance import GuidanceBundleRequest, GuidanceRequest
from app.models.ocr import OCRResult, OCRWord
from app.utils.bounding_boxes import normalize_box
from app.utils.text_normalization import (
    dominant_script,
    fold_for_match,
    fuzzy_sequence_match,
    is_rtl,
    match_tokens,
    tokens,
)

IMAGE = dict(image_width=1000, image_height=1000)

EXPECTED_SCRIPT = {
    Language.ENGLISH: "latin",
    Language.HINDI: "devanagari",
    Language.KANNADA: "kannada",
    Language.URDU: "arabic",
}


def field(label: str, field_type: FieldType = FieldType.TEXT, **box) -> DetectedField:
    pixel = PixelBoundingBox(x=box.get("x", 400), y=box.get("y", 100), width=box.get("w", 400), height=box.get("h", 40), **IMAGE)
    return DetectedField(
        id=box.get("id", "f1"),
        page_index=0,
        label=label,
        field_type=field_type,
        input_box=normalize_box(pixel),
        confidence=0.8,
    )


def word(text: str, x: int, y: int, w: int = 120, h: int = 24, ident: str = "w") -> OCRWord:
    return OCRWord(
        id=ident,
        text=text,
        confidence=90,
        page_index=0,
        pixel=PixelBoundingBox(x=x, y=y, width=w, height=h, **IMAGE),
        line_id=1,
        block_id=1,
    )


# --- script-aware text utilities ---------------------------------------------------


def test_tokens_keep_every_supported_script():
    # The original token regex was [a-z0-9]+, which silently discarded every Devanagari,
    # Kannada, and Urdu label and left them unmatchable.
    assert tokens("पूरा नाम") == ["पूरा", "नाम"]
    assert tokens("ಪೂರ್ಣ ಹೆಸರು") == ["ಪೂರ್ಣ", "ಹೆಸರು"]
    assert tokens("پورا نام") == ["پورا", "نام"]
    assert tokens("Full Name") == ["full", "name"]


def test_match_tokens_drop_the_marks_a_noisy_scan_loses():
    # The matching fold deliberately strips combining marks, so a label read without its
    # vowel signs still matches the alias that has them. It keeps the script itself.
    assert match_tokens("पूरा नाम") == match_tokens("परा नम")
    assert len(match_tokens("ಪೂರ್ಣ ಹೆಸರು")) == 2
    assert match_tokens("Full Name") == ["full", "name"]


def test_dominant_script_prefers_the_regional_script_over_english_headings():
    assert dominant_script("Full Name") == "latin"
    assert dominant_script("पूरा नाम") == "devanagari"
    assert dominant_script("ಪೂರ್ಣ ಹೆಸರು") == "kannada"
    assert dominant_script("پورا نام") == "arabic"
    # A bilingual heading still reports the regional script, because that is the column
    # the applicant needs.
    assert dominant_script("Full Name / पूरा नाम") == "devanagari"
    assert is_rtl("مستقل پتہ") is True
    assert is_rtl("स्थायी पता") is False


def test_arabic_letter_variants_fold_together():
    # The same Urdu word typed on different keyboards must match one alias.
    assert fold_for_match("آدھار") == fold_for_match("ادھار")
    assert fold_for_match("نمبر ") == "نمبر"


def test_fuzzy_sequence_tolerates_ocr_errors_but_not_different_words():
    assert fuzzy_sequence_match(["ful", "nane"], ["full", "name"]) > 0
    assert fuzzy_sequence_match(["dato", "of", "birlh"], ["date", "of", "birth"]) > 0
    # 'brother' and 'mother' share a suffix but are different words.
    assert fuzzy_sequence_match(["brother"], ["mother"]) == 0.0


# --- dictionary resolution ----------------------------------------------------------


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Full Name", "full_name"),
        ("Name of Applicant", "full_name"),
        ("Father's Name", "father_name"),
        ("Date of Birth", "date_of_birth"),
        ("Mobile Number", "mobile_number"),
        ("PIN Code", "pincode"),
        ("Aadhaar Number", "aadhaar_number"),
        ("Bank Account Number", "bank_account_number"),
        ("Signature of Applicant", "signature"),
        ("पूरा नाम", "full_name"),
        ("पिता का नाम", "father_name"),
        ("जन्म तिथि", "date_of_birth"),
        ("आधार संख्या", "aadhaar_number"),
        ("हस्ताक्षर", "signature"),
        ("ಪೂರ್ಣ ಹೆಸರು", "full_name"),
        ("ತಂದೆಯ ಹೆಸರು", "father_name"),
        ("ಜನ್ಮ ದಿನಾಂಕ", "date_of_birth"),
        ("ಬ್ಯಾಂಕ್ ಖಾತೆ ಸಂಖ್ಯೆ", "bank_account_number"),
        ("ಸಹಿ", "signature"),
        ("پورا نام", "full_name"),
        ("والد کا نام", "father_name"),
        ("تاریخ پیدائش", "date_of_birth"),
        ("موبائل نمبر", "mobile_number"),
        ("مستقل پتہ", "permanent_address"),
        ("دستخط", "signature"),
    ],
)
def test_labels_resolve_in_every_language(container, label, expected):
    match = container.semantics.resolve(label, None)
    assert match is not None, f"no match for {label!r}"
    assert match.entry.id == expected
    assert match.confident, f"{label!r} resolved to {expected} but not confidently"


@pytest.mark.parametrize(
    "noisy,expected",
    [
        ("Ful Nane", "full_name"),
        ("Fathers Nane", "father_name"),
        ("Dato of Birlh", "date_of_birth"),
        ("Mobilc Numbor", "mobile_number"),
        ("Aadhar Numbor", "aadhaar_number"),
        ("Annua1 lncome", "annual_income"),
        ("Residentlal Addres", "address"),
        ("Signaturc", "signature"),
        ("जनम तिथि", "date_of_birth"),
        ("ಜನ್ಮ ದಿನಾಕ", "date_of_birth"),
    ],
)
def test_noisy_labels_still_resolve(container, noisy, expected):
    """A scan does not have to be clean for a field to be understood."""
    match = container.semantics.resolve(noisy, None)
    assert match is not None, f"no match for noisy label {noisy!r}"
    assert match.entry.id == expected


def test_a_generic_token_does_not_claim_a_qualified_label(container):
    """'bank' must not win 'Bank Account Number', and 'name' must not win 'Brother Name'."""
    assert container.semantics.resolve("Bank Account Number", None).entry.id == "bank_account_number"
    assert container.semantics.resolve("Brother Name", None).entry.id == "relative_name"
    assert container.semantics.resolve("Bank Name", None).entry.id == "bank_name"


def test_unrecognised_label_falls_back_to_a_pattern_not_a_guess(container):
    assert container.semantics.resolve("Favourite Genre", None) is None
    pattern = container.semantics.match_pattern("Kiosk Turnstile Number")
    assert pattern is not None
    assert pattern.pattern.id == "number_like"


def test_dictionary_covers_all_four_languages_for_every_field(container):
    """A field that exists in English but not Kannada would silently fall back to English
    text under a Kannada heading, which reads as a translation failure to the user."""
    gaps = []
    for entry in container.dictionary.entries:
        for language in ALL_LANGUAGES:
            if not (entry.simple_label.get(language.value) or "").strip():
                gaps.append(f"{entry.id}:simple_label:{language.value}")
            text = entry.what_to_enter.get(language.value) or ""
            if not text.strip():
                gaps.append(f"{entry.id}:what_to_enter:{language.value}")
            elif dominant_script(text) != EXPECTED_SCRIPT[language]:
                gaps.append(f"{entry.id}:wrong_script:{language.value}")
    assert gaps == [], f"dictionary gaps: {gaps[:10]}"


def test_translation_messages_cover_all_four_languages(container):
    assert container.document_service.guidance.translation.coverage() == {}


# --- multilingual guidance bundles --------------------------------------------------


def test_bundle_describes_one_field_in_every_language(container):
    bundle = container.document_service.guidance.bundle_for_field(
        field("Date of Birth", FieldType.DATE), None, []
    )
    assert set(bundle.languages) == set(ALL_LANGUAGES)
    for language in ALL_LANGUAGES:
        guidance = bundle.languages[language]
        assert guidance.what_to_enter.strip()
        assert dominant_script(guidance.what_to_enter) == EXPECTED_SCRIPT[language]
        assert guidance.language == language
    assert bundle.semantic_id == "date_of_birth"
    assert bundle.source == GuidanceSource.COMMON_DICTIONARY


def test_switching_language_changes_only_the_description(container):
    """The guidance text differs per language while the field's identity does not."""
    target = field("مستقل پتہ", FieldType.MULTILINE)
    bundle = container.document_service.guidance.bundle_for_field(target, None, [])
    texts = {language: bundle.languages[language].what_to_enter for language in ALL_LANGUAGES}
    assert len(set(texts.values())) == len(ALL_LANGUAGES), "languages returned duplicate text"
    for guidance in bundle.languages.values():
        assert guidance.field_id == target.id
        assert guidance.highlights == bundle.languages[Language.ENGLISH].highlights
    # The printed label is untouched by any of this.
    assert target.label == "مستقل پتہ"


def test_unlabelled_field_says_so_rather_than_inventing_a_meaning(container):
    bundle = container.document_service.guidance.bundle_for_field(field(""), None, [])
    for language in ALL_LANGUAGES:
        guidance = bundle.languages[language]
        assert guidance.source == GuidanceSource.UNAVAILABLE
        assert guidance.requires_verification
        assert dominant_script(guidance.what_to_enter) == EXPECTED_SCRIPT[language]


def test_inferred_guidance_is_marked_as_inferred(container):
    bundle = container.document_service.guidance.bundle_for_field(
        field("Kiosk Turnstile Number"), None, []
    )
    assert bundle.source == GuidanceSource.LABEL_HEURISTIC
    assert bundle.inferred
    for language in ALL_LANGUAGES:
        guidance = bundle.languages[language]
        assert guidance.inferred
        assert guidance.requires_verification


def test_office_use_block_is_described_as_office_use(container):
    """A block the form marks for office use must tell the user to leave it alone."""
    bundle = container.document_service.guidance.bundle_for_field(
        field("Lending Desk For Office Use"), None, []
    )
    assert bundle.source == GuidanceSource.LABEL_HEURISTIC
    assert bundle.languages[Language.ENGLISH].validation_rule.kind == "office_use"


def test_guidance_never_reaches_for_the_network_when_ai_is_off(container):
    class Exploding:
        def available(self):  # pragma: no cover - must never run
            raise AssertionError("the LLM was consulted with external AI disabled")

    container.document_service.guidance.llm = Exploding()
    bundle = container.document_service.guidance.bundle_for_field(
        field("Favourite Genre"), None, [], allow_external_ai=False
    )
    assert set(bundle.languages) == set(ALL_LANGUAGES)


# --- field typing and validation ----------------------------------------------------


def test_unknown_form_fields_get_a_type_and_a_validation_rule(container):
    fields = [
        field("Date of Birth", id="a"),
        field("Mobile Number", id="b"),
        field("Residential Address", id="c"),
        field("हस्ताक्षर", id="d"),
    ]
    container.document_service._resolve_semantics(fields)
    by_id = {item.id: item for item in fields}
    assert by_id["a"].field_type == FieldType.DATE
    assert by_id["a"].validation_rule.kind == "date"
    assert by_id["b"].validation_rule.kind == "mobile_in"
    assert by_id["c"].field_type == FieldType.MULTILINE
    assert by_id["d"].field_type == FieldType.SIGNATURE


@pytest.mark.parametrize(
    "kind,good,bad",
    [
        ("mobile_in", "9876500000", "12345"),
        ("pincode_in", "560001", "056000"),
        ("aadhaar_in", "999988887777", "123"),
        ("pan_in", "ABCDE1234F", "ABC123"),
        ("ifsc_in", "DEMO0001234", "DEMO1"),
        ("email", "a@b.com", "nope"),
        ("year", "2024", "24"),
        ("blood_group", "O+", "Z+"),
    ],
)
def test_validation_rules(container, kind, good, bad):
    target = field("x")
    target.validation_rule = container.semantics.validation_rule({"kind": kind})
    validate = container.document_service.validation.validate
    assert validate(target, FieldAnswer(field_id=target.id, value=good)).ok
    assert not validate(target, FieldAnswer(field_id=target.id, value=bad)).ok


def test_validation_accepts_regional_digits(container):
    """A value typed on a Hindi, Kannada, or Urdu keyboard is still a valid number."""
    target = field("x")
    target.validation_rule = container.semantics.validation_rule({"kind": "pincode_in"})
    validate = container.document_service.validation.validate
    for value in ("560001", "५६०००१", "೫೬೦೦೦೧", "۵۶۰۰۰۱"):
        assert validate(target, FieldAnswer(field_id=target.id, value=value)).ok, value


def test_validation_messages_follow_the_chosen_language(container):
    target = field("x")
    target.validation_rule = container.semantics.validation_rule({"kind": "mobile_in"})
    validate = container.document_service.validation.validate
    answer = FieldAnswer(field_id=target.id, value="123")
    for language in ALL_LANGUAGES:
        result = validate(target, answer, language)
        assert not result.ok
        assert dominant_script(result.message) == EXPECTED_SCRIPT[language]


def test_signature_is_never_generated(container):
    target = field("Signature", FieldType.SIGNATURE)
    result = container.document_service.validation.validate(
        target, FieldAnswer(field_id=target.id, value="anything")
    )
    assert result.ok
    assert "hand" in result.message.lower()


# --- right-to-left label association -------------------------------------------------


def test_urdu_label_is_found_to_the_right_of_the_blank(container):
    """On a right-to-left page the label precedes the blank, which puts it on the right.
    Searching only leftwards leaves every field on an Urdu form unlabelled."""
    from app.services.label_association_service import LabelAssociationService

    blank = field("", x=60, y=300, w=560, h=44)
    words = [
        word("نام", 880, 300, w=60, h=26, ident="w1"),
        word("کا", 955, 300, w=40, h=26, ident="w2"),
        word("والد", 1010, 300, w=70, h=26, ident="w3"),
    ]
    ocr = OCRResult(page_index=0, full_text="والد کا نام", words=words, **IMAGE)
    assert ocr.full_text and is_rtl(ocr.full_text)
    associated = LabelAssociationService(container.semantics).associate([blank], ocr)
    # Reading order, not screen order: rightmost word first.
    assert associated[0].label == "والد کا نام"
    assert container.semantics.resolve(associated[0].label, None).entry.id == "father_name"


def test_wide_label_column_does_not_truncate_the_label(container):
    """Government forms reserve a third of the page for labels. A tight proximity cap
    turned 'Date of Birth' into 'Birth', which matches nothing."""
    from app.services.label_association_service import LabelAssociationService

    blank = field("", x=480, y=300, w=460, h=44)
    words = [
        word("Date", 60, 302, w=70, h=24, ident="w1"),
        word("of", 140, 302, w=30, h=24, ident="w2"),
        word("Birth", 180, 302, w=80, h=24, ident="w3"),
    ]
    ocr = OCRResult(page_index=0, full_text="Date of Birth", words=words, **IMAGE)
    associated = LabelAssociationService(container.semantics).associate([blank], ocr)
    assert associated[0].label == "Date of Birth"
    assert associated[0].field_type == FieldType.DATE


def test_label_language_is_recorded_without_touching_the_label(container):
    from app.services.label_association_service import LabelAssociationService

    blank = field("", x=480, y=300, w=400, h=44)
    words = [word("ಹೆಸರು", 60, 302, w=140, h=26, ident="w1")]
    ocr = OCRResult(page_index=0, full_text="ಹೆಸರು", words=words, **IMAGE)
    associated = LabelAssociationService(container.semantics).associate([blank], ocr)
    assert associated[0].label == "ಹೆಸರು"
    assert associated[0].label_script == "kannada"
    assert associated[0].label_language == "kn"


# --- document-level behaviour --------------------------------------------------------


def _ready_record(container, fields, scripts, suggested):
    from app.models.common import DocumentStatus, ProcessingStage
    from app.models.document import DocumentRecord, KnownFormMatch

    record = DocumentRecord(
        id="doc-unknown",
        original_filename="form.png",
        original_path="form.png",
        mime_type="image/png",
        category=DocumentCategory.OTHER,
        status=DocumentStatus.READY,
        stage=ProcessingStage.READY,
        fields=fields,
        form_match=KnownFormMatch(unknown=True, score=0.1),
        scripts=scripts,
        suggested_language=suggested,
    )
    container.documents.save(record)
    return record


def test_bundle_endpoint_returns_every_field_in_every_language(container):
    fields = [field("Full Name", id="a"), field("مستقل پتہ", FieldType.MULTILINE, id="b")]
    container.document_service._resolve_semantics(fields)
    _ready_record(container, fields, ["latin", "arabic"], Language.URDU)

    response = container.document_service.guidance_bundles(
        "doc-unknown", GuidanceBundleRequest()
    )
    assert len(response.bundles) == 2
    assert response.llm_used is False
    for bundle in response.bundles:
        assert set(bundle.languages) == set(ALL_LANGUAGES)
    container.document_service.delete("doc-unknown")


def test_suggested_language_follows_the_printed_script(container):
    from app.services.label_association_service import LabelAssociationService

    service = container.document_service
    association = LabelAssociationService(container.semantics)
    urdu = [field("والد کا نام", id="a")]
    association.tag_script(urdu[0])
    assert service._suggested_language(urdu, []) == Language.URDU

    kannada = [field("ಪೂರ್ಣ ಹೆಸರು", id="b")]
    association.tag_script(kannada[0])
    assert service._suggested_language(kannada, []) == Language.KANNADA

    # A bilingual form prefers the regional column over the English headings.
    mixed = [field("Full Name", id="c"), field("पूरा नाम", id="d")]
    for item in mixed:
        association.tag_script(item)
    assert service._suggested_language(mixed, []) == Language.HINDI


def test_single_language_guidance_matches_the_bundle(container):
    """The original single-language endpoint must not drift from the bundle."""
    fields = [field("Mobile Number", id="a")]
    container.document_service._resolve_semantics(fields)
    _ready_record(container, fields, ["latin"], Language.ENGLISH)
    for language in ALL_LANGUAGES:
        one = container.document_service.guide(
            "doc-unknown", GuidanceRequest(field_id="a", language=language)
        )
        bundle = container.document_service.guidance_bundles(
            "doc-unknown", GuidanceBundleRequest(field_ids=["a"], languages=[language])
        )
        assert one.what_to_enter == bundle.bundles[0].languages[language].what_to_enter
    container.document_service.delete("doc-unknown")


def test_plausible_label_rejects_noise_but_keeps_regional_text(container):
    check = container.document_service._plausible_label
    assert check("ವೃತ್ತಿ")
    assert check("دستخط")
    assert check("Date of Birth")
    assert not check("")
    assert not check("೨,")
    assert not check("ًالالاەئەه۔-۔۔-۔+,ص,مص+۸۰-ص")
    assert not check("|")


def test_ask_refuses_to_invent_an_answer_in_every_language(container):
    from app.models.guidance import AskRequest

    target = field("Full Name")
    for language in ALL_LANGUAGES:
        response = container.document_service.guidance.ask(
            target, AskRequest(question="what should i write as my name", language=language), None, []
        )
        assert response.refused is True
        assert dominant_script(response.answer) == EXPECTED_SCRIPT[language]


def test_llm_payload_in_the_wrong_script_is_discarded(container):
    """A model asked for Hindi often answers in romanised Hindi. That is not a Hindi
    translation and must not be shown under a Hindi heading."""
    from app.services.llm_service import LLMService

    class Romanised:
        def available(self):
            return True

        def generate_sync(self, **kwargs):
            return (
                '{"simple_label": {"hi": "Poora naam"}, '
                '"what_to_enter": {"hi": "Apna poora naam likhen."}, '
                '"requires_verification": true}'
            )

    assert LLMService(Romanised()).interpret_field_multilingual("x", [Language.HINDI]) is None


def test_llm_payload_in_the_right_script_is_kept(container):
    from app.services.llm_service import LLMService

    class Native:
        def available(self):
            return True

        def generate_sync(self, **kwargs):
            return (
                '{"simple_label": {"hi": "पूरा नाम"}, '
                '"what_to_enter": {"hi": "अपना पूरा नाम लिखें।"}, '
                '"requires_verification": true}'
            )

    payload = LLMService(Native()).interpret_field_multilingual("x", [Language.HINDI])
    assert payload is not None
    assert payload.for_language(Language.HINDI).what_to_enter.startswith("अपना")
