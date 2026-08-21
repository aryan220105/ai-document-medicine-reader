from fastapi import APIRouter, Request

from app.dependencies import AppContainer

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    container: AppContainer = request.app.state.container
    return {
        "status": "ok",
        "ocr": container.ocr_service.available(),
        "llm_configured": container.llm_service.configured,
        "vector_store": container.rag_service.available(),
        "llm_key_count": len(container.settings.llm_api_keys()),
    }


@router.get("/config")
def config(request: Request) -> dict[str, object]:
    container: AppContainer = request.app.state.container
    return {
        "llm_configured": container.llm_service.configured,
        "max_upload_mb": container.settings.max_upload_mb,
        "languages": ["en", "hi", "kn"],
        "accepted_types": ["image/png", "image/jpeg", "image/webp"],
        "privacy_notice": (
            "Uploaded documents are processed for this demonstration application. "
            "Avoid uploading highly sensitive personal information unless the deployment environment is trusted."
        ),
    }
