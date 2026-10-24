"""Tests for page-structure extraction and the page interpreter.

Built around the shape of a real ruled government form, because that is where the
previous approach failed: a table is a grid of nested rectangles, and treating every
rectangle as a candidate field kept the outer border and discarded every cell inside it.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.models.common import ALL_LANGUAGES, Language, PixelBoundingBox
from app.models.interpretation import ClassifiedField, ClassifiedPage, FilledBy, InterpretedPage
from app.models.ocr import OCRLine, OCRResult, OCRWord
from app.services.form_interpretation_service import FormInterpretationService, _Breaker
from app.services.page_structure_service import PageStructureService

WIDTH, HEIGHT = 1200, 900
IMAGE = dict(image_width=WIDTH, image_height=HEIGHT)


def _page(path, rows, two_columns=True):
    """Draw a ruled table: a caption column and an empty column, like a parentage block."""
    image = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
    top, row_h, left, right = 120, 60, 100, 1100
    split = 520
    for index in range(len(rows) + 1):
        y = top + index * row_h
        cv2.line(image, (left, y), (right, y), (0, 0, 0), 2)
    cv2.line(image, (left, top), (left, top + len(rows) * row_h), (0, 0, 0), 2)
    cv2.line(image, (right, top), (right, top + len(rows) * row_h), (0, 0, 0), 2)
    if two_columns:
        cv2.line(image, (split, top), (split, top + len(rows) * row_h), (0, 0, 0), 2)
    cv2.imencode(".png", image)[1].tofile(str(path))
    return top, row_h, left, split


def _ocr(words_spec):
    words = []
    for index, (text, x, y) in enumerate(words_spec):
        words.append(
            OCRWord(
                id=f"w{index}",
                text=text,
                confidence=90,
                page_index=0,
                pixel=PixelBoundingBox(
                    x=x, y=y, width=max(20, len(text) * 11), height=22,
                    image_width=WIDTH, image_height=HEIGHT,
                ),
                line_id=index,
                block_id=1,
            )
        )
    lines = [
        OCRLine(id=index, text=word.text, word_ids=[word.id], box=word.box)
        for index, word in enumerate(words)
    ]
    return OCRResult(
        page_index=0,
        full_text="\n".join(word.text for word in words),
        image_width=WIDTH,
        image_height=HEIGHT,
        words=words,
        lines=lines,
    )


def test_every_table_row_yields_a_field(tmp_path):
    """The failure that started this: a six-row parentage table produced no fields at all,
    because the outer table rectangle suppressed all of its cells."""
    path = tmp_path / "table.png"
    captions = ["Fathers Name", "Fathers EPIC No", "Mothers Name", "Mothers EPIC No"]
    top, row_h, left, _ = _page(path, captions)
    ocr = _ocr([(text, left + 12, top + index * row_h + 18) for index, text in enumerate(captions)])

    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert len(layout.tables) == 1
    assert layout.tables[0].row_count == len(captions)
    assert len(layout.blanks) == len(captions), [b.caption for b in layout.blanks]
    assert [blank.caption for blank in layout.blanks] == captions
    assert all(blank.origin == "table_cell" for blank in layout.blanks)


def test_a_caption_and_its_blank_in_one_cell(tmp_path):
    """`Elector Name: ______` is one cell holding both a caption and a place to write."""
    path = tmp_path / "inline.png"
    top, row_h, left, _ = _page(path, ["Elector Name:", "District:"], two_columns=False)
    ocr = _ocr([("Elector Name:", left + 12, top + 18), ("District:", left + 12, top + row_h + 18)])

    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert len(layout.blanks) == 2
    assert all(blank.origin == "inline_cell" for blank in layout.blanks)
    # The writing area starts after the caption, not on top of it.
    first = layout.blanks[0]
    assert first.x > left + 12


def test_column_header_distinguishes_identical_captions(tmp_path):
    """Two cells captioned the same way under different headers are different questions.

    This is the whole reason the structure carries headers: without them, the two
    `Relative's Name:` cells on the real form are indistinguishable.
    """
    path = tmp_path / "headers.png"
    top, row_h, left, split = _page(path, ["hdr", "Relatives Name:", "District:"])
    ocr = _ocr(
        [
            ("Details of the Elector", left + 12, top + 18),
            ("Details of the Relative", split + 12, top + 18),
            ("Relatives Name:", left + 12, top + row_h + 18),
            ("Relatives Name:", split + 12, top + row_h + 18),
            ("District:", left + 12, top + 2 * row_h + 18),
            ("District:", split + 12, top + 2 * row_h + 18),
        ]
    )
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert layout.tables[0].header_rows == [0]
    headers = {blank.column_header for blank in layout.blanks if blank.column_header}
    assert "Details of the Elector" in headers
    assert "Details of the Relative" in headers
    # Same caption, different header: the pair is now separable.
    named = [blank for blank in layout.blanks if "Relatives" in blank.caption]
    assert len(named) == 2
    assert named[0].column_header != named[1].column_header


def test_header_row_is_not_mistaken_for_data(tmp_path):
    """A row of `Caption: ____` cells is data, however full of text it looks."""
    path = tmp_path / "hdr.png"
    top, row_h, left, split = _page(path, ["hdr", "Elector Name:", "EPIC No:"])
    ocr = _ocr(
        [
            ("Details of the Elector", left + 12, top + 18),
            ("Details of the Relative", split + 12, top + 18),
            ("Elector Name:", left + 12, top + row_h + 18),
            ("Name:", split + 12, top + row_h + 18),
            ("EPIC No:", left + 12, top + 2 * row_h + 18),
            ("EPIC No:", split + 12, top + 2 * row_h + 18),
        ]
    )
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert layout.tables[0].header_rows == [0]
    # The "Elector Name:" row must still produce its own fields.
    captions = [blank.caption for blank in layout.blanks]
    assert "Elector Name:" in captions
    assert "Name:" in captions


def test_prose_page_proposes_no_fields(tmp_path):
    """An information sheet has no fields. Inventing some is worse than finding none."""
    path = tmp_path / "prose.png"
    image = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
    cv2.imencode(".png", image)[1].tofile(str(path))
    sentences = [
        "Applicants can check their name in the previous rolls:",
        "Provide any document for Self from the list given below:",
        "If born in India before 01.07.1987",
        "Birth Certificate issued by the competent authority",
        "Passport",
        "Forest Right Certificate",
        "National Register of Citizens",
        "Family Register prepared by State authorities",
        "Any land allotment certificate by the Government",
    ]
    ocr = _ocr([(text, 100, 100 + index * 40) for index, text in enumerate(sentences)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert layout.tables == []
    assert layout.blanks == [], [b.caption for b in layout.blanks]
    assert layout.looks_like_prose is True


def test_short_caption_with_a_colon_is_a_field(tmp_path):
    path = tmp_path / "colon.png"
    image = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
    cv2.imencode(".png", image)[1].tofile(str(path))
    ocr = _ocr([("Applicant's Name:", 100, 200), ("Mobile Number:", 100, 260)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert {blank.caption for blank in layout.blanks} == {"Applicant's Name", "Mobile Number"}
    assert all(blank.origin == "colon_gap" for blank in layout.blanks)


# --- interpreter ------------------------------------------------------------------


class _Recorder:
    """A provider stand-in. Records prompts and replies from a script."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.models = []

    def available(self):
        return True

    def generate_sync(self, *, system_prompt, user_prompt, max_tokens=None, **kwargs):
        return self._next(user_prompt)

    def generate_with_model(self, *, model, system_prompt, user_prompt, **kwargs):
        self.models.append(model)
        return self._next(user_prompt)

    def _next(self, user_prompt):
        self.prompts.append(user_prompt)
        if not self.replies:
            raise AssertionError("provider called more times than the test scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _layout_with(blanks_spec, tmp_path):
    path = tmp_path / "x.png"
    captions = [caption for caption, _ in blanks_spec]
    top, row_h, left, _ = _page(path, captions)
    ocr = _ocr([(caption, left + 12, top + index * row_h + 18) for index, (caption, _) in enumerate(blanks_spec)])
    return PageStructureService().analyse(str(path), ocr, 0)


def test_classification_maps_blanks_onto_dictionary_concepts(container, tmp_path):
    layout = _layout_with([("Fathers Name", None), ("Mothers Name", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]
    reply = {
        "fields": [
            {"id": ids[0], "is_field": True, "fill_by": "applicant", "concept": "father_name",
             "needs_detail": True, "label": "Father's name", "what_to_enter": "Write your father's full name.",
             "validation": "person_name", "confidence": 0.95},
            {"id": ids[1], "is_field": True, "fill_by": "applicant", "concept": "mother_name",
             "needs_detail": True, "label": "Mother's name", "what_to_enter": "Write your mother's full name.",
             "validation": "person_name", "confidence": 0.95},
        ]
    }
    import json

    service = FormInterpretationService(_Recorder([json.dumps(reply)]), dictionary=container.dictionary)
    result = service.classify(layout, form_title="Demo")
    assert set(result) == set(ids)
    assert result[ids[0]].concept == "father_name"
    assert result[ids[0]].needs_detail is True


def test_classifier_is_given_the_column_header(container, tmp_path):
    """The prompt must actually carry the context, or the model cannot use it."""
    import json

    layout = _layout_with([("Name:", None)], tmp_path)
    layout.blanks[0].column_header = "Details of the Relative, in the last SIR"
    ids = [blank.id for blank in layout.blanks]
    reply = json.dumps({"fields": [{"id": ids[0], "concept": "relative_name", "label": "Relative's name",
                                    "what_to_enter": "x", "confidence": 0.9}]})
    provider = _Recorder([reply])
    FormInterpretationService(provider, dictionary=container.dictionary).classify(layout)
    assert "Details of the Relative" in provider.prompts[0]


def test_an_unknown_concept_is_not_trusted(container, tmp_path):
    """A concept we have no authored text for must not be recorded as if we did."""
    import json

    layout = _layout_with([("Shelf Code", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]
    reply = json.dumps({"fields": [{"id": ids[0], "concept": "invented_concept", "label": "Shelf code",
                                    "what_to_enter": "x", "confidence": 0.9}]})
    service = FormInterpretationService(_Recorder([reply]), dictionary=container.dictionary)
    result = service.classify(layout)
    assert result[ids[0]].concept is None


def test_a_rejected_blank_is_dropped(container, tmp_path):
    import json

    layout = _layout_with([("Heading", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]
    reply = json.dumps({"fields": [{"id": ids[0], "is_field": False, "label": "", "what_to_enter": ""}]})
    service = FormInterpretationService(_Recorder([reply]), dictionary=container.dictionary)
    assert service.classify(layout) == {}
    assert service.stats.fields_rejected == 1


def test_ids_the_model_invented_are_ignored(container, tmp_path):
    """The page analysis decides which blanks exist; the model only labels them."""
    import json

    layout = _layout_with([("Fathers Name", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]
    reply = json.dumps(
        {
            "fields": [
                {"id": ids[0], "concept": "father_name", "label": "Father", "what_to_enter": "x", "confidence": 0.9},
                {"id": "hallucinated", "concept": "full_name", "label": "Ghost", "what_to_enter": "y", "confidence": 0.9},
            ]
        }
    )
    service = FormInterpretationService(_Recorder([reply]), dictionary=container.dictionary)
    result = service.classify(layout)
    assert set(result) == {ids[0]}


def test_malformed_json_is_retried_then_given_up_on(container, tmp_path):
    layout = _layout_with([("Fathers Name", None)], tmp_path)
    provider = _Recorder(["not json", "still not json"])
    service = FormInterpretationService(provider, dictionary=container.dictionary, max_attempts=2)
    assert service.classify(layout) == {}
    assert len(provider.prompts) == 2
    assert service.stats.failures >= 1


def test_interpreter_absence_is_not_an_error(container, tmp_path):
    class Down:
        def available(self):
            return False

        def generate_sync(self, **kwargs):  # pragma: no cover - must not be called
            raise AssertionError("provider called while unavailable")

    layout = _layout_with([("Fathers Name", None)], tmp_path)
    service = FormInterpretationService(Down(), dictionary=container.dictionary)
    assert service.classify(layout) == {}


def test_results_are_cached_by_structure(container, tmp_path):
    """Re-reading the same form must not pay for the model twice."""
    import json

    layout = _layout_with([("Fathers Name", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]
    reply = json.dumps({"fields": [{"id": ids[0], "concept": "father_name", "label": "Father",
                                    "what_to_enter": "x", "confidence": 0.9}]})
    provider = _Recorder([reply])
    service = FormInterpretationService(provider, dictionary=container.dictionary)
    first = service.classify(layout)
    second = service.classify(layout)
    assert first.keys() == second.keys()
    assert len(provider.prompts) == 1
    assert service.stats.cache_hits == 1


def test_failover_gives_up_within_an_overall_deadline():
    """The retry matrix must be bounded in time, not just in attempts.

    Two keys and two models is four attempts per call, and the caller retries once. A
    provider that hangs rather than refusing could otherwise hold one batch for eight
    full timeouts, and an upload of several batches for the better part of an hour --
    long enough that the page never finishes and the circuit breaker never trips.
    """
    import time as clock

    from app.providers.llm.groq_provider import GroqProvider

    class Hanging(GroqProvider):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.calls = 0

        def _complete(self, *args, **kwargs):
            self.calls += 1
            clock.sleep(0.3)
            raise RuntimeError("503 overloaded")

    provider = Hanging(["k1", "k2"], ["m1", "m2"], "http://example", timeout_seconds=1, attempt_budget=1.0)
    started = clock.monotonic()
    with pytest.raises(Exception):
        provider.generate_sync(system_prompt="s", user_prompt="u")
    elapsed = clock.monotonic() - started
    assert elapsed < 1.4, f"failover ran for {elapsed:.2f}s with a 1s budget"
    assert provider.calls < 4


def test_document_context_is_read_before_fields(container):
    """A field's meaning comes from the document it sits in.

    "AC No." is an Assembly Constituency number on an electoral form and an account
    number on a banking one; the caption is identical. The whole-document pass is what
    settles which kind of form this is, so it has to run first and its glossary has to
    reach the per-field request.
    """
    import json

    from app.models.interpretation import FormContext

    reply = json.dumps(
        {
            "title": "Annexure-IV Declaration Form",
            "authority": "Election Commission of India",
            "purpose": "Enrolment as a new elector",
            "glossary": {"AC": "Assembly Constituency", "EPIC": "Electoral Photo Identity Card"},
            "notes": ["Values must match the last electoral roll"],
            "office_sections": ["BLO's undertaking"],
            "confidence": 0.9,
        }
    )
    provider = _Recorder([reply])
    service = FormInterpretationService(provider, dictionary=container.dictionary)
    context = service.read_context(["Annexure-IV Declaration Form", "AC Name:", "EPIC No."])
    assert isinstance(context, FormContext)
    assert context.glossary["AC"] == "Assembly Constituency"
    assert service.stats.context_reads == 1
    # The briefing has to be compact enough to prepend to every later request.
    assert "Assembly Constituency" in context.summary()


def test_the_glossary_reaches_the_field_request(container, tmp_path):
    """Establishing the context is useless if it does not travel with the fields."""
    import json

    from app.models.interpretation import FormContext

    layout = _layout_with([("AC No", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]
    context = FormContext(
        title="Declaration Form",
        authority="Election Commission of India",
        glossary={"AC": "Assembly Constituency"},
    )
    reply = json.dumps({"fields": [{"id": ids[0], "concept": None, "label": "Assembly Constituency number",
                                    "what_to_enter": "x", "confidence": 0.9}]})
    provider = _Recorder([reply])
    service = FormInterpretationService(provider, dictionary=container.dictionary)
    service.classify(layout, form_title="Declaration Form", context=context)
    assert "Assembly Constituency" in provider.prompts[0]
    assert "Election Commission of India" in provider.prompts[0]


def test_context_is_cached(container):
    import json

    reply = json.dumps({"title": "A form", "glossary": {"AC": "Assembly Constituency"}})
    provider = _Recorder([reply])
    service = FormInterpretationService(provider, dictionary=container.dictionary)
    lines = ["A form", "AC Name:"]
    first = service.read_context(lines)
    second = service.read_context(lines)
    assert first.title == second.title
    assert len(provider.prompts) == 1
    assert service.stats.cache_hits == 1


def test_context_pass_is_skipped_without_a_provider(container):
    class Down:
        def available(self):
            return False

        def generate_sync(self, **kwargs):  # pragma: no cover - must not be called
            raise AssertionError("provider called while unavailable")

    service = FormInterpretationService(Down(), dictionary=container.dictionary)
    assert service.read_context(["some text"]) is None


def test_glossary_accepts_a_list_of_objects():
    """Models answer this shape about as often as the one that was asked for."""
    from app.models.interpretation import FormContext

    context = FormContext.model_validate(
        {"title": "x", "glossary": [{"term": "AC", "meaning": "Assembly Constituency"}]}
    )
    assert context.glossary == {"AC": "Assembly Constituency"}


def test_an_assembly_constituency_is_not_a_bank_account(container):
    """The wording that caused the original complaint.

    "AC Number" and "account number" are close as run-together strings, which is how an
    electoral form's Assembly Constituency number came to be explained as a bank account
    with instructions to copy it from a passbook. Token alignment must refuse it.
    """
    for label in ("AC Number", "AC No.", "AC Name"):
        match = container.semantics.resolve(label, None)
        assert match is None or match.entry.id != "bank_account_number", label
    # The genuine wording still resolves.
    assert container.semantics.resolve("Account Number", None).entry.id == "bank_account_number"


def test_a_no_concept_verdict_blocks_the_word_match(container, tmp_path):
    """When the page has been read and no concept fits, the lexical matcher must not
    get a second go at the same label.

    This is the bug in its final hiding place. On an electoral form the model correctly
    returned no concept for "AC Number (previous roll)"; guidance then matched that
    wording against the dictionary, landed on bank account number, and told the user to
    copy it from their passbook. A word match cannot overrule a reading of the page.
    """
    from app.models.common import FieldType, PixelBoundingBox
    from app.models.fields import DetectedField
    from app.models.interpretation import ClassifiedField
    from app.utils.bounding_boxes import normalize_box

    box = normalize_box(PixelBoundingBox(x=1, y=1, width=40, height=20, image_width=100, image_height=100))
    field = DetectedField(
        id="f1",
        page_index=0,
        label="AC Number (previous roll)",
        display_label="AC Number (previous roll)",
        field_type=FieldType.TEXT,
        input_box=box,
        confidence=0.8,
    )
    guidance = container.document_service.guidance

    # With a reading of the page that found no concept, the word match is refused.
    reading = ClassifiedField(id="f1", concept=None, label="AC Number", what_to_enter="x", confidence=0.9)
    guided = guidance.bundle_for_field(field, None, [], classified=reading)
    assert guided.semantic_id != "bank_account_number"
    for language in ALL_LANGUAGES:
        text = guided.languages[language].what_to_enter.lower()
        assert "passbook" not in text
        assert "account number" not in text


def test_a_failed_classify_batch_is_split_not_lost(container, tmp_path):
    """Classification is the step everything else rests on.

    Losing a batch here does not degrade those blanks a little, it drops them out of the
    system: no display name, no concept, no four-language text, and they fall back to
    matching their own caption. That is how one "AC Number" cell came out as the
    relative's constituency number and the identical one beside it as "the printed label
    asks for a number or code".
    """
    import json

    layout = _layout_with([("AC Number", None), ("Part No", None), ("Sr No", None), ("AC Number", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]

    def reply(subset):
        return json.dumps(
            {"fields": [{"id": i, "is_field": True, "concept": None, "label": i,
                         "what_to_enter": "x", "confidence": 0.9} for i in subset]}
        )

    provider = _Recorder(["not json", "not json", reply(ids[:2]), reply(ids[2:])])
    service = FormInterpretationService(provider, dictionary=container.dictionary, classify_batch=4)
    result = service.classify(layout, form_title="t")
    assert set(result) == set(ids), "every blank should survive a failed batch"


def test_a_partial_classify_reply_is_topped_up(container, tmp_path):
    """A reply covering only some of the batch must not leave the rest unread."""
    import json

    layout = _layout_with([("AC Number", None), ("Part No", None)], tmp_path)
    ids = [blank.id for blank in layout.blanks]
    first = json.dumps({"fields": [{"id": ids[0], "is_field": True, "concept": None,
                                    "label": "AC Number", "what_to_enter": "x", "confidence": 0.9}]})
    second = json.dumps({"fields": [{"id": ids[1], "is_field": True, "concept": None,
                                     "label": "Part No", "what_to_enter": "y", "confidence": 0.9}]})
    provider = _Recorder([first, second])
    service = FormInterpretationService(provider, dictionary=container.dictionary, classify_batch=2)
    result = service.classify(layout, form_title="t")
    assert set(result) == set(ids)
    assert len(provider.prompts) == 2


def test_a_refusing_provider_is_not_asked_twice_more_when_classifying(container, tmp_path):
    layout = _layout_with([("A", None), ("B", None), ("C", None), ("D", None)], tmp_path)
    provider = _Recorder(["not json"] * 12)
    service = FormInterpretationService(provider, dictionary=container.dictionary, classify_batch=4)
    service.breaker.threshold = 1
    assert service.classify(layout) == {}
    assert len(provider.prompts) <= 2, f"made {len(provider.prompts)} calls while refused"


def test_a_page_reading_is_not_badged_as_a_guess(container):
    """An answer read from the page with 88% confidence must not also claim to be
    inferred from the wording. Showing both at once contradicts itself."""
    from app.models.common import FieldType, GuidanceSource, PixelBoundingBox
    from app.models.fields import DetectedField
    from app.models.interpretation import InterpretedField
    from app.utils.bounding_boxes import normalize_box

    box = normalize_box(PixelBoundingBox(x=1, y=1, width=40, height=20, image_width=100, image_height=100))
    field = DetectedField(id="f1", page_index=0, label="Part No.", field_type=FieldType.TEXT,
                          input_box=box, confidence=0.8)
    interpreted = InterpretedField(
        id="f1",
        what_to_enter={"en": "Enter the part number of the elector as shown in the last SIR."},
        label={"en": "Part No."},
        confidence=0.9,
    )
    bundle = container.document_service.guidance.bundle_for_field(field, None, [], interpreted=interpreted)
    english = bundle.languages[Language.ENGLISH]
    assert english.source is GuidanceSource.PAGE_INTERPRETATION
    assert english.inferred is False
    assert bundle.inferred is False
    # It still asks to be checked against the form.
    assert english.requires_verification


def test_a_failed_describe_batch_is_split_not_lost(container, tmp_path):
    """One unusable reply must not cost every field in the batch.

    A batch is answered as a single JSON object. Before this, one malformed reply left
    four of thirty fields on a real form with nothing but a generic "this asks for a
    number" while the rest had full descriptions. Bisecting recovers what it can.
    """
    import json

    layout = _layout_with([("Alpha", None), ("Beta", None), ("Gamma", None), ("Delta", None)], tmp_path)
    blanks = layout.blanks
    ids = [blank.id for blank in blanks]

    def good(subset):
        return json.dumps(
            {
                "fields": [
                    {"id": i, "is_field": True, "what_to_enter": {"en": f"Write {i}."}, "label": {"en": i}}
                    for i in subset
                ]
            }
        )

    # Whole batch fails, each half succeeds.
    provider = _Recorder(["not json", "not json", good(ids[:2]), good(ids[2:])])
    service = FormInterpretationService(provider, dictionary=container.dictionary, describe_batch=4)
    result = service.describe(layout, blanks, {}, form_title="t")
    assert set(result) == set(ids), "bisecting should recover every field"


def test_a_partial_describe_reply_is_topped_up(container, tmp_path):
    """A reply that answers only some of the batch gets a follow-up for the rest."""
    import json

    layout = _layout_with([("Alpha", None), ("Beta", None)], tmp_path)
    blanks = layout.blanks
    ids = [blank.id for blank in blanks]
    first = json.dumps({"fields": [{"id": ids[0], "is_field": True,
                                    "what_to_enter": {"en": "Write alpha."}, "label": {"en": "Alpha"}}]})
    second = json.dumps({"fields": [{"id": ids[1], "is_field": True,
                                     "what_to_enter": {"en": "Write beta."}, "label": {"en": "Beta"}}]})
    provider = _Recorder([first, second])
    service = FormInterpretationService(provider, dictionary=container.dictionary, describe_batch=2)
    result = service.describe(layout, blanks, {}, form_title="t")
    assert set(result) == set(ids)
    assert len(provider.prompts) == 2


def test_a_refusing_provider_is_not_asked_twice_more(container, tmp_path):
    """Bisecting a failed batch helps when a reply was malformed. It does not help when
    the provider is refusing outright -- it just asks the same question again, which is
    the opposite of what a rate limit calls for."""
    layout = _layout_with([("Alpha", None), ("Beta", None), ("Gamma", None), ("Delta", None)], tmp_path)
    provider = _Recorder(["not json"] * 12)
    service = FormInterpretationService(provider, dictionary=container.dictionary, describe_batch=4)
    service.breaker.threshold = 1  # open immediately on the first failure
    result = service.describe(layout, layout.blanks, {}, form_title="t")
    assert result == {}
    # Two attempts on the whole batch, then it stops rather than splitting.
    assert len(provider.prompts) <= 2, f"made {len(provider.prompts)} calls while refused"


def test_a_classified_field_keeps_its_reading_when_the_language_step_fails(container):
    """Two identical cells in one row must not be explained differently.

    The classifier reads every blank; the four-language step can fail for a batch. When
    it did, one "AC Number" cell was described as the relative's constituency number and
    the identical cell beside it as "the printed label asks for a number or code". The
    classifier's reading has to survive that.
    """
    from app.models.common import FieldType, GuidanceSource, PixelBoundingBox
    from app.models.fields import DetectedField
    from app.models.interpretation import ClassifiedField
    from app.utils.bounding_boxes import normalize_box

    box = normalize_box(PixelBoundingBox(x=1, y=1, width=40, height=20, image_width=100, image_height=100))
    field = DetectedField(
        id="f1",
        page_index=0,
        label="AC Number",
        display_label="Assembly Constituency number (elector)",
        field_type=FieldType.TEXT,
        input_box=box,
        confidence=0.8,
    )
    reading = ClassifiedField(
        id="f1",
        concept=None,
        label="Assembly Constituency number (elector)",
        what_to_enter="Enter the Assembly Constituency number from the last SIR.",
        validation="alphanumeric",
        confidence=0.9,
    )
    bundle = container.document_service.guidance.bundle_for_field(field, None, [], classified=reading)
    english = bundle.languages[Language.ENGLISH]
    assert "Assembly Constituency number" in english.what_to_enter
    assert english.source is GuidanceSource.PAGE_INTERPRETATION
    assert english.requires_verification
    # The other languages still answer, in their own script, rather than going blank.
    for language in ALL_LANGUAGES:
        assert bundle.languages[language].what_to_enter.strip()


def test_web_lookup_is_off_unless_a_search_model_is_named(container):
    """An ordinary chat model asked to "search" answers from memory. That is not a
    search, and inventing background about an official form is worse than having none."""
    service = FormInterpretationService(_Recorder([]), dictionary=container.dictionary)
    from app.models.interpretation import FormContext

    assert service.web_search_model == ""
    assert service.look_up_on_the_web(FormContext(title="Some Form"), ["text"]) is None


def test_web_findings_only_fill_gaps(container):
    """The paper in hand is the authority on itself. A search result may be about a
    different edition, or a different form with a similar name."""
    import json

    from app.models.interpretation import FormContext

    reply = json.dumps(
        {
            "official_name": "Declaration Form (Annexure IV)",
            "authority": "Election Commission of India",
            "summary": "Used when enrolling as a new elector.",
            "glossary": {"EPIC": "WRONG - from the web", "SIR": "Special Intensive Revision"},
            "sources": ["eci.gov.in"],
            "confidence": 0.8,
        }
    )
    provider = _Recorder([reply])
    service = FormInterpretationService(
        provider, dictionary=container.dictionary, web_search_model="groq/compound-mini"
    )
    context = FormContext(title="Annexure-IV Declaration Form", glossary={"EPIC": "read from the page"})
    found = service.look_up_on_the_web(context, ["EPIC No.", "AC Name"])
    assert found is not None
    context.merge_web(found)
    assert context.glossary["EPIC"] == "read from the page", "the page must win"
    assert context.glossary["SIR"] == "Special Intensive Revision", "the gap should be filled"
    assert context.authority == "Election Commission of India"
    assert context.web_sources == ["eci.gov.in"]
    # The initialisms the page left unexplained are put to the search explicitly.
    assert "EPIC" in provider.prompts[0]


def test_a_failed_web_lookup_never_costs_the_upload(container):
    from app.models.interpretation import FormContext

    class Exploding:
        def available(self):
            return True

        def generate_with_model(self, **kwargs):
            raise RuntimeError("search backend down")

    service = FormInterpretationService(
        Exploding(), dictionary=container.dictionary, web_search_model="groq/compound-mini"
    )
    assert service.look_up_on_the_web(FormContext(title="A Form"), ["text"]) is None


def test_useless_web_findings_are_discarded(container):
    import json

    from app.models.interpretation import FormContext

    empty = json.dumps({"official_name": "", "summary": "", "glossary": {}, "confidence": 0.0})
    service = FormInterpretationService(
        _Recorder([empty]), dictionary=container.dictionary, web_search_model="groq/compound-mini"
    )
    assert service.look_up_on_the_web(FormContext(title="A Form"), ["text"]) is None


def test_no_output_budget_is_sent_to_the_model():
    """These models reason before they answer, and the reasoning is charged against
    `max_tokens` on this provider. Setting it does not shorten the reply, it empties it:
    measured on a two-page form, budgets of 1600 and 6000 both returned zero characters
    while no budget returned a complete answer. Reply length is controlled by batching.
    """
    from app.services import form_interpretation_service as module

    assert module.CONTEXT_MAX_TOKENS is None
    assert module.CLASSIFY_MAX_TOKENS is None
    assert module.DESCRIBE_MAX_TOKENS is None


def test_the_sdk_does_not_retry_underneath_our_own_retries():
    """One retry loop, not two nested ones.

    This class already retries across keys and then across models, under a deadline.
    Leaving the OpenAI SDK's own retries switched on puts a second back-off loop inside
    each of those attempts, so one unreachable host becomes a dozen waits. Measured
    during a real DNS outage before this was fixed: 256 seconds to fall back to the
    offline path, where it should be about a second.
    """
    from app.providers.llm import groq_provider

    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = self

        @property
        def completions(self):
            raise RuntimeError("stop here; only the constructor matters")

    original = groq_provider.OpenAI
    groq_provider.OpenAI = FakeClient
    try:
        provider = groq_provider.GroqProvider(["k"], ["m"], "http://example", timeout_seconds=5)
        with pytest.raises(Exception):
            provider.generate_sync(system_prompt="s", user_prompt="u")
    finally:
        groq_provider.OpenAI = original

    assert captured.get("max_retries") == 0, "the SDK must not retry underneath us"
    assert captured.get("timeout") == 5


def test_circuit_opens_after_repeated_failures():
    breaker = _Breaker(threshold=3, cooldown=600)
    assert breaker.allow()
    for _ in range(3):
        breaker.record_failure()
    assert breaker.allow() is False
    breaker.record_success()
    assert breaker.allow() is True


def test_wrong_script_languages_are_dropped(container, tmp_path):
    """Romanised Hindi is not Hindi, and must not appear under a Hindi heading."""
    from app.models.interpretation import InterpretedField

    service = FormInterpretationService(_Recorder([]), dictionary=container.dictionary)
    field = InterpretedField(
        id="x",
        what_to_enter={"en": "Write your name.", "hi": "Apna naam likhen.", "kn": "ನಿಮ್ಮ ಹೆಸರು ಬರೆಯಿರಿ."},
        label={"en": "Name", "hi": "Naam", "kn": "ಹೆಸರು"},
    )
    cleaned = service._keep_native_languages(field)
    assert set(cleaned.what_to_enter) == {"en", "kn"}
    assert "hi" not in cleaned.label
    assert service.stats.dropped_wrong_script == 1


@pytest.mark.parametrize(
    "value,expected",
    [("person_name", "person_name"), ("PERSON_NAME", "person_name"), ("made_up_kind", "text"), ("", "text")],
)
def test_only_known_validation_kinds_are_accepted(value, expected):
    """A hallucinated rule must not be able to reject a user's correct answer."""
    assert ClassifiedField(id="x", validation=value).validation == expected


def test_office_fields_are_marked():
    field = ClassifiedField(id="x", fill_by="office")
    assert field.fill_by is FilledBy.OFFICE
    assert ClassifiedField(id="y", fill_by="nonsense").fill_by is FilledBy.APPLICANT


def test_empty_pages_parse_to_nothing():
    assert ClassifiedPage().fields == []
    assert InterpretedPage().by_id() == {}


# --- page cropping ------------------------------------------------------------------


def test_a_table_is_not_mistaken_for_the_page_edge(tmp_path):
    """Cropping to an interior rectangle deletes the rest of the document.

    A form is full of large four-sided shapes. When the page-edge detector accepted any
    quad covering 18% of the image, the two-column table on a Kannada electoral form won
    and the processed page lost its title, its first three fields and its whole lower
    half -- which then looked like a field-detection failure rather than a cropping one.
    """
    from app.services.image_service import ImageService

    page = np.full((1400, 1000, 3), 255, np.uint8)
    # A bold table occupying the middle third of the page, and nothing else.
    cv2.rectangle(page, (120, 500), (880, 900), (0, 0, 0), 4)
    for offset in range(1, 4):
        y = 500 + offset * 100
        cv2.line(page, (120, y), (880, y), (0, 0, 0), 3)
    path = tmp_path / "page.png"
    cv2.imencode(".png", page)[1].tofile(str(path))

    assert ImageService()._largest_document_contour(page) is None


def test_a_photographed_page_on_a_background_is_still_cropped(tmp_path):
    """The feature this guard protects must keep working."""
    from app.services.image_service import ImageService

    photo = np.full((1400, 1000, 3), 40, np.uint8)  # dark desk
    cv2.rectangle(photo, (60, 70), (940, 1330), (255, 255, 255), -1)  # the sheet
    cv2.rectangle(photo, (60, 70), (940, 1330), (10, 10, 10), 3)
    contour = ImageService()._largest_document_contour(photo)
    assert contour is not None, "a page lying on a background should still be found"


# --- right-to-left pages --------------------------------------------------------------


def test_an_urdu_cell_puts_its_blank_left_of_the_caption(tmp_path):
    """Reading order decides which half of a cell is the writing space.

    Measured the left-to-right way on an Urdu form, every inline blank landed on top of
    its own caption.
    """
    from app.services.page_structure_service import Cell

    words = [
        OCRWord(
            id="w1",
            text="نام",
            confidence=90,
            page_index=0,
            pixel=PixelBoundingBox(x=700, y=210, width=180, height=24, **IMAGE),
            line_id=1,
        )
    ]
    cell = Cell(id="c", x=200, y=200, width=700, height=44, words=words)

    rtl = PageStructureService._inline_blank(cell, rtl=True)
    ltr = PageStructureService._inline_blank(cell, rtl=False)
    assert rtl is not None
    # The blank starts at the cell's left edge and stops before the caption.
    assert rtl[0] < 700
    assert rtl[0] + rtl[2] <= 700
    # Left-to-right would have found nothing here, because the caption runs to the edge.
    assert ltr is None


def test_an_urdu_row_caption_is_read_from_the_right(tmp_path):
    from app.services.page_structure_service import Blank, Cell, Table

    caption_cell = Cell(id="c1", x=600, y=100, width=300, height=40)
    caption_cell.words = [
        OCRWord(
            id="w1",
            text="والد کا نام",
            confidence=90,
            page_index=0,
            pixel=PixelBoundingBox(x=620, y=108, width=260, height=24, **IMAGE),
            line_id=1,
        )
    ]
    caption_cell.row = 0
    blank_cell = Cell(id="c2", x=200, y=100, width=390, height=40)
    blank_cell.row = 0
    table = Table(index=0, x=200, y=100, width=700, height=40, cells=[caption_cell, blank_cell])
    blank = Blank(id="b", x=blank_cell.x, y=blank_cell.y, width=blank_cell.width,
                  height=blank_cell.height, origin="table_cell", row=0)

    assert PageStructureService._row_caption(table, blank, rtl=True) == "والد کا نام"
    # Reading the wrong side finds nothing, which is how Urdu rows ended up unlabelled.
    assert PageStructureService._row_caption(table, blank, rtl=False) == ""


# --- worked examples -------------------------------------------------------------------


def test_examples_follow_the_reader_s_script(container):
    """A name shown in Latin letters beside Kannada guidance makes the reader switch
    script mid-sentence. Script-neutral values stay the same in every language."""
    from app.utils.text_normalization import dominant_script

    name = container.dictionary.get("full_name")
    assert dominant_script(name.example_for(Language.KANNADA)) == "kannada"
    assert dominant_script(name.example_for(Language.HINDI)) == "devanagari"
    assert dominant_script(name.example_for(Language.URDU)) == "arabic"
    assert dominant_script(name.example_for(Language.ENGLISH)) == "latin"

    # A date reads the same everywhere and keeps one example.
    born = container.dictionary.get("date_of_birth")
    assert born.example_for(Language.KANNADA) == born.example


def test_a_plain_string_example_from_the_model_still_works():
    """Older replies, and models that ignore the per-language shape, must not break."""
    from app.models.interpretation import InterpretedField

    field = InterpretedField.model_validate({"id": "x", "example": "15/08/1998"})
    assert field.example_for(Language.KANNADA) == "15/08/1998"
    assert field.example_for(Language.ENGLISH) == "15/08/1998"
    empty = InterpretedField.model_validate({"id": "y", "example": None})
    assert empty.example_for(Language.ENGLISH) is None


# --- blanks must not land on printed text ---------------------------------------------


def test_a_paragraph_ending_in_a_colon_is_not_a_field(tmp_path):
    """Word counts do not separate a caption from a sentence in an agglutinative
    language: a five-word Kannada sentence fills a line. The geometry does."""
    path = tmp_path / "prose.png"
    cv2.imencode(".png", np.full((HEIGHT, WIDTH, 3), 255, np.uint8))[1].tofile(str(path))
    # A line that runs most of the way across the page and happens to end in a colon.
    long_caption = "x" * 90
    ocr = _ocr([(f"{long_caption}:", 60, 200), ("Applicant Name:", 60, 260)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    captions = {blank.caption for blank in layout.blanks}
    assert "Applicant Name" in captions
    assert not any(caption.startswith("x" * 10) for caption in captions)


def test_nothing_is_proposed_on_top_of_words(tmp_path):
    path = tmp_path / "p.png"
    cv2.imencode(".png", np.full((HEIGHT, WIDTH, 3), 255, np.uint8))[1].tofile(str(path))
    ocr = _ocr([("Some printed words here", 100, 300)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    word = ocr.words[0].pixel
    assert PageStructureService.covers_text(layout, word.x + 5, word.y + 5, 40, 20) is True
    assert PageStructureService.covers_text(layout, word.x, word.y + 200, 40, 20) is False


def test_a_tick_box_inside_a_sentence_is_not_a_field(tmp_path):
    """A box printed at the end of a declaration is punctuation the reader ticks by hand.
    Offering an answer box for it while a real signature line goes undetected is the
    wrong way round."""
    from app.models.common import FieldType, PixelBoundingBox
    from app.models.fields import DetectedField
    from app.utils.bounding_boxes import normalize_box

    path = tmp_path / "p.png"
    cv2.imencode(".png", np.full((HEIGHT, WIDTH, 3), 255, np.uint8))[1].tofile(str(path))
    sentence = "I am applying for inclusion in the Electoral Roll through Form 6 and my name is not included"
    ocr = _ocr([(sentence, 60, 300), ("Savings", 60, 500)])
    layout = PageStructureService().analyse(str(path), ocr, 0)

    def mark(x: int, y: int) -> DetectedField:
        pixel = PixelBoundingBox(x=x, y=y, width=18, height=18, **IMAGE)
        return DetectedField(id=f"m{x}", page_index=0, label="", field_type=FieldType.CHECKBOX,
                             input_box=normalize_box(pixel), confidence=0.7)

    service = PageStructureService()
    before = len(layout.blanks)
    # Beside the long declaration sentence: printed text.
    service.add_marks(layout, [mark(int(ocr.words[0].pixel.x + ocr.words[0].pixel.width + 10), 300)])
    assert len(layout.blanks) == before, "a box beside a paragraph is not a field"


# --- signature areas -------------------------------------------------------------------


def test_a_signature_line_is_found_even_with_little_room_under_it(tmp_path):
    """The officer's block at the foot of the page was found and the elector's own, a few
    lines above, was not -- the one place on the form the applicant certainly must write.
    A signature line is a signature line whatever follows it."""
    path = tmp_path / "p.png"
    cv2.imencode(".png", np.full((HEIGHT, WIDTH, 3), 255, np.uint8))[1].tofile(str(path))
    ocr = _ocr(
        [
            ("Signature of Elector with date", 600, 300),
            ("BLO undertaking I have verified", 60, 360),
            ("BLO Signature", 600, 600),
        ]
    )
    layout = PageStructureService().analyse(str(path), ocr, 0)
    captions = {blank.caption for blank in layout.blanks if blank.origin == "space_below"}
    assert "Signature of Elector with date" in captions
    assert "BLO Signature" in captions


def test_a_kannada_signature_caption_is_recognised(tmp_path):
    path = tmp_path / "p.png"
    cv2.imencode(".png", np.full((HEIGHT, WIDTH, 3), 255, np.uint8))[1].tofile(str(path))
    ocr = _ocr([("ಮತದಾರರ ಸಹಿ ಮತ್ತು ದಿನಾಂಕ", 600, 300), ("next line", 60, 420)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert any(blank.origin == "space_below" for blank in layout.blanks)


# --- two-column comparison tables --------------------------------------------------------


def test_one_column_losing_its_caption_does_not_cancel_the_other(tmp_path):
    """In a two-column comparison table, a cell whose caption OCR missed reads as empty.
    Treating any empty neighbour as "the answer cell" then cancelled the field in the
    column that *was* read, so a row asking two questions produced one."""
    from app.services.page_structure_service import Cell, Table

    read = Cell(id="a", x=100, y=100, width=400, height=40)
    read.row = 0
    read.words = [
        OCRWord(id="w", text="Name:", confidence=90, page_index=0,
                pixel=PixelBoundingBox(x=110, y=108, width=90, height=22, **IMAGE), line_id=1)
    ]
    unread = Cell(id="b", x=520, y=100, width=400, height=40)
    unread.row = 0
    table = Table(index=0, x=100, y=100, width=820, height=40, cells=[read, unread])

    # The empty neighbour is the same width as the cell holding the caption, so it is
    # the matching column of a comparison table, not a dedicated answer box.
    assert PageStructureService._has_blank_sibling(table, read) is False


def test_a_label_and_value_table_still_suppresses_the_padding(tmp_path):
    """The behaviour the sibling rule exists for must survive."""
    from app.services.page_structure_service import Cell, Table

    label = Cell(id="a", x=100, y=100, width=300, height=40)
    label.row = 0
    label.words = [
        OCRWord(id="w", text="Father Name", confidence=90, page_index=0,
                pixel=PixelBoundingBox(x=105, y=108, width=180, height=22, **IMAGE), line_id=1)
    ]
    value = Cell(id="b", x=410, y=100, width=600, height=40)
    value.row = 0
    table = Table(index=0, x=100, y=100, width=910, height=40, cells=[label, value])
    assert PageStructureService._has_blank_sibling(table, label) is True


def test_only_the_first_row_can_be_a_top_header(tmp_path):
    """Letting row 1 qualify risked swallowing a whole row of real fields."""
    path = tmp_path / "hdr.png"
    top, row_h, left, split = _page(path, ["hdr", "second", "third"])
    ocr = _ocr(
        [
            ("Details of the Elector in the Roll", left + 12, top + 18),
            ("Details of the Relative in the Roll", split + 12, top + 18),
            ("Elector Name", left + 12, top + row_h + 18),
            ("Relative Name", split + 12, top + row_h + 18),
        ]
    )
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert layout.tables[0].header_rows in ([], [0])
    assert 1 not in layout.tables[0].header_rows


# --- field assembly --------------------------------------------------------------------


def _legacy_field(pixel: PixelBoundingBox, name: str = "legacy"):
    from app.models.common import FieldType
    from app.models.fields import DetectedField
    from app.utils.bounding_boxes import normalize_box

    return DetectedField(
        id=name,
        page_index=0,
        label="",
        field_type=FieldType.TEXT,
        input_box=normalize_box(pixel),
        confidence=0.6,
    )


def test_an_unruled_page_merges_the_shape_detector_in(tmp_path):
    """The table-less branch of assembly was never exercised by a test, and a wrong
    argument count in it failed every upload of an unruled form with "I could not process
    this form" -- a message that blames the scan for a bug in the code."""
    from app.services.field_assembly_service import FieldAssemblyService

    path = tmp_path / "plain.png"
    cv2.imencode(".png", np.full((HEIGHT, WIDTH, 3), 255, np.uint8))[1].tofile(str(path))
    ocr = _ocr([("Applicant Name:", 60, 200)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert layout.tables == []

    clear = PixelBoundingBox(x=100, y=600, width=300, height=40, **IMAGE)
    fields = FieldAssemblyService().build(layout, [_legacy_field(clear)], 0)
    assert any(field.id == "legacy" for field in fields)


def test_a_shape_candidate_over_printed_words_is_dropped(tmp_path):
    from app.services.field_assembly_service import FieldAssemblyService

    path = tmp_path / "plain.png"
    cv2.imencode(".png", np.full((HEIGHT, WIDTH, 3), 255, np.uint8))[1].tofile(str(path))
    ocr = _ocr([("Some printed sentence of the form", 60, 400)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    word = ocr.words[0].pixel
    on_text = PixelBoundingBox(x=word.x, y=word.y, width=word.width, height=word.height, **IMAGE)
    fields = FieldAssemblyService().build(layout, [_legacy_field(on_text)], 0)
    assert not any(field.id == "legacy" for field in fields)


def test_a_ruled_page_ignores_the_shape_detector(tmp_path):
    from app.services.field_assembly_service import FieldAssemblyService

    path = tmp_path / "ruled.png"
    top, row_h, left, split = _page(path, ["a", "b"])
    ocr = _ocr([("Father Name", left + 12, top + 18)])
    layout = PageStructureService().analyse(str(path), ocr, 0)
    assert layout.tables, "fixture should be a ruled page"
    clear = PixelBoundingBox(x=100, y=800, width=300, height=40, **IMAGE)
    fields = FieldAssemblyService().build(layout, [_legacy_field(clear)], 0)
    assert not any(field.id == "legacy" for field in fields)
