from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import build_container
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    get_settings.cache_clear()
    configured = Settings(
        data_dir=tmp_path,
        knowledge_base_dir=Path(__file__).resolve().parents[1] / "knowledge_base",
        use_light_embeddings=True,
        external_ai_enabled=False,
        groq_api_key="",
        groq_model="",
        tesseract_cmd="",
    )
    configured.data_dir.mkdir(parents=True, exist_ok=True)
    configured.uploads_dir.mkdir(parents=True, exist_ok=True)
    configured.processed_dir.mkdir(parents=True, exist_ok=True)
    configured.previews_dir.mkdir(parents=True, exist_ok=True)
    configured.chroma_dir.mkdir(parents=True, exist_ok=True)
    return configured


@pytest.fixture
def container(settings: Settings):
    return build_container(settings)


@pytest.fixture
def client(settings: Settings, container):
    app = create_app()
    app.state.container = container
    with TestClient(app) as test_client:
        yield test_client
