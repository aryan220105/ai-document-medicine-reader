from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.config import get_settings
from app.dependencies import build_container
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    container = build_container(settings)
    app.state.container = container
    logger.info(
        "Application starting env=%s llm_configured=%s ocr=%s",
        settings.app_env,
        container.llm_service.configured,
        container.ocr_service.available(),
    )
    try:
        container.rag_service.seed_knowledge_base()
    except Exception:
        logger.exception("Knowledge-base indexing failed at startup")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI Document & Medicine Assistant",
        description="Upload a document or medicine label, extract text, and ask grounded questions.",
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
    application.include_router(health_router, prefix="/api")
    application.include_router(documents_router, prefix="/api")
    return application


app = create_app()
