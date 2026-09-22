from fastapi import APIRouter, Request

from app.dependencies import AppContainer
from app.models.common import DocumentCategory, Language

router = APIRouter()


@router.get("/config")
def config(request: Request) -> dict[str, object]:
    container: AppContainer = request.app.state.container
    return {
        "llm_configured": container.settings.llm_configured,
        "external_ai_enabled": container.settings.external_ai_enabled,
        "max_upload_mb": container.settings.max_upload_mb,
        "max_pdf_pages": container.settings.max_pdf_pages,
        "languages": [item.value for item in Language],
        "categories": [item.value for item in DocumentCategory],
        "accepted_types": ["image/png", "image/jpeg", "image/webp", "application/pdf"],
        "privacy_notice": (
            "FormSathi is an academic demonstration. Uploaded forms stay on this machine. "
            "Personal answers are never sent to an external language model. "
            "Avoid highly sensitive real forms unless you trust this deployment."
        ),
    }
