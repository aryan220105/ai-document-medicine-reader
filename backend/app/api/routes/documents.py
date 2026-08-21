from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.dependencies import AppContainer
from app.models.chat import ChatRequest, ChatResponse
from app.models.document import DocumentResponse, DocumentTypeUpdate
from app.models.ocr import OCRResult

router = APIRouter()


def _container(request: Request) -> AppContainer:
    return request.app.state.container


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
) -> DocumentResponse:
    container = _container(request)
    record = await container.document_service.create_from_upload(file)
    background_tasks.add_task(container.document_service.process, record.id)
    return container.document_service.to_response(record)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, request: Request) -> DocumentResponse:
    container = _container(request)
    record = container.document_service.get(document_id)
    return container.document_service.to_response(record)


@router.get("/documents/{document_id}/ocr", response_model=OCRResult)
def get_ocr(document_id: str, request: Request) -> OCRResult:
    record = _container(request).document_service.get(document_id)
    if record.ocr is None:
        raise HTTPException(status_code=409, detail="OCR is not ready yet.")
    return record.ocr


@router.get("/documents/{document_id}/fields")
def get_fields(document_id: str, request: Request) -> dict:
    record = _container(request).document_service.get(document_id)
    return {"fields": [field.model_dump() for field in record.fields]}


@router.patch("/documents/{document_id}/type", response_model=DocumentResponse)
def update_type(document_id: str, payload: DocumentTypeUpdate, request: Request) -> DocumentResponse:
    container = _container(request)
    record = container.document_service.override_type(document_id, payload.document_type)
    return container.document_service.to_response(record)


@router.post("/documents/{document_id}/ask", response_model=ChatResponse)
async def ask_document(document_id: str, payload: ChatRequest, request: Request) -> ChatResponse:
    return await _container(request).chat_service.ask(document_id, payload)


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, request: Request) -> dict[str, str]:
    _container(request).document_service.delete(document_id)
    return {"status": "deleted", "id": document_id}


@router.get("/documents/{document_id}/image/original")
def original_image(document_id: str, request: Request) -> FileResponse:
    record = _container(request).document_service.get(document_id)
    path = Path(record.original_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Original image is no longer available.")
    return FileResponse(path)


@router.get("/documents/{document_id}/image/processed")
def processed_image(document_id: str, request: Request) -> FileResponse:
    record = _container(request).document_service.get(document_id)
    if not record.processed_path or not Path(record.processed_path).exists():
        raise HTTPException(status_code=404, detail="Processed image is not available.")
    return FileResponse(record.processed_path)
