"""End-to-end evaluation of the unknown-form flow.

Runs the real pipeline -- preprocess, Tesseract OCR, field detection, label association,
dictionary resolution, multilingual guidance -- over the synthetic unknown forms in
English, Hindi, Kannada, and Urdu, clean and noisy, and reports per-language numbers.

    python scripts/evaluate_unknown_flow.py
    python scripts/evaluate_unknown_flow.py --output unknown_flow_results.json

Nothing here is fabricated: every figure comes from running the pipeline against the
ground-truth files written by scripts/generate_unknown_samples.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.dependencies import build_container  # noqa: E402
from app.models.common import ALL_LANGUAGES, Language  # noqa: E402
from app.utils.bounding_boxes import iou  # noqa: E402
from app.utils.text_normalization import dominant_script  # noqa: E402

SAMPLES = ROOT / "samples"
GT = SAMPLES / "ground_truth"

EXPECTED_SCRIPT = {
    Language.ENGLISH: "latin",
    Language.HINDI: "devanagari",
    Language.KANNADA: "kannada",
    Language.URDU: "arabic",
}

UNKNOWN_FORMS = [
    "demo_unknown_en_library",
    "demo_unknown_hi_panchayat",
    "demo_unknown_kn_grama",
    "demo_unknown_ur_welfare",
]


def settings_for(tmp: Path) -> Settings:
    configured = Settings(
        data_dir=tmp,
        knowledge_base_dir=ROOT / "backend" / "knowledge_base",
        use_light_embeddings=True,
        external_ai_enabled=False,
        groq_api_key="",
        groq_model="",
    )
    for directory in (
        configured.data_dir,
        configured.uploads_dir,
        configured.processed_dir,
        configured.previews_dir,
        configured.chroma_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return configured


def run_one(container, image_path: Path, truth: dict) -> dict:
    """Push one page through the real pipeline and score it against ground truth."""
    service = container.document_service
    processed = Path(container.settings.processed_dir) / f"{image_path.stem}.png"
    processed.parent.mkdir(parents=True, exist_ok=True)
    preprocess = service.image_service.preprocess(str(image_path), str(processed))

    ocr = service.ocr_service.extract(preprocess.processed_path, page_index=0)
    if not ocr.has_useful_text:
        ocr = service.ocr_service.extract(str(image_path), page_index=0)

    detected = service.field_detection.detect(preprocess.processed_path, 0)
    fields = service.label_association.associate(detected, ocr)
    service.recover_missing_labels(fields, preprocess.processed_path, ocr)
    service._resolve_semantics(fields)

    expected = truth["fields"]
    # Detection: a ground-truth box counts as found when a detected box overlaps it.
    matched_boxes = 0
    for item in expected:
        pixel = item["pixel"]
        target = {
            "x": pixel["x"] / pixel["image_width"],
            "y": pixel["y"] / pixel["image_height"],
            "width": pixel["width"] / pixel["image_width"],
            "height": pixel["height"] / pixel["image_height"],
        }
        for field in fields:
            box = field.input_box
            if iou(
                type(box)(x=target["x"], y=target["y"], width=target["width"], height=target["height"]),
                box,
            ) >= 0.3:
                matched_boxes += 1
                break

    # Semantics: did the printed label resolve to the field the form actually asks for?
    expected_ids = {item["field_id"] for item in expected if item["field_id"]}
    resolved_ids = {field.semantic_id for field in fields if field.semantic_id}
    correct = expected_ids & resolved_ids

    labelled = [field for field in fields if (field.label or "").strip()]
    described = [field for field in fields if field.semantic_id or field.label_pattern_id]

    # Guidance: every field must produce text in all four languages, each in its own script.
    language_gaps: list[str] = []
    wrong_script: list[str] = []
    for field in fields:
        bundle = container.document_service.guidance.bundle_for_field(
            field, None, [ocr], languages=list(ALL_LANGUAGES), allow_external_ai=False
        )
        for language in ALL_LANGUAGES:
            guidance = bundle.languages.get(language)
            if guidance is None or not guidance.what_to_enter.strip():
                language_gaps.append(f"{field.id}:{language.value}")
                continue
            if dominant_script(guidance.what_to_enter) != EXPECTED_SCRIPT[language]:
                wrong_script.append(f"{field.id}:{language.value}")

    return {
        "image": image_path.name,
        "expected_fields": len(expected),
        "detected_fields": len(fields),
        "boxes_matched": matched_boxes,
        "box_recall": round(matched_boxes / max(len(expected), 1), 3),
        "labelled_fields": len(labelled),
        "label_rate": round(len(labelled) / max(len(fields), 1), 3),
        "semantic_expected": len(expected_ids),
        "semantic_correct": len(correct),
        "semantic_recall": round(len(correct) / max(len(expected_ids), 1), 3),
        "described_fields": len(described),
        "describe_rate": round(len(described) / max(len(fields), 1), 3),
        "ocr_script": ocr.script,
        "ocr_languages": ocr.languages_used,
        "ocr_confidence": ocr.average_confidence,
        "guidance_language_gaps": language_gaps,
        "guidance_wrong_script": wrong_script,
        "missed_semantics": sorted(expected_ids - resolved_ids),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--samples", type=Path, default=SAMPLES)
    args = parser.parse_args()

    tmp = ROOT / "data" / "evaluation_unknown"
    tmp.mkdir(parents=True, exist_ok=True)
    container = build_container(settings_for(tmp))

    results: list[dict] = []
    for name in UNKNOWN_FORMS:
        truth_path = GT / f"{name}.json"
        if not truth_path.exists():
            print(f"skip {name}: no ground truth. Run scripts/generate_unknown_samples.py first.")
            continue
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        for variant in ("", "_noisy"):
            image = args.samples / f"{name}{variant}.png"
            if not image.exists():
                continue
            row = run_one(container, image, truth)
            row["language"] = truth.get("language", "en")
            row["variant"] = "noisy" if variant else "clean"
            row["rtl"] = truth.get("rtl", False)
            results.append(row)
            print(
                f"{row['language']:>3} {row['variant']:<5} "
                f"boxes {row['boxes_matched']}/{row['expected_fields']} "
                f"labels {row['label_rate']:.2f} "
                f"semantics {row['semantic_correct']}/{row['semantic_expected']} "
                f"described {row['describe_rate']:.2f} "
                f"script={row['ocr_script']} "
                f"gaps={len(row['guidance_language_gaps'])} "
                f"wrong_script={len(row['guidance_wrong_script'])}"
                + (f" missed={row['missed_semantics']}" if row["missed_semantics"] else "")
            )

    if results:
        def mean(key: str, rows: list[dict]) -> float:
            return round(sum(row[key] for row in rows) / len(rows), 3)

        clean = [row for row in results if row["variant"] == "clean"]
        noisy = [row for row in results if row["variant"] == "noisy"]
        print("\nsummary")
        for label, rows in (("clean", clean), ("noisy", noisy)):
            if rows:
                print(
                    f"  {label}: box_recall={mean('box_recall', rows)} "
                    f"label_rate={mean('label_rate', rows)} "
                    f"semantic_recall={mean('semantic_recall', rows)} "
                    f"describe_rate={mean('describe_rate', rows)}"
                )
        total_gaps = sum(len(row["guidance_language_gaps"]) for row in results)
        total_wrong = sum(len(row["guidance_wrong_script"]) for row in results)
        print(f"  guidance language gaps: {total_gaps}, wrong-script responses: {total_wrong}")

    if args.output:
        args.output.write_text(json.dumps({"results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.output}")


if __name__ == "__main__":
    main()
