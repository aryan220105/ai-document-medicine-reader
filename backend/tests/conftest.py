from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY_2", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("USE_LIGHT_EMBEDDINGS", "true")
    get_settings.cache_clear()
    from app.main import create_app

    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    get_settings.cache_clear()
