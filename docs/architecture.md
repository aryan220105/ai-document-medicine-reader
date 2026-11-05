# Architecture

FormSathi is a monorepo: a FastAPI backend and a React frontend.

## Layers

- **Routes** validate HTTP input and call services.
- **Services** own the document pipeline, guidance priority, and preview rendering.
- **Repositories** persist documents (SQLite) and knowledge (JSON + Chroma/lexical).
- **Providers** wrap Tesseract, embeddings, and the optional Groq LLM.

## Coordinate integrity

Every OCR word and detected field stores page index, pixel box, source image size, and a normalized 0–1 box produced by `app.utils.bounding_boxes.normalize_box`. The processed page is the authoritative display surface after preprocessing.

## Preparing the page

Two decisions here are easy to get wrong in ways that look like failures somewhere else.

**Page-edge detection only crops a photograph of a document on a background.** A form is
full of large four-sided shapes — every ruled table is one — so a candidate must behave
like a page boundary: cover most of the image and reach close to all four edges. An
earlier version accepted any quad covering 18% of the frame, and on a Kannada electoral
form the two-column table won: the processed page lost its title, its first three fields
and its entire lower half. That presented as missing fields, not as a cropping bug. An
image that already *is* the page, such as a rendered PDF, is left alone rather than
warped and resampled.

**Resolution.** Indic and Arabic scripts carry meaning in small marks — vowel signs,
nuqtas, dots above and below — which are the first thing lost to downscaling. The working
limit is 2400px on the longest side; 1800 was enough for Latin and too tight for the rest.

## Reading a form's structure

A ruled form is a grid, not a bag of rectangles. `PageStructureService` finds the rules,
derives the cells between them, assigns OCR words to cells, and decides which cells are
captions and which are blanks. It also records, for every blank, the caption beside it,
the column header above it, any sub-heading, and the section it sits under.

This replaced treating every detected rectangle as a candidate field and then suppressing
overlaps. On a real government form that kept the outer table border and discarded every
cell inside it: one upload went from 121 detected rectangles to 2 fields, losing an entire
parentage table.

Three cases the grid analysis handles that shape detection alone cannot:

- **a caption and its blank sharing one cell** — `Elector Name: ______` is one cell that
  holds both a question and a place to write;
- **nested headers** — a band of narrow cells under their own `AC Number | Part No. |
  Sr No.` strip, below the table's main header;
- **pages that are not forms** — an instruction sheet has no grid and no caption-and-gap
  pattern, and is reported as prose so that no fields are invented on it.

The shape detector is still used, but only on pages with no table at all, where there is
no grid to read. Run against a ruled form whose structure was already understood it
contributed twenty-two spurious boxes, most of them slices of the title text.

### What counts as a blank

A blank is somewhere to write, so it cannot be somewhere already written. Every candidate
is checked against the OCR word boxes and discarded if it overlaps one, whichever stage
proposed it — a colon gap, an attestation area, or the shape detector's underlines. Without
that rule the instruction sheet's own sentences came back as answer boxes.

Three further rules separate the page's own printing from places the applicant fills:

- **A long line ending in a colon is a sentence, not a caption.** Word counts cannot decide
  this in an agglutinative language, where five Kannada words fill a line. Width can: a
  caption occupies well under half the page, and anything wider is prose that happens to
  end in a colon.
- **A tick box inside a paragraph is punctuation.** The declaration text on the ECI form
  prints `☐` mid-sentence for the reader to mark by hand; offered as a field it crowded out
  real ones. A box whose neighbouring line runs most of the page's width is printed text.
- **A signature line does not need room beneath it.** The gap required under an attestation
  caption was wide enough that the officer's block at the foot of the page qualified and the
  elector's own, a few lines above it, did not — the one place on the form the applicant
  certainly must sign. The requirement is now one line's height.

Only the first row of a table can be its header. Allowing later rows to qualify risked
swallowing a row of real fields, and on a comparison table the second row is a question,
not a heading.

**A comparison table asks the same question twice.** `Name:` appears under "in the roll" and
again under "as claimed", and each column is a field. An empty neighbouring cell is treated
as the answer box only when it is clearly wider than the space left beside the caption *and*
not the same width as the caption's own cell. Before the second condition, a column whose
caption OCR had missed read as empty and cancelled the field in the column that was read, so
a row asking two questions produced one.

## Establishing what the document is

A field's meaning depends on the document it sits in, not only on its own caption.
"AC No." is an Assembly Constituency number on an electoral form and an account number on
a banking form, and the caption is identical in both. Matched caption-first, the electoral
one came back as a bank account number, confidently.

So before any field is looked at, the whole document is read once. Every page's printed
text goes in, **including the instruction sheets that have no fields of their own** —
field detection skips those, but they are exactly where a form explains its abbreviations
and says which earlier record a value must be copied from. The pass returns the form's
title, the issuing authority, its purpose, a glossary of the abbreviations used on it,
instructions that change how a field is filled, and the sections an official completes.

