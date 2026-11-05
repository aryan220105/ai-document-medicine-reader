from __future__ import annotations

import re
from datetime import datetime

from app.models.common import FieldType, Language
from app.models.fields import DetectedField, FieldAnswer, ValidationResult
from app.services.translation_service import TranslationService

DIGITS = re.compile(r"\d")
# Indic and Arabic-Indic digit forms, so a value typed on a Hindi or Urdu keyboard
# validates the same way Latin digits do.
DIGIT_FOLD = {
    **{chr(0x0966 + i): str(i) for i in range(10)},  # Devanagari
    **{chr(0x0CE6 + i): str(i) for i in range(10)},  # Kannada
    **{chr(0x0660 + i): str(i) for i in range(10)},  # Arabic-Indic
    **{chr(0x06F0 + i): str(i) for i in range(10)},  # Extended Arabic-Indic (Urdu)
}

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")
BLOOD_RE = re.compile(r"^(A|B|AB|O)[+-]$", re.IGNORECASE)
ALNUM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/\-\s]*$")
NAME_RE = re.compile(r"^[^\d@#$%^&*_=+<>{}\[\]|\\]+$")


def fold_digits(value: str) -> str:
    return "".join(DIGIT_FOLD.get(char, char) for char in value)


def digits_only(value: str) -> str:
    return "".join(char for char in fold_digits(value) if char.isdigit())


