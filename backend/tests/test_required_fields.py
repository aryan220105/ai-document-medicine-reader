from app.models.common import FieldType, Language
from app.models.fields import DetectedField, FieldAnswer, ValidationRule
from app.models.preview import PreviewRequest
from app.services.required_field_service import assign_required, looks_required_from_label
from app.utils.bounding_boxes import normalize_box
from app.models.common import PixelBoundingBox


def _field(field_id: str, label: str = "Name", **kwargs) -> DetectedField:
    box = normalize_box(PixelBoundingBox(x=20, y=40, width=200, height=40, image_width=400, image_height=200))
    data = {
        "id": field_id,
        "page_index": 0,
        "label": label,
        "field_type": FieldType.TEXT,
        "input_box": box,
        "confidence": 0.9,
        "filled_by": "applicant",
    }
    data.update(kwargs)
    return DetectedField(**data)


def test_asterisk_on_label_is_required():
    assert looks_required_from_label("Full Name *")
    assert looks_required_from_label("आवश्यक नाम")


def test_assign_required_marks_applicant_blanks_and_skips_office():
    name = _field("name")
    office = _field("office", label="For office use", filled_by="office")
    optional = _field(
        "spouse",
        label="Spouse",
        validation_rule=ValidationRule(kind="person_name", optional=True),
    )
    signature = _field("sig", label="Sign", field_type=FieldType.SIGNATURE)
    assign_required([name, office, optional, signature])
    assert name.required is True
    assert office.required is False
    assert optional.required is False
    assert signature.required is False


def test_preview_blocks_when_required_answers_are_missing(container, tmp_path):
    from PIL import Image

    from app.models.common import DocumentCategory, DocumentStatus, ProcessingStage
    from app.models.document import DocumentPage, DocumentRecord

    page = tmp_path / "page.png"
    Image.new("RGB", (400, 200), (255, 255, 255)).save(page)
    name = _field("name")
    name.required = True
    record = DocumentRecord(
        id="doc-required",
        original_filename="x.png",
        original_path=str(page),
        mime_type="image/png",
        category=DocumentCategory.OTHER,
        status=DocumentStatus.READY,
        stage=ProcessingStage.READY,
        pages=[DocumentPage(index=0, original_path=str(page), processed_path=str(page), width=400, height=200)],
        fields=[name],
    )
    container.documents.save(record)
    blocked = container.document_service.create_preview(
        "doc-required",
        PreviewRequest(answers=[], language=Language.ENGLISH),
    )
    assert blocked.pdf_url == ""
    assert any(item.code == "missing_required" for item in blocked.warnings)
    assert any("required question" in (item.message or "").lower() for item in blocked.warnings)

    ok = container.document_service.create_preview(
        "doc-required",
        PreviewRequest(answers=[FieldAnswer(field_id="name", value="Ravi")], language=Language.ENGLISH),
    )
    assert ok.pdf_url
    assert not any(item.code == "missing_required" for item in ok.warnings)
    container.document_service.delete("doc-required")
