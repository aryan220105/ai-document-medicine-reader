from __future__ import annotations

import re
from datetime import datetime

from app.models.common import FieldType
from app.models.fields import DetectedField, FieldAnswer, ValidationResult


class ValidationService:
    def validate(self, field: DetectedField, answer: FieldAnswer) -> ValidationResult:
        value = (answer.value or "").strip()
        if field.field_type == FieldType.SIGNATURE:
            return ValidationResult(ok=True, message="Sign the official form by hand. FormSathi never creates a signature.")
        if field.required and not value and not answer.selected_option_ids:
            return ValidationResult(ok=False, message="This field looks required. Enter a value or exclude the field.")
        if field.field_type == FieldType.DATE and value:
            if not self._date(value):
                return ValidationResult(ok=False, message="Use a date such as DD/MM/YYYY.")
        if field.field_type in {FieldType.CHECKBOX, FieldType.RADIO}:
            return ValidationResult(ok=True)
        return ValidationResult(ok=True)

    @staticmethod
    def _date(value: str) -> bool:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                continue
        return bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}", value))
