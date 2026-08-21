def test_health(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["llm_configured"] is False
    assert "ocr" in payload
    assert "vector_store" in payload
    assert "llm_key_count" in payload


def test_config_does_not_expose_secrets(client) -> None:
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.text.lower()
    assert "gsk_" not in body
    assert "api_key" not in body or "llm_configured" in body