On the ECI declaration form that produces `AC = Assembly Constituency`,
`EPIC = Electoral Photo Identity Card`, `ERO = Electoral Registration Officer`, and the
authority `Election Commission of India`. That glossary is prepended to every later
request, which is what stops "AC No." being read as an account number.

The result is cached by a hash of the document text and shown in the interface, because
every field description rests on it: if the glossary were wrong, every description would
be wrong in the same way, and that should be visible rather than inferred from a run of
odd answers.

### Looking the form up online

The pages are read first and are always the authority. Where they leave a gap — an
initialism the form never spells out, an issuing body it never names — an optional second
step searches for the form by its printed title.

It runs only when a Groq **compound** model is configured, because those perform the
search server-side. There is no fallback to an ordinary chat model: asked to "search", it
answers from memory, and background invented about an official form is worse than no
background at all.

Three limits keep this safe. The search is told what the form is called and which
initialisms went unexplained, so it has a narrow question to answer. It is asked only for
a name, an authority, and a glossary — never for eligibility, documents, fees, deadlines
or procedure, which vary by edition and by applicant and must come from the paper. And
its findings are merged with `setdefault`, so anything the pages said stands.

The privacy cost is real and worth stating: enabling this sends the form's title and a
short extract to a search backend. It is off by default, and the sources used are shown
in the interface rather than folded in silently.

## Deciding what a field means

Captions repeat, and their meaning often comes from a column header rather than from the
caption itself. On the ECI declaration form, `Name:` and `Relative's Name:` each appear
twice on one row under different headings, and `AC Name` is an Assembly Constituency, not
a person. Matching those captions against a word list gives answers that are confident and
wrong, which is the worst failure mode this application has: the lexical matcher resolved
`Mobile Number` to a bank account number and a garbled column header to a PIN code.

`FormInterpretationService` therefore reads each page's blanks **in context**, in two
passes, because one does not fit:

1. **Classify.** Every blank, in English only: which concept from the authored dictionary
   it is, who fills it in, what to write, and how confident the reading is. Compact enough
   that thirty blanks fit in one reply. An earlier single-pass design asked for all four
   languages at once and the output budget truncated it — five of thirty fields came back.
2. **Describe.** The four language columns, for the blanks the dictionary cannot serve:
   concepts we do not have, and fields the page qualifies (a parent's record, an office
   block, a value from an earlier roll). Ordinary fields about the applicant's own details
   are served from the dictionary's hand-written text instead, at no further cost.

The model never invents a field. It labels blanks the page analysis measured, and it may
reject one. An id it did not receive is discarded, a concept outside the vocabulary is
treated as unmapped, and a validation kind outside the allowed set becomes plain text, so
a hallucinated rule cannot reject a correct answer.

## Running this in production

- **Batching** — one request per batch of blanks, never one per field.
- **Caching** — keyed by a hash of the structural input, so re-uploading the same blank
  form costs nothing the second time and returns instantly.
- **Circuit breaker** — after three consecutive failures the interpreter is skipped for a
  cooldown, with one probe allowed after it. Without this, a provider outage makes every
  page of every upload wait for its full timeout before degrading.
- **Failover** — the provider rotates across API keys and models on rate limits and
  5xx responses, under an overall deadline, with the SDK's own retries switched off so
  that one retry loop is not nested inside another.
- **Empty completions are retried** — these models occasionally return a blank message
  with no error raised, typically when JSON mode meets a long prompt. Nothing in the
  transport notices, so the caller just sees unparseable output. An empty reply is retried
  without the JSON-mode constraint, and the whole-document pass additionally retries on a
  shorter extract. Measured on one form: the context read went from succeeding in none of
  one attempt to four of four.
- **Partial and failed batches are recovered, in both passes** — a batch is answered as a
  single JSON object, so one bad reply used to cost every field in it. A failed batch is
  bisected and a partial reply is topped up, which turns an all-or-nothing into a partial
  loss at worst. Splitting stops while the circuit is open, since a provider that is
  refusing should not be asked the same question twice more.

  This matters most in the **classification** pass, and that is where it was missing
  longest. Losing a batch there does not degrade those blanks a little; it drops them out
  of the system entirely — no display name, no concept, no four-language text — and they
  fall back to matching their own caption. On the ECI form that produced the worst visible
  symptom of the whole project: two identical `AC Number` cells in one row, one explained
  as the relative's constituency number and the other as "the printed label asks for a
  number or code".

- **A lost description does not discard the reading** — if the four-language pass fails
  for a field whose classification succeeded, the classifier's own sentence is used for
  English and the shape description for the other languages, rather than throwing both
  away and starting again from the caption.
