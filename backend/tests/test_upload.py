def test_invalid_file_upload(client) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
    assert "PNG" in response.json()["detail"]


def test_empty_upload(client) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
