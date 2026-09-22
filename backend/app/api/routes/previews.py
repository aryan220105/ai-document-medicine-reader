from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.models.preview import PreviewRequest, PreviewResult

router = APIRouter()


@router.post("/documents/{document_id}/preview", response_model=PreviewResult)
def create_preview(document_id: str, payload: PreviewRequest, request: Request) -> PreviewResult:
    return request.app.state.container.document_service.create_preview(document_id, payload)


@router.get("/documents/{document_id}/previews/{preview_id}.pdf")
def download_preview(document_id: str, preview_id: str, request: Request) -> FileResponse:
    path = request.app.state.container.document_service.preview_pdf(document_id, preview_id)
    return FileResponse(path, media_type="application/pdf", filename="formsathi-reference-preview.pdf")
