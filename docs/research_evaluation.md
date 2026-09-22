# Research evaluation

## Research question

Can a multilingual Computer Vision plus RAG/LLM assistant reliably explain, locate, and preview form entries while keeping the user in control?

## Hypothesis

The hybrid system will improve field localization, guidance accuracy, and task completion compared with raw OCR and a generic LLM-only baseline.

## Conditions

Evaluate the same tasks across:

1. Raw OCR baseline (word boxes only)
2. LLM-only semantic guidance without coordinate assistance (mocked or configured)
3. FormSathi hybrid pipeline

## Test groups

- Known synthetic forms
- Unseen synthetic forms
- Clean images
- Rotated or noisy images
- English printed forms
- Guidance requested in English, Hindi, and Kannada

## Metrics

Objective metrics computed by `scripts/evaluate_pipeline.py`:

- Field detection precision, recall, and F1 at IoU 0.3
- Known-form identification accuracy
- Average processing time

Human-rated metrics (do not fabricate):

- Label-field association accuracy
- Guidance correctness (supported / partial / unsupported)
- Unsupported-claim rate
- Form completion time
- Correction count
- Usability questionnaire score

Use `samples/human_review_template.csv`. Evaluators should score each guidance response against the printed form and the knowledge-base source, and mark any invented eligibility, fee, or document requirement as an unsupported claim.

## Confidence

Application confidence scores are heuristic indicators, not calibrated probabilities.