class ValidationService:
    """Checks a typed answer against the rule attached to its field.

    Every message comes back in the explanation language the caller asked for, so a user
    reading Urdu guidance does not get an English error. Messages never block the user:
    the preview still renders what they typed, with the warning attached.
    """

    def __init__(self, translation: TranslationService | None = None) -> None:
        self.translation = translation or TranslationService()

    def validate(
        self,
        field: DetectedField,
        answer: FieldAnswer,
        language: Language = Language.ENGLISH,
    ) -> ValidationResult:
        value = (answer.value or "").strip()
        say = lambda key, **kw: self.translation.validation_message(key, language, **kw)  # noqa: E731

        if field.field_type == FieldType.SIGNATURE:
            return ValidationResult(ok=True, message=say("sign_by_hand"))

        rule = field.validation_rule
        kind = rule.kind if rule else self._kind_from_type(field.field_type)
        optional = bool(rule and rule.optional)

        if not value and not answer.selected_option_ids:
            if field.required and not optional:
                return ValidationResult(ok=False, message=say("required"))
            return ValidationResult(ok=True)

        if field.field_type in {FieldType.CHECKBOX, FieldType.RADIO} or kind == "choice":
            return ValidationResult(ok=True)

        if kind == "office_use":
            return ValidationResult(ok=True, message=say("office_use"))

        if rule and rule.max_length and len(value) > rule.max_length:
            return ValidationResult(ok=False, message=say("too_long", limit=rule.max_length))

        if rule and rule.pattern:
            try:
                if not re.fullmatch(rule.pattern, value):
                    return ValidationResult(ok=False, message=rule.message or say("bad_format", fmt=rule.format or ""))
            except re.error:
                pass

        checker = getattr(self, f"_check_{kind}", None)
        if checker is not None:
            return checker(value, rule, say)
        return ValidationResult(ok=True)

    @staticmethod
    def _kind_from_type(field_type: FieldType) -> str:
        return {
            FieldType.DATE: "date",
            FieldType.MULTILINE: "multiline",
            FieldType.CHECKBOX: "choice",
            FieldType.RADIO: "choice",
            FieldType.SIGNATURE: "signature",
        }.get(field_type, "text")

    # --- individual rules -------------------------------------------------------

    def _check_date(self, value, rule, say):
        if self._is_date(value):
            return ValidationResult(ok=True)
        return ValidationResult(ok=False, message=say("bad_date", fmt=(rule.format if rule else None) or "DD/MM/YYYY"))

    def _check_integer(self, value, rule, say):
        folded = fold_digits(value)
        if not folded.isdigit():
            return ValidationResult(ok=False, message=say("digits_only"))
        number = int(folded)
        low = rule.min_value if rule and rule.min_value is not None else None
        high = rule.max_value if rule and rule.max_value is not None else None
        if (low is not None and number < low) or (high is not None and number > high):
            return ValidationResult(ok=False, message=say("out_of_range", low=low, high=high))
        return ValidationResult(ok=True)

    def _check_decimal(self, value, rule, say):
        try:
            number = float(fold_digits(value).replace(",", ""))
        except ValueError:
            return ValidationResult(ok=False, message=say("number_expected"))
        low = rule.min_value if rule and rule.min_value is not None else None
        high = rule.max_value if rule and rule.max_value is not None else None
        if (low is not None and number < low) or (high is not None and number > high):
            return ValidationResult(ok=False, message=say("out_of_range", low=low, high=high))
        return ValidationResult(ok=True)

    def _check_amount(self, value, rule, say):
        cleaned = fold_digits(value).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
        try:
            number = float(cleaned)
        except ValueError:
            return ValidationResult(ok=False, message=say("amount_expected"))
        if number < 0:
            return ValidationResult(ok=False, message=say("amount_expected"))
        return ValidationResult(ok=True)

    def _check_year(self, value, rule, say):
        folded = fold_digits(value)
        if not re.fullmatch(r"\d{4}", folded):
            return ValidationResult(ok=False, message=say("bad_year"))
        return ValidationResult(ok=True)

    def _check_mobile_in(self, value, rule, say):
        digits = digits_only(value)
        # Tolerate a written country code; judge the subscriber number.
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if len(digits) != 10 or digits[0] not in "6789":
            return ValidationResult(ok=False, message=say("bad_mobile"))
        return ValidationResult(ok=True)

    def _check_phone(self, value, rule, say):
        digits = digits_only(value)
        if not 6 <= len(digits) <= 15:
            return ValidationResult(ok=False, message=say("bad_phone"))
        return ValidationResult(ok=True)

    def _check_pincode_in(self, value, rule, say):
        digits = digits_only(value)
        if len(digits) != 6 or digits[0] == "0":
            return ValidationResult(ok=False, message=say("bad_pincode"))
        return ValidationResult(ok=True)

    def _check_aadhaar_in(self, value, rule, say):
        digits = digits_only(value)
        if len(digits) != 12:
            return ValidationResult(ok=False, message=say("bad_aadhaar"))
        if digits[0] in "01":
            return ValidationResult(ok=False, message=say("bad_aadhaar"))
        return ValidationResult(ok=True)

    def _check_pan_in(self, value, rule, say):
        if not PAN_RE.match(value.replace(" ", "").upper()):
            return ValidationResult(ok=False, message=say("bad_pan"))
        return ValidationResult(ok=True)

    def _check_ifsc_in(self, value, rule, say):
        if not IFSC_RE.match(value.replace(" ", "").upper()):
            return ValidationResult(ok=False, message=say("bad_ifsc"))
        return ValidationResult(ok=True)

    def _check_bank_account(self, value, rule, say):
        digits = digits_only(value)
        if not 8 <= len(digits) <= 20:
            return ValidationResult(ok=False, message=say("bad_account"))
        return ValidationResult(ok=True)

    def _check_email(self, value, rule, say):
        if not EMAIL_RE.match(value):
            return ValidationResult(ok=False, message=say("bad_email"))
        return ValidationResult(ok=True)

    def _check_blood_group(self, value, rule, say):
        if not BLOOD_RE.match(value.replace(" ", "")):
            return ValidationResult(ok=False, message=say("bad_blood_group"))
        return ValidationResult(ok=True)

    def _check_alphanumeric(self, value, rule, say):
        if not ALNUM_RE.match(value):
            return ValidationResult(ok=False, message=say("bad_reference"))
        return ValidationResult(ok=True)

    def _check_person_name(self, value, rule, say):
        if DIGITS.search(fold_digits(value)):
            return ValidationResult(ok=False, message=say("name_has_digits"))
        if not NAME_RE.match(value):
            return ValidationResult(ok=False, message=say("name_has_symbols"))
        return ValidationResult(ok=True)

    def _check_attachment(self, value, rule, say):
        return ValidationResult(ok=True, message=say("attachment"))

    def _check_signature(self, value, rule, say):
        return ValidationResult(ok=True, message=say("sign_by_hand"))

    # --- helpers ---------------------------------------------------------------

    @staticmethod
    def _is_date(value: str) -> bool:
        folded = fold_digits(value).strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y"):
            try:
                datetime.strptime(folded, fmt)
                return True
            except ValueError:
                continue
        return False
