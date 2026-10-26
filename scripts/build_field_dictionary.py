"""Generate the runtime common-field dictionary from scripts/field_dictionary/.

    python scripts/build_field_dictionary.py

Writes backend/knowledge_base/common_fields.json and label_patterns.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from field_dictionary import LANGUAGES  # noqa: E402
from field_dictionary import banking, contact, declaration, documents, education, identity, patterns  # noqa: E402

KB = ROOT / "backend" / "knowledge_base"

SECTIONS = [identity, contact, documents, banking, education, declaration]


def collect() -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    for section in SECTIONS:
        for item in section.ENTRIES:
            if item["id"] in seen:
                raise ValueError(f"duplicate field id: {item['id']}")
            seen.add(item["id"])
            entries.append(item)
    return entries


def audit(entries: list[dict]) -> None:
    """Fail loudly rather than ship a field that silently falls back to English."""
    problems: list[str] = []
    for item in entries:
        for language in LANGUAGES:
            if not item["aliases"].get(language):
                problems.append(f"{item['id']}: no {language} aliases")
            if not item["simple_label"].get(language, "").strip():
                problems.append(f"{item['id']}: no {language} simple_label")
            if not item["what_to_enter"].get(language, "").strip():
                problems.append(f"{item['id']}: no {language} what_to_enter")
        why = item.get("why_needed") or {}
        if why and sorted(why) != sorted(LANGUAGES):
            problems.append(f"{item['id']}: why_needed covers {sorted(why)}")
    for item in patterns.PATTERNS:
        for language in LANGUAGES:
            if not item["markers"].get(language):
                problems.append(f"pattern {item['id']}: no {language} markers")
            if not item["what_to_enter"].get(language, "").strip():
                problems.append(f"pattern {item['id']}: no {language} what_to_enter")
    if problems:
        raise SystemExit("Dictionary audit failed:\n  " + "\n  ".join(problems))


def main() -> None:
    entries = collect()
    audit(entries)
    KB.mkdir(parents=True, exist_ok=True)
    (KB / "common_fields.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (KB / "label_patterns.json").write_text(
        json.dumps(
            {"inferred_note": patterns.INFERRED_NOTE, "patterns": patterns.PATTERNS},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    alias_count = sum(len(values) for item in entries for values in item["aliases"].values())
    print(f"wrote {len(entries)} fields, {alias_count} aliases, {len(patterns.PATTERNS)} label patterns")
    print(f"languages: {', '.join(LANGUAGES)}")


if __name__ == "__main__":
    main()
