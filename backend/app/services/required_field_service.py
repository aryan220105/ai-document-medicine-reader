"""Decide which blanks the applicant must fill before a reference preview is built.

Matches the Google Forms pattern: required blanks are marked, and a preview is blocked
until every one of them has an answer (or is marked not applicable on the client).
"""

from __future__ import annotations

import re

from app.models.common import FieldType
from app.models.fields import DetectedField

_ASTERISK = re.compile(r"[*＊✱⁎⋆★☆]|必|आवश्यक|ಅಗತ್ಯ|ضروری")
_REQUIRED_WORD = re.compile(
    r"\b(required|mandatory|compulsory|must\s+fill|must\s+enter)\b|"
    r"(अनिवार्य|आवश्यक)|"
    r"(ಕಡ್ಡಾಯ|ಅಗತ್ಯ)|"
    r"(لازمی|ضروری)",
    re.IGNORECASE,
)


def looks_required_from_label(label: str) -> bool:
    text = (label or "").strip()
    if not text:
        return False
    return bool(_ASTERISK.search(text) or _REQUIRED_WORD.search(text))


def is_applicant_blank(field: DetectedField) -> bool:
    if field.field_type == FieldType.SIGNATURE:
        return False
    if field.filled_by == "office":
        return False
    rule = field.validation_rule
    if rule is not None and (rule.optional or rule.kind == "office_use"):
        return False
    return True


def assign_required(fields: list[DetectedField]) -> None:
    """Mark applicant blanks that must be answered.

    Defaults: every applicant blank that is not explicitly optional is required, matching
    how most Indian forms treat printed answer lines. An asterisk or a 'required' word on
    the printed label always forces the mark.
    """
    for field in fields:
        if not is_applicant_blank(field):
            field.required = False
            continue
        if field.required is True:
            continue
        if looks_required_from_label(field.label) or looks_required_from_label(field.caption or ""):
            field.required = True
            continue
        if field.required is False:
            continue
        field.required = True
