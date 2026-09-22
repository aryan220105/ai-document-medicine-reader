from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.models.common import FieldType, Language
from app.utils.text_normalization import fold


class FormKnowledgeRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.forms: dict[str, dict[str, Any]] = {}
        self.common_fields: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        self.forms = {}
        forms_dir = self.settings.knowledge_dir / "forms"
        if forms_dir.exists():
            for path in sorted(forms_dir.glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.forms[payload["form_id"]] = payload
        common_path = self.settings.knowledge_dir / "common_fields.json"
        self.common_fields = json.loads(common_path.read_text(encoding="utf-8")) if common_path.exists() else []

    def all_forms(self) -> list[dict[str, Any]]:
        return list(self.forms.values())

    def get_form(self, form_id: str) -> dict[str, Any] | None:
        return self.forms.get(form_id)

    def field_chunks(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for form in self.forms.values():
            for field in form.get("fields", []):
                for language in Language:
                    what = field.get("what_to_enter", {}).get(language.value, "")
                    why = field.get("why_needed", {}).get(language.value, "")
                    text = " ".join(
                        [
                            field.get("field_id", ""),
                            " ".join(field.get("aliases", [])),
                            what,
                            why,
                        ]
                    )
                    chunks.append(
                        {
                            "id": f"{form['form_id']}:{field['field_id']}:{language.value}",
                            "text": text,
                            "metadata": {
                                "form_id": form["form_id"],
                                "display_name": form.get("display_name", ""),
                                "field_id": field["field_id"],
                                "aliases": field.get("aliases", []),
                                "language": language.value,
                                "category": form.get("category", "other"),
                                "version": str(form.get("version", "1")),
                                "source": "known_form_knowledge_base",
                                "source_reference": field.get("source_reference", form.get("disclaimer", "")),
                                "what_to_enter": what,
                                "why_needed": why,
                                "example": field.get("example"),
                                "validation": field.get("validation", {}),
                                "type": field.get("type", "text"),
                            },
                        }
                    )
        return chunks

    def find_field(self, form_id: str, aliases: list[str], language: Language) -> dict[str, Any] | None:
        form = self.get_form(form_id)
        if not form:
            return None
        folded = {fold(alias) for alias in aliases if alias}
        best: tuple[int, dict[str, Any]] | None = None
        for field in form.get("fields", []):
            names = [field.get("field_id", ""), *field.get("aliases", [])]
            overlap = len(folded.intersection({fold(name) for name in names}))
            if overlap and (best is None or overlap > best[0]):
                best = (overlap, field)
        if best is None:
            return None
        field = best[1]
        return {
            "field": field,
            "language": language,
            "form": form,
        }

    @staticmethod
    def field_type(value: str) -> FieldType:
        mapping = {
            "text": FieldType.TEXT,
            "multiline": FieldType.MULTILINE,
            "date": FieldType.DATE,
            "checkbox": FieldType.CHECKBOX,
            "radio": FieldType.RADIO,
            "signature": FieldType.SIGNATURE,
            "table": FieldType.TABLE_CELL,
        }
        return mapping.get(value, FieldType.TEXT)
