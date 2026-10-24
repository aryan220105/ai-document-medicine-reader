from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.dependencies import AppContainer

router = APIRouter()


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: str


@router.post("/speech")
def speak(body: SpeechRequest, request: Request) -> Response:
    """Read one guidance sentence. The body must be guidance, never an answer or a form."""
    container: AppContainer = request.app.state.container
    audio = container.speech.synthesize(body.text, body.language)
    return Response(content=audio, media_type="audio/mpeg")
