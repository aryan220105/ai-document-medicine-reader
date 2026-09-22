from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.dependencies import build_container
from app.models.common import DocumentCategory, PixelBoundingBox
from app.utils.bounding_boxes import iou, normalize_box


class FakeUpload:
    def __init__(self, path: Path) -> None:
        self.filename = path.name
        self.content_type = "image/png"
        self._data = path.read_bytes()

    async def read(self) -> bytes:
        return self._data


def load_gt(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pixel_iou(pred, truth: dict) -> float:
    t = truth["pixel"]
    truth_box = normalize_box(
        PixelBoundingBox(
            x=t["x"],
            y=t["y"],
            width=t["width"],
            height=t["height"],
            image_width=t["image_width"],
            image_height=t["image_height"],
        )
    )
    return iou(pred.input_box, truth_box)


def evaluate(samples: Path, output: Path) -> dict:
    settings = get_settings()
    settings.use_light_embeddings = True
    container = build_container(settings)
    container.retrieval.seed()
    results = []
    for gt_path in sorted((samples / "ground_truth").glob("*.json")):
        gt = load_gt(gt_path)
        image = samples / gt["image"]
        if not image.exists():
            continue
        started = time.perf_counter()

        async def run():
            record = await container.document_service.create_from_upload(FakeUpload(image), DocumentCategory.OTHER)
            container.document_service.process(record.id)
            return record.id

        document_id = asyncio.run(run())
        elapsed = time.perf_counter() - started
        record = container.document_service.get(document_id)
        matched = 0
        for truth in gt["fields"]:
            if any(pixel_iou(field, truth) >= 0.3 for field in record.fields):
                matched += 1
        precision = matched / max(len(record.fields), 1)
        recall = matched / max(len(gt["fields"]), 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        identified = (record.form_match.form_id == gt.get("form_id")) if gt.get("form_id") else record.form_match.unknown
        results.append(
            {
                "sample": gt["image"],
                "expected_form": gt.get("form_id"),
                "predicted_form": record.form_match.form_id,
                "identified": bool(identified),
                "fields_detected": len(record.fields),
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
                "seconds": round(elapsed, 2),
            }
        )
        container.document_service.delete(record.id)
    summary = {
        "iou_threshold": 0.3,
        "note": "Confidence scores are heuristic, not calibrated probabilities. Human-rated metrics are not fabricated.",
        "results": results,
        "human_review_template": str(samples / "human_review_template.csv"),
    }
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    template = samples / "human_review_template.csv"
    if not template.exists():
        template.write_text(
            "sample,language,guidance_correct,unsupported_claim,completion_minutes,corrections,sus_score,notes\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default=str(ROOT / "samples"))
    parser.add_argument("--output", default=str(ROOT / "evaluation_results.json"))
    args = parser.parse_args()
    evaluate(Path(args.samples), Path(args.output))


if __name__ == "__main__":
    main()
