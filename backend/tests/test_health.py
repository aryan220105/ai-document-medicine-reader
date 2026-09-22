from app.dependencies import build_container
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_without_llm(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is False


def test_health_with_llm_config(tmp_path, settings):
    settings.external_ai_enabled = True
    settings.groq_api_key = "test-key"
    settings.groq_model = "demo-model"
    app = create_app()
    app.state.container = build_container(settings)
    with TestClient(app) as client:
        body = client.get("/api/health").json()
        assert body["llm_configured"] is True
        assert body["llm_key_count"] >= 1
