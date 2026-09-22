from fastapi import APIRouter, Request

from app.models.fields import FieldAnswer, ValidationResult
from app.models.guidance import AskRequest, AskResponse, FieldGuidance, GuidanceRequest

router = APIRouter()


@router.post("/documents/{document_id}/guidance", response_model=FieldGuidance)
def field_guidance(document_id: str, payload: GuidanceRequest, request: Request) -> FieldGuidance:
    return request.app.state.container.document_service.guide(document_id, payload)


@router.post("/documents/{document_id}/ask", response_model=AskResponse)
def ask_field(document_id: str, payload: AskRequest, request: Request) -> AskResponse:
    return request.app.state.container.document_service.ask(document_id, payload)


@router.post("/documents/{document_id}/validate", response_model=ValidationResult)
def validate_answer(document_id: str, payload: FieldAnswer, request: Request) -> ValidationResult:
    return request.app.state.container.document_service.validate_answer(document_id, payload)
