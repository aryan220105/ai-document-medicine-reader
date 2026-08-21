#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from generate_samples import generate_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    with httpx.Client(timeout=60.0) as client:
        health = client.get(f"{base}/api/health")
        health.raise_for_status()
        print("health:", health.json())
        samples = generate_all(ROOT / "samples")
        with samples["medicine"].open("rb") as handle:
            upload = client.post(
                f"{base}/api/documents/upload",
                files={"file": ("medicine_label.png", handle, "image/png")},
            )
        upload.raise_for_status()
        document_id = upload.json()["id"]
        print("uploaded:", document_id)
        for _ in range(40):
            status = client.get(f"{base}/api/documents/{document_id}")
            payload = status.json()
            if payload["status"] in {"ready", "failed"}:
                print("status:", payload["status"], payload.get("stage"))
                break
            import time

            time.sleep(0.5)
        ocr = client.get(f"{base}/api/documents/{document_id}/ocr")
        print("ocr_status:", ocr.status_code)
        fields = client.get(f"{base}/api/documents/{document_id}/fields")
        print("fields_status:", fields.status_code)
        asked = client.post(
            f"{base}/api/documents/{document_id}/ask",
            json={"question": "What is the expiry date?", "language": "en", "easy_read": False},
        )
        print("ask_status:", asked.status_code)
        print("ask_body:", asked.json().get("answer", asked.text)[:240])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
