from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.dependencies import AppContainer
from app.models.common import DocumentCategory
from app.models.document import DocumentResponse, KnownFormMatch

router = APIRouter()


def _container(request: Request) -> AppContainer:
    return request.app.state.container


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: DocumentCategory = Form(DocumentCategory.OTHER),
) -> DocumentResponse:
    container = _container(request)
    record = await container.document_service.create_from_upload(file, category=category)
    background_tasks.add_task(container.document_service.process, record.id)
    return container.document_service.to_response(record)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, request: Request) -> DocumentResponse:
    container = _container(request)
    return container.document_service.to_response(container.document_service.get(document_id))


@router.get("/documents/{document_id}/status", response_model=DocumentResponse)
def get_status(document_id: str, request: Request) -> DocumentResponse:
    return get_document(document_id, request)


@router.get("/documents/{document_id}/pages")
def get_pages(document_id: str, request: Request) -> dict:
    record = _container(request).document_service.get(document_id)
    return {
        "pages": [
            {
                "index": page.index,
                "width": page.width,
                "height": page.height,
                "original_url": f"/api/documents/{document_id}/pages/{page.index}/original",
                "processed_url": f"/api/documents/{document_id}/pages/{page.index}/processed",
            }
            for page in record.pages
        ]
    }


@router.get("/documents/{document_id}/pages/{page_index}/original")
def original_page(document_id: str, page_index: int, request: Request) -> FileResponse:
    return FileResponse(_container(request).document_service.page_image(document_id, page_index, "original"))


@router.get("/documents/{document_id}/pages/{page_index}/processed")
def processed_page(document_id: str, page_index: int, request: Request) -> FileResponse:
    return FileResponse(_container(request).document_service.page_image(document_id, page_index, "processed"))


@router.get("/documents/{document_id}/ocr")
def get_ocr(document_id: str, request: Request) -> dict:
    record = _container(request).document_service.get(document_id)
    return {"pages": [page.model_dump() for page in record.ocr]}


@router.get("/documents/{document_id}/fields")
def get_fields(document_id: str, request: Request) -> dict:
    record = _container(request).document_service.get(document_id)
    return {"fields": [field.model_dump() for field in record.fields]}


@router.get("/documents/{document_id}/form-match", response_model=KnownFormMatch)
def get_form_match(document_id: str, request: Request) -> KnownFormMatch:
    return _container(request).document_service.get(document_id).form_match


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, request: Request) -> dict[str, str]:
    _container(request).document_service.delete(document_id)
    return {"status": "deleted", "id": document_id}
