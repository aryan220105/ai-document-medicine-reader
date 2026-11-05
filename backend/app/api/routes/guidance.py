from fastapi import APIRouter, Query, Request

from app.models.common import Language
from app.models.fields import FieldAnswer, ValidationResult
from app.models.guidance import (
    AskRequest,
    AskResponse,
    FieldGuidance,
    GuidanceBundleRequest,
    GuidanceBundleResponse,
    GuidanceRequest,
)

router = APIRouter()


@router.post("/documents/{document_id}/guidance", response_model=FieldGuidance)
def field_guidance(document_id: str, payload: GuidanceRequest, request: Request) -> FieldGuidance:
    return request.app.state.container.document_service.guide(document_id, payload)


@router.post("/documents/{document_id}/guidance/bundle", response_model=GuidanceBundleResponse)
def guidance_bundle(
    document_id: str, payload: GuidanceBundleRequest, request: Request
) -> GuidanceBundleResponse:
    """Guidance for the requested fields in every requested language at once.

    The client keeps the bundle, so changing explanation language is immediate and does
    not re-read the form or disturb the answers already typed.
    """
    return request.app.state.container.document_service.guidance_bundles(document_id, payload)


@router.post("/documents/{document_id}/ask", response_model=AskResponse)
def ask_field(document_id: str, payload: AskRequest, request: Request) -> AskResponse:
    return request.app.state.container.document_service.ask(document_id, payload)


@router.post("/documents/{document_id}/validate", response_model=ValidationResult)
def validate_answer(
    document_id: str,
    payload: FieldAnswer,
    request: Request,
    language: Language = Query(default=Language.ENGLISH, description="Language for the message text."),
) -> ValidationResult:
    return request.app.state.container.document_service.validate_answer(document_id, payload, language)
