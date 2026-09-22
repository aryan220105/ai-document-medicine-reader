from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import AppError
from app.api.routes.config import router as config_router
from app.api.routes.documents import router as documents_router
from app.api.routes.guidance import router as guidance_router
from app.api.routes.health import router as health_router
from app.api.routes.previews import router as previews_router
from app.config import get_settings
from app.dependencies import build_container
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    container = getattr(app.state, "container", None) or build_container(settings)
    app.state.container = container
    logger.info(
        "FormSathi starting env=%s llm_configured=%s ocr=%s",
        settings.app_env,
        settings.llm_configured,
        container.ocr_service.available(),
    )
    try:
        container.retrieval.seed()
    except Exception:
        logger.exception("Knowledge-base indexing failed at startup")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="FormSathi API",
        description="AI-powered multilingual form assistant. Academic demonstration. Not an official submission service.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    application.include_router(health_router, prefix="/api")
    application.include_router(config_router, prefix="/api")
    application.include_router(documents_router, prefix="/api")
    application.include_router(guidance_router, prefix="/api")
    application.include_router(previews_router, prefix="/api")
    return application


app = create_app()
