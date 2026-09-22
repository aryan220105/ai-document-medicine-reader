# Privacy and safety

FormSathi is an academic demonstration. Do not upload highly sensitive real identity or financial forms unless you trust the machine running the backend.

## Data that stays local

- Uploaded files under UUID names in `data/uploads`
- Processed pages in `data/processed`
- Preview copies in `data/previews`
- SQLite metadata in `data/app.db`

Deletion removes these artifacts for that document.

## External AI

- Disabled by default (`EXTERNAL_AI_ENABLED=false`).
- Requires UI consent on the first use.
- Sends only printed labels and nearby OCR text.
- Never sends user answers, names, account numbers, dates of birth entered by the user, signatures, or page images.

## Product boundary

The application does not submit forms, generate signatures, or present AI text as official instructions. Low-confidence and AI sources are labelled **Verify with official instructions**.
