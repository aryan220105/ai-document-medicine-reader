from fastapi import APIRouter, Request

from app.dependencies import AppContainer

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    container: AppContainer = request.app.state.container
    return {
        "status": "ok",
        "ocr": container.ocr_service.available(),
        "llm_configured": container.settings.llm_configured,
        "external_ai_enabled": container.settings.external_ai_enabled,
        "vector_store": container.vectors.backend,
        "llm_key_count": len(container.settings.llm_api_keys()),
    }
