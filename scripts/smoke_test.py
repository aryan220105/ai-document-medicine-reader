from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "demo_bank_account_opening.png"
UNKNOWN = ROOT / "samples" / "demo_unknown_library_card.png"
BASE = "http://127.0.0.1:8000"


def request(method: str, path: str, data: bytes | None = None, content_type: str | None = None) -> tuple[int, dict | bytes]:
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read()
            if "application/json" in response.headers.get("Content-Type", ""):
                return response.status, json.loads(body.decode("utf-8"))
            return response.status, body
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            return exc.code, json.loads(payload.decode("utf-8"))
        except Exception:
            return exc.code, payload


def multipart(path: Path, category: str = "banking") -> bytes:
    boundary = "----formsathi"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"category\"\r\n\r\n{category}\r\n".encode(),
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + b"\r\n"
        + f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts)


def wait(document_id: str) -> dict:
    for _ in range(40):
        status, payload = request("GET", f"/api/documents/{document_id}/status")
        if status == 200 and isinstance(payload, dict) and payload.get("status") in {"ready", "failed"}:
            return payload
        time.sleep(1)
    raise SystemExit("Timed out waiting for processing")


def main() -> None:
    if not SAMPLE.exists() or not UNKNOWN.exists():
        from generate_samples import main as generate

        generate()
    status, health = request("GET", "/api/health")
    assert status == 200 and health.get("status") == "ok", health
    print("health ok", health)

    status, uploaded = request("POST", "/api/documents/upload", multipart(SAMPLE), "multipart/form-data; boundary=----formsathi")
    assert status == 200, uploaded
    known = wait(uploaded["id"])
    assert known["status"] == "ready", known
    status, fields = request("GET", f"/api/documents/{uploaded['id']}/fields")
    assert status == 200 and fields["fields"], fields
    status, match = request("GET", f"/api/documents/{uploaded['id']}/form-match")
    assert status == 200 and match.get("form_id") == "demo_bank_account_opening_v1", match
    guidance_body = json.dumps({"field_id": fields["fields"][0]["id"], "language": "en", "allow_external_ai": False}).encode()
    status, guidance = request("POST", f"/api/documents/{uploaded['id']}/guidance", guidance_body, "application/json")
    assert status == 200 and guidance.get("source") in {
        "known_form_knowledge_base",
        "common_field_dictionary",
        "printed_form_text",
    }, guidance
    preview_body = json.dumps({"answers": [{"field_id": fields["fields"][0]["id"], "value": "Ananya Rao"}]}).encode()
    status, preview = request("POST", f"/api/documents/{uploaded['id']}/preview", preview_body, "application/json")
    assert status == 200 and preview.get("preview_id"), preview
    if preview.get("pdf_url"):
        status, pdf = request("GET", preview["pdf_url"])
        assert status == 200 and isinstance(pdf, bytes) and pdf[:4] == b"%PDF", "preview pdf missing"

    status, unknown = request("POST", "/api/documents/upload", multipart(UNKNOWN, "other"), "multipart/form-data; boundary=----formsathi")
    unknown_doc = wait(unknown["id"])
    assert unknown_doc["status"] == "ready", unknown_doc
    status, umatch = request("GET", f"/api/documents/{unknown['id']}/form-match")
    assert status == 200 and umatch.get("unknown") is True, umatch
    request("DELETE", f"/api/documents/{uploaded['id']}")
    request("DELETE", f"/api/documents/{unknown['id']}")
    print("smoke test passed")


if __name__ == "__main__":
    main()
