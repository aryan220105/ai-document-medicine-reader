from pathlib import Path

from PIL import Image, ImageDraw

from app.models.common import FieldType, Language, PixelBoundingBox
from app.models.fields import DetectedField, FieldAnswer
from app.models.guidance import GuidanceRequest
from app.models.ocr import OCRResult, OCRWord
from app.models.preview import PreviewRequest
from app.services.field_detection_service import FieldDetectionService
from app.services.label_association_service import LabelAssociationService
from app.utils.bounding_boxes import normalize_box


def _page_with_shapes(path: Path) -> None:
    image = Image.new("RGB", (800, 1000), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((200, 80, 700, 130), outline=(0, 0, 0), width=3)
    draw.line((200, 220, 700, 220), fill=(0, 0, 0), width=3)
    draw.rectangle((80, 300, 108, 328), outline=(0, 0, 0), width=3)
    draw.rectangle((82, 302, 106, 326), outline=(0, 0, 0), width=2)
    image.save(path)


def test_field_rectangle_underline_checkbox(settings, tmp_path):
    path = tmp_path / "fields.png"
    _page_with_shapes(path)
    fields = FieldDetectionService(settings).detect(str(path), 0)
    types = {field.field_type for field in fields}
    assert FieldType.TEXT in types or FieldType.MULTILINE in types
    assert any("underline" in field.confidence_reasons for field in fields)
    assert any(field.field_type in {FieldType.CHECKBOX, FieldType.RADIO} for field in fields)


def test_duplicate_merge(settings):
    service = FieldDetectionService(settings)
    a = PixelBoundingBox(x=10, y=10, width=100, height=30, image_width=400, image_height=400)
    from app.services.field_detection_service import DetectionCandidate

    merged = service._merge(
        [
            DetectionCandidate(FieldType.TEXT, a, 0.7, ["a"]),
            DetectionCandidate(FieldType.TEXT, a, 0.6, ["b"]),
        ]
    )
    assert len(merged) == 1


def test_label_association():
    field = DetectedField(
        id="f1",
        page_index=0,
        label="",
        field_type=FieldType.TEXT,
        input_box=normalize_box(PixelBoundingBox(x=200, y=80, width=200, height=30, image_width=400, image_height=400)),
        confidence=0.7,
    )
    word = OCRWord(
        id="w1",
        text="Name:",
        confidence=80,
        page_index=0,
        pixel=PixelBoundingBox(x=20, y=80, width=80, height=20, image_width=400, image_height=400),
        line_id=1,
    )
    ocr = OCRResult(page_index=0, full_text="Name:", image_width=400, image_height=400, words=[word])
    associated = LabelAssociationService().associate([field], ocr)
    assert associated[0].label.lower().startswith("name")


def test_label_stays_on_the_same_row():
    image = dict(image_width=1000, image_height=1000)
    field = DetectedField(
        id="f1",
        page_index=0,
        label="",
        field_type=FieldType.TEXT,
        input_box=normalize_box(PixelBoundingBox(x=400, y=400, width=500, height=40, **image)),
        confidence=0.7,
    )
    words = [
        OCRWord(id="title", text="Demo", confidence=90, page_index=0, pixel=PixelBoundingBox(x=40, y=40, width=80, height=20, **image), line_id=1, block_id=1),
        OCRWord(id="date", text="Date", confidence=90, page_index=0, pixel=PixelBoundingBox(x=40, y=200, width=60, height=20, **image), line_id=1, block_id=2),
        OCRWord(id="student", text="Student", confidence=90, page_index=0, pixel=PixelBoundingBox(x=40, y=405, width=90, height=20, **image), line_id=1, block_id=3),
        OCRWord(id="name", text="Name", confidence=90, page_index=0, pixel=PixelBoundingBox(x=140, y=405, width=70, height=20, **image), line_id=1, block_id=3),
    ]
    ocr = OCRResult(page_index=0, full_text="Demo Date Student Name", image_width=1000, image_height=1000, words=words)
    associated = LabelAssociationService().associate([field], ocr)
    assert associated[0].label == "Student Name"
    assert associated[0].field_type == FieldType.TEXT


def test_known_and_unknown_forms(container):
    from app.models.common import DocumentCategory
    from app.models.ocr import OCRResult

    box = normalize_box(PixelBoundingBox(x=1, y=1, width=10, height=10, image_width=100, image_height=100))
    known = container.document_service.form_identification.match(
        [OCRResult(full_text="Demo Bank account type nominee occupation savings")],
        [DetectedField(id="a", page_index=0, label="Nominee", field_type=FieldType.TEXT, input_box=box, confidence=0.8)],
        DocumentCategory.BANKING,
    )
    assert known.form_id == "demo_bank_account_opening_v1"
    unknown = container.document_service.form_identification.match(
        [OCRResult(full_text="library card favourite genre membership")],
        [],
        DocumentCategory.OTHER,
    )
    assert unknown.unknown is True


def test_common_guidance_and_languages(container):
    field = DetectedField(
        id="f1",
        page_index=0,
        label="Date of Birth",
        field_type=FieldType.DATE,
        input_box=normalize_box(PixelBoundingBox(x=1, y=1, width=10, height=10, image_width=100, image_height=100)),
        confidence=0.8,
    )
    en = container.document_service.guidance.for_field(field, GuidanceRequest(field_id="f1", language=Language.ENGLISH), None, [])
    hi = container.document_service.guidance.for_field(field, GuidanceRequest(field_id="f1", language=Language.HINDI), None, [])
    kn = container.document_service.guidance.for_field(field, GuidanceRequest(field_id="f1", language=Language.KANNADA), None, [])
    assert en.source.value == "common_field_dictionary"
    assert hi.language == Language.HINDI
    assert kn.language == Language.KANNADA
    low = container.document_service.guidance.for_field(
        DetectedField(id="z", page_index=0, label="Favourite Genre", field_type=FieldType.TEXT, input_box=field.input_box, confidence=0.3),
        GuidanceRequest(field_id="z", language=Language.ENGLISH, allow_external_ai=False),
        None,
        [],
    )
    assert low.requires_verification is True
    assert low.source.value == "unavailable"


def test_llm_disabled_and_malformed(container):
    from app.services.llm_service import LLMService

    class Dummy:
        def available(self):
            return True

        def generate_sync(self, **kwargs):
            return "not-json"

    service = LLMService(Dummy())
    assert service.interpret_field("label: x") is None
    assert container.llm_service.available() is False


def test_user_answers_not_in_prompt(container):
    field = DetectedField(
        id="f1",
        page_index=0,
        label="Full Name",
        field_type=FieldType.TEXT,
        input_box=normalize_box(PixelBoundingBox(x=1, y=1, width=10, height=10, image_width=100, image_height=100)),
        confidence=0.8,
    )
    nearby = container.document_service.guidance._nearby_text(field, [])
    assert "Ananya Secret" not in nearby
    assert container.document_service.guidance.prompt_contains_user_answer("Printed label: Full Name", ["Ananya Secret"]) is False


def test_retrieval_and_lexical(container):
    container.retrieval.seed()
    hits = container.retrieval.retrieve("nominee occupation account type", Language.ENGLISH, "demo_bank_account_opening_v1")
    assert hits
    assert hits[0]["metadata"].get("form_id") == "demo_bank_account_opening_v1" or hits[0]["backend"] in {"chroma", "lexical"}
    lexical = container.vectors._lexical_query("date of birth", 3)
    assert lexical


def test_validation_and_preview_signature(container, tmp_path):
    from app.models.document import DocumentPage, DocumentRecord
    from app.models.common import DocumentCategory, DocumentStatus, ProcessingStage

    page = tmp_path / "page.png"
    Image.new("RGB", (400, 500), (255, 255, 255)).save(page)
    field = DetectedField(
        id="sig",
        page_index=0,
        label="Signature",
        field_type=FieldType.SIGNATURE,
        input_box=normalize_box(PixelBoundingBox(x=20, y=400, width=150, height=50, image_width=400, image_height=500)),
        confidence=0.9,
    )
    date = DetectedField(
        id="dob",
        page_index=0,
        label="Date of Birth",
        field_type=FieldType.DATE,
        input_box=normalize_box(PixelBoundingBox(x=20, y=40, width=80, height=20, image_width=400, image_height=500)),
        confidence=0.9,
    )
    overflow = DetectedField(
        id="tiny",
        page_index=0,
        label="Code",
        field_type=FieldType.TEXT,
        input_box=normalize_box(PixelBoundingBox(x=20, y=80, width=20, height=10, image_width=400, image_height=500)),
        confidence=0.9,
    )
    record = DocumentRecord(
        id="doc-preview",
        original_filename="x.png",
        original_path=str(page),
        mime_type="image/png",
        category=DocumentCategory.OTHER,
        status=DocumentStatus.READY,
        stage=ProcessingStage.READY,
        pages=[DocumentPage(index=0, original_path=str(page), processed_path=str(page), width=400, height=500)],
        fields=[field, date, overflow],
    )
    container.documents.save(record)
    assert container.document_service.validate_answer("doc-preview", FieldAnswer(field_id="dob", value="15/08/1998")).ok
    assert not container.document_service.validate_answer("doc-preview", FieldAnswer(field_id="dob", value="nope")).ok
    preview = container.document_service.create_preview(
        "doc-preview",
        PreviewRequest(answers=[FieldAnswer(field_id="sig", value="should-not-become-signature")]),
    )
    assert preview.preview_id
    assert not any(item.code == "signature_generated" for item in preview.warnings)
    overflowed = container.document_service.preview.render(
        record,
        PreviewRequest(answers=[FieldAnswer(field_id="tiny", value="THIS TEXT IS FAR TOO LONG TO FIT")]),
    )
    assert any(item.code == "text_overflow" for item in overflowed.warnings)
    container.document_service.delete("doc-preview")
    assert container.documents.get("doc-preview") is None
