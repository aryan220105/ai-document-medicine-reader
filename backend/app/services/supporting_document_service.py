"""Read identity facts from a supporting document and place them on matching form fields.

A missing or unreadable document changes nothing. The form is still filled by hand.
"""

from __future__ import annotations

import re
from datetime import date

from app.models.common import FieldType
from app.models.document import SuggestedAnswer
from app.models.fields import DetectedField

_AADHAAR = re.compile(r"(?<!\d)([2-9]\d{3})[ \-]?(\d{4})[ \-]?(\d{4})(?!\d)")
_PAN = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")
_DATE = re.compile(r"\b(\d{2})[\/\-.](\d{2})[\/\-.](\d{4})\b")
_PIN = re.compile(r"(?<!\d)([1-9]\d{5})(?!\d)")
_EPIC = re.compile(r"\b([A-Z]{3}\d{7})\b")

_NAME_LABELS = ("name", "full name", "applicant name", "applicant's name", "नाम", "पूरा नाम")
_FATHER_LABELS = ("father's name", "father name", "fathers name", "पिता का नाम")
_DOB_LABELS = ("dob", "d.o.b", "date of birth", "birth date", "जन्म तिथि", "जन्म दिनांक")
_ADDRESS_LABELS = ("address", "पता")

_HEADER = re.compile(
    r"government|india|uidai|income tax|department|authority|identification|"
    r"aadhaar|aadhar|unique|permanent account|male|female|address|dob",
    re.IGNORECASE,
)
_OTHER_PERSON = ("father", "mother", "spouse", "husband", "wife", "nominee", "guardian", "witness", "relative")
_FILLABLE = {FieldType.TEXT, FieldType.MULTILINE, FieldType.DATE, FieldType.TABLE_CELL}