- **No output budget** — `max_tokens` is left unset. These models reason before they
  answer and the reasoning is charged against the same allowance, so a limit empties the
  reply rather than shortening it. Batch size is what controls reply length.
- **Degradation** — if the interpreter is unavailable, unsure, or switched off, the
  offline dictionary path still runs. The application works without a network.
- **Rate limiting** — uploads are limited per client address, because each one costs OCR
  on every page and several model requests, and one client must not be able to spend a
  shared deployment's provider quota.
- **Observability** — `/api/metrics` reports request counts, failures, cache hit rate,
  average latency, circuit state, how many fields were served by the model versus the
  dictionary, how many were rejected, and how many language columns were discarded for
  being in the wrong script.

## Guidance priority

1. Exact known-form field guidance
2. The page interpreter's own four-language description of this blank, when it has one
3. The authored dictionary entry for the concept the interpreter chose
4. Common-field dictionary, confident match on the printed wording
5. Common-field dictionary, plausible match (fuzzy or partial), marked for verification
6. Retrieved related guidance above the similarity threshold, with a higher floor when the form itself is unknown
7. Label-pattern heuristic, which describes the shape of the answer and is marked as inferred
8. Groq interpretation of a single printed label, rejected if not written in the requested script
9. Honest unavailable state

Steps 2 and 3 need the interpreter; the rest work offline. When the interpreter reports no
concept for a blank, any earlier lexical guess is withdrawn rather than kept, because a
reading of the page is better evidence than a word match made from the caption alone.

Each step is implemented as a resolution object in `app/services/guidance_service.py` that knows how to render itself into any requested language. That is what allows one match to fill all four language columns without being resolved four times.

## Reading a page in four scripts

Three decisions are made in `app/providers/ocr/tesseract.py`, each because a single fixed choice measurably loses text on one of the supported scripts.

- **Which language models.** Loading every installed script at once makes the engine choose between four alphabets per glyph and corrupts Latin text. Script detection (`osd`) is accurate on Devanagari, Kannada, and Arabic pages but unreliable on Latin ones, so a confident non-Latin detection selects that model plus English, and anything else starts with English alone and widens only if the reading scores poorly.
- **Which image.** Erasing the form's rules helps layout analysis find labels wedged against a box border, but costs text on crisp scans. The page is read both ways and the word sets are merged, taking a word from the second reading only where the first found nothing at that position.
- **What counts as a rule.** Devanagari joins a word's letters under a continuous headline and Urdu joins them along a continuous baseline. A fixed-length kernel mistakes both for a ruling line, so candidates are measured per connected component and only long, thin runs are erased.

## Direction

Reading direction is handled in these places and nowhere else:

- `LabelAssociationService` searches to the right of a blank on a right-to-left page, and returns label words in reading order rather than screen order. Tesseract reports Urdu words with their true coordinates, so sorting by ascending x yields the reverse of how the words are read.
- `OCRResult.rtl` and per-line ordering keep `full_text` in reading order.
- The frontend sets direction per element, never on the page, because the form's printed labels and FormSathi's explanation can be in different scripts at the same time.

## Field semantics

`FieldSemanticsService` resolves a printed label, in any supported script, to a row of the common-field dictionary. Matching is layered so that certainty is never overstated: an exact wording wins outright, a contained wording scores by how much of the label it explains, and token-aligned fuzzy matching sits below both — that last layer is what carries noisy scans, and it is capped under the exact-match band so a smudged guess cannot outrank a clean reading. A single generic token inside a longer label ("bank" inside "bank account number") is demoted below the usable floor, so the label-pattern heuristic answers instead of the wrong dictionary row.

The resolved row supplies the field's input type and its validation rule, which is why an unknown form supports answer entry, validation, and the reference preview in the same way a known one does.

## Reading aloud

Browser speech voices are whatever the operating system has installed, and a Windows machine
usually has English and nothing else. The button used to disable itself when the chosen
language had no voice, which left Kannada and Urdu users with silence.

It now reads with the closest installed voice and says which one: Kannada falls back through
Telugu, Tamil, Malayalam and Hindi, Urdu through Arabic, Persian and Hindi — related
letter-to-sound rules, far closer than English — and the panel names the substitute so the
pronunciation is not mistaken for a bad translation. The utterance keeps the requested
language tag even when the voice is a stand-in, because some engines use it to pick
pronunciation rules independently of the voice, and it is read slightly slower.

The voice list arrives asynchronously and the first `getVoices()` call returns an empty
array, which is why an earlier version reported "no voice" for languages that were
installed. The hook watches `voiceschanged` and polls a few times for the browsers that
never fire it.

## No-LLM mode

The API starts without `GROQ_API_KEY`. Upload, OCR, detection, known-form help, answers, preview, and deletion remain available.
