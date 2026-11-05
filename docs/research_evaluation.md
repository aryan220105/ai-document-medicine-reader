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
- Forms printed in Hindi (Devanagari), Kannada, and Urdu (Arabic, right-to-left)
- Guidance requested in English, Hindi, Kannada, and Urdu

## Metrics

Objective metrics computed by `scripts/evaluate_pipeline.py` (known forms):

- Field detection precision, recall, and F1 at IoU 0.3
- Known-form identification accuracy
- Average processing time

Objective metrics computed by `scripts/evaluate_unknown_flow.py` (unknown forms, per language and per clean/noisy variant):

- **Field-box recall** — ground-truth input regions matched by a detected field at IoU ≥ 0.3
- **Label rate** — detected fields that ended up with a printed label attached
- **Semantic recall** — labels resolved to the dictionary field the form actually asks for
- **Describe rate** — fields that received a usable description, whether by dictionary match or by label pattern
- **Guidance language gaps** — field/language pairs that produced no text. Expected to be zero.
- **Wrong-script responses** — field/language pairs whose text was not written in that language's script. Expected to be zero.

The last two are the ones that matter most for the multilingual claim: a system that silently falls back to English under a Kannada heading would score well on the others and still be useless to the reader it is for.

Human-rated metrics (do not fabricate):

- Label-field association accuracy
- Guidance correctness (supported / partial / unsupported)
- Unsupported-claim rate
- Form completion time
- Correction count
- Usability questionnaire score

Use `samples/human_review_template.csv`. Evaluators should score each guidance response against the printed form and the knowledge-base source, and mark any invented eligibility, fee, or document requirement as an unsupported claim.

## Recorded results

Running `python scripts/evaluate_unknown_flow.py --output unknown_flow_results.json` writes the raw per-form output, including the list of missed fields for each language and variant. That file is a run artefact and is not committed, so regenerate it rather than quoting a stale copy. The headline figures are reproduced in the README.

Measured on Tesseract 5.5.3 with `tessdata_fast` models: field-box recall 1.00 on both clean and noisy variants; semantic recall 0.89 clean and 0.92 noisy; zero language gaps and zero wrong-script responses across all 88 field-language pairs.

### Interpreting the Urdu result

Urdu scores lowest (6/9 fields resolved on both variants). The cause is isolable: the labels that fail are the ones Tesseract's `urd` model does not read at all, and the same labels read correctly on the blurred variant of the same form. Once a label is read it resolves. Report this as an OCR-model limitation on crisp small Naskh, not as a failure of multilingual field resolution, and do not present the two as one number.

### Complex real forms

The synthetic samples are single-column and lightly ruled, and they flatter the system.
A real government form found the limits of lexical matching immediately. Tested on the
ECI "Declaration Form (Annexure-IV)", a two-page scanned PDF with two ruled tables and a
two-column comparison block:

| | Before | After |
| --- | --- | --- |
| Fields found, page 1 | 12, several wrong | 30, matching the printed form |
| Fields found, page 2 (instructions) | 2 invented | 0 |
| Parentage table (6 rows) | not detected at all | all 6 |
| `Mobile Number` resolved as | bank account number | mobile number |
| `AC Name` (twice) resolved as | a person's name | Assembly Constituency, elector's and relative's told apart |
| Repeated `Name:` cells | identical generic text | distinguished by column header |
| `BLO's Name and Phone Number` | offered to the applicant | marked office use, no answer box |

Two findings worth recording:

- **Structure is not optional on a ruled form.** Treating each rectangle as a candidate
  and suppressing overlaps kept the table border and discarded its cells: one page went
  from 121 detected rectangles to 2 fields.
- **A confident wrong answer is the real failure mode.** The lexical matcher did not
  fail by returning nothing; it returned a plausible-looking description of the wrong
  field, at 78% stated confidence. Any evaluation of this system should count
  *confidently wrong* answers separately from *unavailable* ones, because they cost the
  user far more.

### Threats to validity

- The unknown-form samples are synthetic and generated by this repository, so they share a renderer, a font, and a layout grammar with each other. They are not a substitute for photographs of real regional forms.
- Ground truth is authored alongside the samples. One early run scored a correct result as a miss because a form printed "permanent address" while the ground truth expected "address"; the ground truth was wrong, not the pipeline. Check disagreements in both directions before recording them.
- Measurements on the ECI form above are from a single document, read once. They
  illustrate the failure modes and the fix; they are not a benchmark, and a model's
  answers vary between runs.
- The dictionary was written by the same author as the samples. Resolution accuracy on wordings outside it is not measured by this harness, and the `describe_rate` metric exists partly to make that gap visible.

## Confidence

Application confidence scores are heuristic indicators, not calibrated probabilities.