def read_facts(text: str) -> tuple[dict[str, str], str]:
    """Return semantic-id values found in one document, and a short source name."""
    lines = [_clean(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    blob = "\n".join(lines)
    kind = _kind(blob)
    facts: dict[str, str] = {}

    aadhaar = _AADHAAR.search(re.sub(r"\s+", " ", blob))
    if aadhaar and kind in {"Aadhaar", "supporting document"}:
        facts["aadhaar_number"] = f"{aadhaar.group(1)} {aadhaar.group(2)} {aadhaar.group(3)}"

    pan = _PAN.search(blob.upper())
    if pan and (kind == "PAN" or re.search(r"\bpan\b|permanent account", blob, re.IGNORECASE)):
        facts["pan_number"] = pan.group(1)

    epic = _EPIC.search(blob.upper())
    if epic and kind == "voter card":
        facts["voter_id"] = epic.group(1)

    dob = _labeled_date(lines) or _only_date(lines)
    if dob:
        facts["date_of_birth"] = dob

    name = _labeled(lines, _NAME_LABELS) or _first_person_line(lines)
    if name and not _HEADER.search(name):
        facts["full_name"] = name

    father = _labeled(lines, _FATHER_LABELS) or _care_of(lines)
    if father and not _HEADER.search(father):
        facts["father_name"] = father

    gender = _gender(blob)
    if gender:
        facts["gender"] = gender

    address, pin = _address(lines)
    if address:
        facts["address"] = address
    if pin:
        facts["pincode"] = pin

    if kind == "supporting document" and not facts:
        return {}, kind
    return facts, kind


def match_fields(
    fields: list[DetectedField],
    facts: dict[str, str],
    sources: dict[str, str] | None = None,
    today: date | None = None,
) -> list[SuggestedAnswer]:
    """Place each fact on the first applicant field that already means that fact."""
    if not facts:
        return []
    sources = sources or {}
    today = today or date.today()
    values = dict(facts)
    if "date_of_birth" in values and "age" not in values:
        age = _age(values["date_of_birth"], today)
        if age:
            values["age"] = age
            sources = {**sources, "age": sources.get("date_of_birth", "supporting document")}

    used: set[str] = set()
    suggestions: list[SuggestedAnswer] = []
    for field in fields:
        if field.filled_by == "office" or field.field_type not in _FILLABLE:
            continue
        key = _field_key(field, values)
        if key is None or key in used:
            continue
        label = " ".join(
            part for part in (field.display_label, field.label, field.caption, field.column_header) if part
        ).lower()
        if key == "full_name" and any(word in label for word in _OTHER_PERSON):
            continue
        suggestions.append(
            SuggestedAnswer(
                field_id=field.id,
                value=values[key],
                source=sources.get(key, "supporting document"),
            )
        )
        used.add(key)
    return suggestions


def _field_key(field: DetectedField, values: dict[str, str]) -> str | None:
    for candidate in (field.known_field_id, field.semantic_id):
        if candidate and candidate in values:
            return candidate
    return None


def _kind(blob: str) -> str:
    lowered = blob.lower()
    if any(word in lowered for word in ("aadhaar", "aadhar", "uidai", "unique identification")):
        return "Aadhaar"
    if "permanent account" in lowered or re.search(r"\bpan\b", lowered):
        return "PAN"
    if any(word in lowered for word in ("election commission", "elector", "epic")):
        return "voter card"
    return "supporting document"


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" \t|")


def _labeled(lines: list[str], labels: tuple[str, ...]) -> str | None:
    wanted = {label.lower() for label in labels}
    for index, line in enumerate(lines):
        lowered = line.lower().rstrip(":").strip()
        if lowered in wanted:
            return _next_value(lines, index + 1)
        for label in wanted:
            prefix = f"{label}:"
            if lowered.startswith(prefix):
                rest = line.split(":", 1)[1].strip()
                if _acceptable_name(rest):
                    return rest
    return None


def _next_value(lines: list[str], start: int) -> str | None:
    for line in lines[start:]:
        if _acceptable_name(line):
            return line
        if line.endswith(":"):
            return None
    return None


def _acceptable_name(line: str) -> bool:
    if not line or line.endswith(":"):
        return False
    if any(char.isdigit() for char in line):
        return False
    if _HEADER.search(line):
        return False
    words = [word for word in re.split(r"\s+", line) if word]
    return 1 <= len(words) <= 6


def _care_of(lines: list[str]) -> str | None:
    for line in lines:
        match = re.match(r"^(?:s\/o|d\/o|c\/o|son of|daughter of)\s*[:\-]?\s*(.+)$", line, re.IGNORECASE)
        if match and _acceptable_name(match.group(1)):
            return match.group(1).strip()
    return None


def _first_person_line(lines: list[str]) -> str | None:
    for line in lines:
        lowered = line.lower().rstrip(":")
        if lowered in _ADDRESS_LABELS or lowered.startswith("address"):
            break
        if re.match(r"^(?:s\/o|d\/o|c\/o|son of|daughter of)\b", line, re.IGNORECASE):
            continue
        if _acceptable_name(line) and len(line.split()) >= 2 and lowered not in _NAME_LABELS:
            return line
    return None


def _labeled_date(lines: list[str]) -> str | None:
    wanted = {label.lower() for label in _DOB_LABELS}
    for index, line in enumerate(lines):
        lowered = line.lower()
        if any(label in lowered for label in wanted):
            found = _DATE.search(line)
            if found:
                return _as_date(found)
            for follower in lines[index + 1 : index + 3]:
                found = _DATE.search(follower)
                if found:
                    return _as_date(found)
    return None


def _only_date(lines: list[str]) -> str | None:
    found = []
    for line in lines:
        found.extend(_DATE.finditer(line))
    if len(found) == 1:
        return _as_date(found[0])
    return None


def _as_date(match: re.Match[str]) -> str:
    return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"


def _gender(blob: str) -> str | None:
    if re.search(r"\bfemale\b|महिला|स्त्री", blob, re.IGNORECASE):
        return "Female"
    if re.search(r"\bmale\b|पुरुष", blob, re.IGNORECASE):
        return "Male"
    return None


def _address(lines: list[str]) -> tuple[str, str | None]:
    start = None
    for index, line in enumerate(lines):
        lowered = line.lower().rstrip(":").strip()
        if lowered in _ADDRESS_LABELS or lowered.startswith("address"):
            start = index
            break
    if start is None:
        return "", None
    parts: list[str] = []
    head = lines[start]
    if ":" in head:
        rest = head.split(":", 1)[1].strip()
        if rest:
            parts.append(rest)
    pin = None
    for line in lines[start + 1 :]:
        if _AADHAAR.search(line) or _PAN.search(line.upper()):
            break
        found = _PIN.search(line)
        if found:
            pin = found.group(1)
            before = line[: found.start()].strip(" ,-")
            if before and not _HEADER.search(before):
                parts.append(before)
            break
        if _acceptable_name(line) or any(char.isdigit() for char in line):
            parts.append(line)
    address = ", ".join(part for part in parts if part)
    return address, pin


def _age(dob: str, today: date) -> str | None:
    match = _DATE.fullmatch(dob)
    if not match:
        return None
    born = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    if born > today:
        return None
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    if years < 0 or years > 120:
        return None
    return str(years)
