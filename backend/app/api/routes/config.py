from fastapi import APIRouter, Request

from app.dependencies import AppContainer
from app.models.common import ALL_LANGUAGES, DocumentCategory, Language

router = APIRouter()

LANGUAGE_NAMES = {
    Language.ENGLISH: {"label": "English", "native": "English", "locale": "en-IN"},
    Language.HINDI: {"label": "Hindi", "native": "हिन्दी", "locale": "hi-IN"},
    Language.KANNADA: {"label": "Kannada", "native": "ಕನ್ನಡ", "locale": "kn-IN"},
    Language.URDU: {"label": "Urdu", "native": "اردو", "locale": "ur-IN"},
}


@router.get("/config")
def config(request: Request) -> dict[str, object]:
    container: AppContainer = request.app.state.container
    return {
        "llm_configured": container.settings.llm_configured,
        "external_ai_enabled": container.settings.external_ai_enabled,
        "max_upload_mb": container.settings.max_upload_mb,
        "max_pdf_pages": container.settings.max_pdf_pages,
        "languages": [item.value for item in ALL_LANGUAGES],
        "language_details": [
            {
                "id": language.value,
                "direction": language.direction,
                **LANGUAGE_NAMES[language],
            }
            for language in ALL_LANGUAGES
        ],
        "categories": [item.value for item in DocumentCategory],
        "accepted_types": ["image/png", "image/jpeg", "image/webp", "application/pdf"],
        "dictionary_fields": len(container.dictionary.entries),
        "interpreter_enabled": container.interpreter.available(),
        "label_patterns": len(container.dictionary.patterns),
        "ocr_languages": container.settings.tesseract_lang,
        "privacy_notice": (
            "FormSathi is an academic demonstration. Uploaded forms stay on this machine. "
            "Personal answers are never sent to an external language model. "
            "Changing the explanation language never changes your form or your answers. "
            "Avoid highly sensitive real forms unless you trust this deployment."
        ),
    }
