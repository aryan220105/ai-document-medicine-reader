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
- Is reached only after every offline source has been tried. An unknown form in any supported language is fully usable with external AI switched off; the test suite asserts that no network call is attempted in that mode.
- A reply is discarded if it is not written in the script that was requested, so a romanised answer cannot be presented as a Hindi, Kannada, or Urdu translation.

## The page interpreter

When external AI is enabled, an unknown form's printed structure is sent to the model so
that each blank can be read in context.

- Sent: captions, column headers, section headings, and the page's printed text in
  reading order.
- Never sent: anything the user typed, the page image, or any file.
- The model labels blanks that were measured on the page. It cannot add a field, and an
  id it was not given is discarded.
- A concept outside FormSathi's vocabulary is treated as unmapped rather than trusted, and
  a validation rule outside the allowed set becomes plain text, so a hallucinated rule can
  never reject a correct answer.
- Interpretations are cached by a hash of the page structure, in memory, for the life of
  the process. Nothing about a document is sent anywhere twice.
- With external AI off, nothing leaves the machine and the offline dictionary still works.

## The optional background lookup

Off by default (`WEB_CONTEXT_ENABLED=false`). When switched on, FormSathi searches the web
for the form by its printed title, to fill gaps the pages left.

- Sent: the form's printed title, the authority named on it, the initialisms it uses, and
  a short extract of its text. Never the page image, never a whole page, never anything
  the user typed.
- This is a wider boundary than the rest of the application, which is why it is opt-in and
  why the sources used are listed in the interface rather than folded in silently.
- The lookup is asked only for a name, an issuing body, and abbreviation expansions. It is
  explicitly not asked for eligibility rules, document checklists, fees, deadlines or
  procedure. Those vary between editions of a form and between applicants, and the printed
  page the user is holding is the only trustworthy source for them.
- Findings never override the document. They fill gaps only.
- It requires a model that actually searches. There is no fallback to an ordinary chat
  model, which would answer from memory and present invention as research.

## Languages

- The four supported languages are English, Hindi, Kannada, and Urdu.
- **No translation service is used anywhere.** Every string shown in Hindi, Kannada, or Urdu is authored by hand in `scripts/field_dictionary/` and `backend/app/services/translation_service.py`. Changing the explanation language selects between strings that already exist locally; nothing is sent anywhere to translate it.
- **The uploaded form is never translated.** Only FormSathi's own description of a field changes language. The page image, the printed labels, and the answers the user typed are untouched by a language switch, and the frontend test suite asserts this.
- Explanation language is remembered in `localStorage` under `formsathi.language`. Nothing else about the session is stored in the browser.

## Product boundary

The application does not submit forms, generate signatures, or present AI text as official instructions. Low-confidence and AI sources are labelled **Verify with official instructions**.

On an unknown form the same boundary holds, and the interface distinguishes three honestly different situations:

- a field whose printed wording FormSathi recognises, described from the authored dictionary;
- a field whose wording it does not recognise, where only the *shape* of the expected answer is described, badged **Inferred From Printed Label**;
- a field whose label could not be read at all, which says so rather than offering a guess.

It also distinguishes **who fills a field in**. A block meant for a verifying officer is
marked as office use, is shown without an answer box, and is never presented to the
applicant as something to complete.

FormSathi never supplies the value a user should write, in any language. Asking it to is refused, and the refusal is itself shown in the user's chosen language.
