from datetime import date

from app.models.common import FieldType, PixelBoundingBox
from app.models.fields import DetectedField
from app.services.supporting_document_service import match_fields, read_facts
from app.utils.bounding_boxes import normalize_box


def _field(field_id: str, semantic_id: str, label: str, field_type: FieldType = FieldType.TEXT) -> DetectedField:
    return DetectedField(
        id=field_id,
        page_index=0,
        label=label,
        field_type=field_type,
        input_box=normalize_box(
            PixelBoundingBox(x=10, y=10, width=40, height=10, image_width=100, image_height=100)
        ),
        confidence=0.9,
        semantic_id=semantic_id,
    )


AADHAAR = """
Government of India
Unique Identification Authority of India
Ananya Rao
DOB: 15/08/1998
Female
2345 6789 0123
S/O Mahesh Rao
Address:
12 Lake Road
Bengaluru
Karnataka - 560001
"""

PAN = """
Income Tax Department
Permanent Account Number
ABCDE1234F
Name
ANANYA RAO
Father's Name
MAHESH RAO
Date of Birth
15/08/1998
"""


def test_aadhaar_text_yields_identity_facts():
    facts, kind = read_facts(AADHAAR)
    assert kind == "Aadhaar"
    assert facts["full_name"] == "Ananya Rao"
    assert facts["date_of_birth"] == "15/08/1998"
    assert facts["gender"] == "Female"
    assert facts["aadhaar_number"] == "2345 6789 0123"
    assert facts["father_name"] == "Mahesh Rao"
    assert "12 Lake Road" in facts["address"]
    assert facts["pincode"] == "560001"


def test_pan_text_yields_pan_and_father():
    facts, kind = read_facts(PAN)
    assert kind == "PAN"
    assert facts["pan_number"] == "ABCDE1234F"
    assert facts["full_name"] == "ANANYA RAO"
    assert facts["father_name"] == "MAHESH RAO"
    assert facts["date_of_birth"] == "15/08/1998"


def test_facts_fill_matching_fields_and_leave_unrelated_ones_blank():
    fields = [
        _field("nominee", "full_name", "Nominee name"),
        _field("name", "full_name", "Full name"),
        _field("father", "father_name", "Father's name"),
        _field("dob", "date_of_birth", "Date of birth", FieldType.DATE),
        _field("age", "age", "Age"),
        _field("uid", "aadhaar_number", "Aadhaar number"),
        _field("pin", "pincode", "PIN code"),
        _field("sign", "signature", "Signature", FieldType.SIGNATURE),
        _field("gender", "gender", "Gender", FieldType.RADIO),
    ]
    facts, kind = read_facts(AADHAAR)
    suggestions = match_fields(fields, facts, {key: kind for key in facts}, today=date(2026, 11, 5))
    by_id = {item.field_id: item.value for item in suggestions}
    assert by_id["name"] == "Ananya Rao"
    assert by_id["father"] == "Mahesh Rao"
    assert by_id["dob"] == "15/08/1998"
    assert by_id["age"] == "28"
    assert by_id["uid"] == "2345 6789 0123"
    assert by_id["pin"] == "560001"
    assert "sign" not in by_id
    assert "gender" not in by_id
    assert "nominee" not in by_id


def test_empty_supporting_text_fills_nothing():
    facts, _kind = read_facts("   \n")
    assert match_fields([_field("name", "full_name", "Full name")], facts) == []
