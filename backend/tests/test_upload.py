from io import BytesIO

from PIL import Image


def _png() -> bytes:
    image = Image.new("RGB", (80, 80), (255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_valid_pdf_upload(client):
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=500)
    page.insert_text((40, 80), "Demo Bank Nominee Occupation")
    payload = doc.tobytes()
    doc.close()
    response = client.post("/api/documents/upload", files={"file": ("form.pdf", payload, "application/pdf")})
    assert response.status_code == 200


def test_valid_image_upload(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("form.png", _png(), "image/png")},
        data={"category": "banking"},
    )
    assert response.status_code == 200
    assert response.json()["id"]


def test_invalid_mime(client):
    response = client.post("/api/documents/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_type"


def test_oversized_upload(client, settings):
    settings.max_upload_mb = 0
    # 0 MB limit -> any non-empty file is too large, but sniff happens after size check
    huge = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    response = client.post("/api/documents/upload", files={"file": ("a.png", huge, "image/png")})
    assert response.status_code == 400


def test_invalid_pdf(client):
    response = client.post("/api/documents/upload", files={"file": ("a.pdf", b"%PDF-1.4 broken", "application/pdf")})
    assert response.status_code == 200
    document_id = response.json()["id"]
    # processing happens in background; invoke directly
    from app.dependencies import AppContainer

    container: AppContainer = client.app.state.container
    record = container.document_service.process(document_id)
    assert record.status.value == "failed"
