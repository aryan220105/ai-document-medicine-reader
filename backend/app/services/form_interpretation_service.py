"""Reads a page's blanks in context, using a language model.

This exists because a lexical dictionary cannot resolve a caption whose meaning comes
from its column header. On the ECI declaration form, `Name:` and `Relative's Name:` each
appear twice on the same row under different headings, and `AC Name` is a constituency,
not a person. Matching those captions against a word list produces answers that are both
confident and wrong, which is the worst thing this application can do.

So the page's structure -- captions, column headers, sub-headings, nearby text -- is sent
to a model that is asked to explain each blank *in that context*, in all four languages at
once. The structure itself is still measured, not generated: the model never invents a
field, it only labels blanks the page analysis actually found, and it may reject one.

Operationally this is built to be run repeatedly and cheaply:

- one request per batch of fields, not one per field;
- results cached by a hash of the structural input, so re-uploading the same form costs
  nothing the second time;
- bounded retries, a timeout, key and model failover inside the provider, and a circuit
  breaker so a provider outage degrades to the offline dictionary instead of making every
  upload hang.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

from pydantic import ValidationError

from app.models.common import ALL_LANGUAGES, Language
from app.models.interpretation import (
    ClassifiedField,
    ClassifiedPage,
    FormContext,
    InterpretedField,
    InterpretedPage,
    WebContext,
)
from app.providers.llm.groq_provider import LLMRateLimitedError, LLMUnavailableError
from app.services.page_structure_service import Blank, PageLayout
from app.utils.text_normalization import dominant_script

logger = logging.getLogger(__name__)

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
CONTEXT_PROMPT_PATH = PROMPTS / "form_context_system.txt"
WEB_CONTEXT_PROMPT_PATH = PROMPTS / "form_web_context_system.txt"
CLASSIFY_PROMPT_PATH = PROMPTS / "form_classification_system.txt"
DESCRIBE_PROMPT_PATH = PROMPTS / "form_interpretation_system.txt"

EXPECTED_SCRIPT = {
    Language.ENGLISH: "latin",
    Language.HINDI: "devanagari",
    Language.KANNADA: "kannada",
    Language.URDU: "arabic",
}

# Page text sent as context. Enough to carry headings and declarations, bounded so a
# dense instruction page cannot blow up the request.
MAX_CONTEXT_LINES = 60

# Lines of whole-document text used to establish what the form is. Instruction sheets are
# verbose, and the first part of them carries the subject and the abbreviations.
MAX_DOCUMENT_LINES = 140

# Shorter extract used for a second attempt when the full one comes back empty.
SHORT_DOCUMENT_LINES = 55
MAX_LINE_CHARS = 160

# Output budgets, deliberately left unset.
#
# The models used here reason before they answer, and on this provider the reasoning is
# charged against `max_tokens`. Setting it does not truncate the answer, it suppresses it:
# measured on a two-page form, a budget of 1600 returned zero characters and a budget of
# 6000 also returned zero characters, while no budget at all returned a complete 1857
# character reply. Replies are instead kept short by batching -- a handful of fields per
# request -- which is the thing that actually controls their length.
CONTEXT_MAX_TOKENS = None
CLASSIFY_MAX_TOKENS = None
DESCRIBE_MAX_TOKENS = None


@dataclass
class InterpretationStats:
    """Counters worth having in production: they answer "is it working, and what is it
    costing" without turning on debug logging."""

    requests: int = 0
    failures: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    context_reads: int = 0
    web_lookups: int = 0
    web_lookups_useful: int = 0
    classified: int = 0
    described_by_model: int = 0
    served_from_dictionary: int = 0
    fields_interpreted: int = 0
    fields_rejected: int = 0
    dropped_wrong_script: int = 0
    breaker_open_skips: int = 0
    total_seconds: float = 0.0

    def snapshot(self) -> dict[str, float | int]:
        return {
            "requests": self.requests,
            "failures": self.failures,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "context_reads": self.context_reads,
            "web_lookups": self.web_lookups,
            "web_lookups_useful": self.web_lookups_useful,
            "classified": self.classified,
            "described_by_model": self.described_by_model,
            "served_from_dictionary": self.served_from_dictionary,
            "fields_interpreted": self.fields_interpreted,
            "fields_rejected": self.fields_rejected,
            "dropped_wrong_script": self.dropped_wrong_script,
            "breaker_open_skips": self.breaker_open_skips,
            "average_seconds": round(self.total_seconds / self.requests, 2) if self.requests else 0.0,
        }


@dataclass
class _Breaker:
    """Stops hammering a provider that is clearly down.

    After `threshold` consecutive failures the circuit opens and calls are skipped for
    `cooldown` seconds; the first call after that is allowed through as a probe. Without
    this, a provider outage would make every page of every upload wait for its full
    timeout before degrading.
    """

    threshold: int = 3
    cooldown: float = 60.0
    failures: int = 0
    opened_at: float = 0.0

    def allow(self) -> bool:
        if self.failures < self.threshold:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown:
            self.failures = self.threshold - 1  # let one probe through
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = 0.0

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()
            logger.warning("Form interpreter circuit opened after %s consecutive failures", self.failures)


@dataclass
class InterpretationCache:
    """In-memory cache keyed by the structure that produced the answer.

    Two uploads of the same blank form produce the same structural hash, so the second
    costs nothing and returns instantly. Bounded so a long-running process cannot grow
    without limit.
    """

    max_entries: int = 256
    entries: dict[str, object] = dataclass_field(default_factory=dict)
    order: list[str] = dataclass_field(default_factory=list)

    def get(self, key: str) -> object | None:
        return self.entries.get(key)

    def put(self, key: str, value: object) -> None:
        if key in self.entries:
            return
        self.entries[key] = value
        self.order.append(key)
        while len(self.order) > self.max_entries:
            self.entries.pop(self.order.pop(0), None)


class FormInterpretationService:
    """Two passes, because one does not fit.

    Pass one classifies every blank in English only: which concept it is, who fills it,
    what to write. Compact enough that a page of thirty blanks fits comfortably in one
    reply. An earlier single-pass design asked for all four languages at once and the
    model's output budget truncated it -- five of thirty fields came back.

    Pass two writes the four language columns, and runs only for the blanks the authored
    dictionary cannot serve. Most blanks on most forms map to a dictionary concept, whose
    Hindi, Kannada, and Urdu text is already written by hand and is better than anything
    generated per request.
    """

    def __init__(
        self,
        provider,
        dictionary=None,
        classify_batch: int = 10,
        describe_batch: int = 5,
        max_attempts: int = 2,
        cache: InterpretationCache | None = None,
        web_search_model: str = "",
    ) -> None:
        self.provider = provider
        self.dictionary = dictionary
        self.web_search_model = (web_search_model or "").strip()
        self.classify_batch = max(3, classify_batch)
        self.describe_batch = max(2, describe_batch)
        self.max_attempts = max(1, max_attempts)
        self.context_prompt = CONTEXT_PROMPT_PATH.read_text(encoding="utf-8")
        self.web_context_prompt = WEB_CONTEXT_PROMPT_PATH.read_text(encoding="utf-8")
        self.classify_prompt = CLASSIFY_PROMPT_PATH.read_text(encoding="utf-8")
        self.describe_prompt = DESCRIBE_PROMPT_PATH.read_text(encoding="utf-8")
        self.cache = cache or InterpretationCache()
        self.stats = InterpretationStats()
        self.breaker = _Breaker()

    def available(self) -> bool:
        return bool(self.provider) and self.provider.available()

    @property
    def vocabulary(self) -> list[str]:
        if self.dictionary is None:
            return []
        return [entry.id for entry in self.dictionary.entries]

    # --- public ------------------------------------------------------------------

    def read_context(self, document_lines: list[str]) -> FormContext | None:
        """Work out what the document is, once, before any field is described.

        Takes the printed text of every page, instruction sheets included. Those sheets
        are skipped by field detection -- they have no fields -- but they are where a form
        explains its own abbreviations and says which earlier record a value must come
        from, which is exactly what the per-field step needs and cannot infer from a
        caption.
        """
        if not document_lines or not self.available():
            return None
        usable = [line[:MAX_LINE_CHARS] for line in document_lines if line.strip()]
        if not usable:
            return None
        # Two goes, the second on a shorter extract. These models occasionally return an
        # empty message on a long prompt, and the first part of a form carries its title
        # and most of its abbreviations, so a trimmed second attempt usually succeeds
        # where the full one did not.
        for limit in (MAX_DOCUMENT_LINES, SHORT_DOCUMENT_LINES):
            context = self._read_context_once(usable[:limit])
            if context is not None:
                return context
            if limit == SHORT_DOCUMENT_LINES or len(usable) <= SHORT_DOCUMENT_LINES:
                break
            logger.info("Context read failed on %s lines; retrying with %s", limit, SHORT_DOCUMENT_LINES)
        return None

    def look_up_on_the_web(self, context: FormContext, extract: list[str]) -> WebContext | None:
        """Search the web for background on this form, by its printed title.

        Runs only when a web-search model is configured. Groq's "compound" models perform
        the search server-side; an ordinary chat model asked the same question would
        answer from its own memory, which is a different and much less trustworthy thing,
        so there is no fallback to one.

        The result only ever fills gaps the printed pages left -- an initialism the form
        never expands, the issuing body it never names. The paper in the user's hands
        stays the authority on itself, because a search result may describe a different
        edition of the form, or a different form with a similar name.
        """
        if not self.web_search_model or not self.available():
            return None
        title = (context.title or "").strip()
        if not title:
            return None
        if not self.breaker.allow():
            self.stats.breaker_open_skips += 1
            return None

        payload = json.dumps(
            {
                "form_title": title,
                "authority_on_the_form": context.authority,
                "abbreviations_the_form_did_not_explain": [
                    term for term in self._unexplained_terms(extract) if term not in context.glossary
                ][:12],
                "text_extract": extract[:25],
            },
            ensure_ascii=False,
        )
        key = "w:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
        cached = self.cache.get(key)
        if isinstance(cached, WebContext):
            self.stats.cache_hits += 1
            return cached

        self.stats.cache_misses += 1
        self.stats.web_lookups += 1
        try:
            raw = self.provider.generate_with_model(
                model=self.web_search_model,
                system_prompt=self.web_context_prompt,
                user_prompt=payload,
            )
        except Exception:
            # Background is a bonus. Losing it must never cost the upload.
            logger.info("Web background lookup unavailable; continuing without it")
            return None

        found = self._parse(raw, set(), WebContext)
        if found is None or not found.useful:
            return None
        self.stats.web_lookups_useful += 1
        self.cache.put(key, found)
        logger.info(
            "Web background: %r, %s abbreviations, sources=%s",
            found.official_name,
            len(found.glossary),
            found.sources[:3],
        )
        return found

    @staticmethod
    def _unexplained_terms(extract: list[str]) -> list[str]:
        """Initialisms on the page, so the search can be asked about them specifically."""
        seen: list[str] = []
        for line in extract:
            for token in re.findall(r"\b[A-Z]{2,6}\b", line):
                if token not in seen and token not in {"THE", "AND", "FOR", "NOT"}:
                    seen.append(token)
        return seen

    def _read_context_once(self, trimmed: list[str]) -> FormContext | None:
        payload = json.dumps({"pages_text_in_reading_order": trimmed}, ensure_ascii=False)
        key = "x:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
        cached = self.cache.get(key)
        if isinstance(cached, FormContext):
            self.stats.cache_hits += 1
            return cached
        self.stats.cache_misses += 1
        context = self._call(
            prompt=payload,
            system=self.context_prompt,
            expected=set(),
            model=FormContext,
            max_tokens=CONTEXT_MAX_TOKENS,
        )
        if context is None:
            return None
        self.stats.context_reads += 1
        self.cache.put(key, context)
        logger.info(
            "Form context: %r by %r, %s abbreviations, %s notes",
            context.title,
            context.authority,
            len(context.glossary),
            len(context.notes),
        )
        return context

    def classify(
        self, layout: PageLayout, form_title: str = "", context: FormContext | None = None
    ) -> dict[str, ClassifiedField]:
        """Work out what each blank on the page is. English only, one compact pass.

        An empty result is a normal outcome, not an error: it means the interpreter was
        unavailable or unsure, and the caller falls back to the offline dictionary.
        """
        if not layout.blanks or not self.available():
            return {}
        page_lines = self._page_context(layout)
        vocabulary = self.vocabulary
        briefing = context.summary() if context is not None else ""
        results: dict[str, ClassifiedField] = {}
        for batch in self._batches(layout.blanks, self.classify_batch):
            results.update(self._classify_batch(batch, form_title, page_lines, vocabulary, briefing))

        kept = {}
        for blank_id, item in results.items():
            if not item.is_field:
                self.stats.fields_rejected += 1
                continue
            if item.concept and item.concept not in set(vocabulary):
                # The model named a concept we do not have. Treat it as unmapped rather
                # than trusting a label we cannot back with authored text.
                item.concept = None
            kept[blank_id] = item
        self.stats.classified += len(kept)
        return kept

    def _classify_batch(
        self,
        batch: list[Blank],
        form_title: str,
        page_lines: list[str],
        vocabulary: list[str],
        briefing: str,
    ) -> dict[str, ClassifiedField]:
        """Classify one batch, splitting it rather than losing it when a reply fails.

        This is the step everything else rests on: the four-language description, the
        display name, the concept, who fills the field in. Losing a batch of ten here does
        not degrade those ten fields a little, it drops them out of the system entirely
        and they fall back to matching their own caption -- which is how one "AC Number"
        cell came out as the relative's constituency number and the one beside it as "the
        printed label asks for a number or code".
        """
        key = "c:" + self._cache_key(form_title + briefing, page_lines, batch)
        cached = self.cache.get(key)
        if isinstance(cached, ClassifiedPage):
            self.stats.cache_hits += 1
            return cached.by_id()

        self.stats.cache_misses += 1
        page = self._call(
            prompt=self._classify_prompt_for(form_title, page_lines, batch, vocabulary, briefing),
            system=self.classify_prompt,
            expected={blank.id for blank in batch},
            model=ClassifiedPage,
            max_tokens=CLASSIFY_MAX_TOKENS,
        )
        if page is not None:
            self.cache.put(key, page)
            answered = page.by_id()
            missing = [blank for blank in batch if blank.id not in answered]
            if missing and len(batch) > 1 and self.breaker.allow():
                # A reply that covered only part of the batch. Ask again for the rest,
                # rather than leaving those blanks with no reading at all.
                logger.info(
                    "Classify reply covered %s of %s blanks; asking again for the rest",
                    len(answered),
                    len(batch),
                )
                answered.update(
                    self._classify_batch(missing, form_title, page_lines, vocabulary, briefing)
                )
            return answered

        if len(batch) <= 1:
            logger.info("Giving up on classifying blank %s", batch[0].id if batch else "?")
            return {}
        if not self.breaker.allow():
            # The provider is refusing outright. Splitting would only ask it twice more.
            logger.info("Not splitting a failed classify batch of %s: circuit is open", len(batch))
            return {}

        middle = len(batch) // 2
        logger.info("Classify batch of %s failed; splitting", len(batch))
        recovered = self._classify_batch(batch[:middle], form_title, page_lines, vocabulary, briefing)
        recovered.update(self._classify_batch(batch[middle:], form_title, page_lines, vocabulary, briefing))
        return recovered

    def describe(
        self,
        layout: PageLayout,
        blanks: list[Blank],
        classified: dict[str, ClassifiedField],
        form_title: str = "",
        context: FormContext | None = None,
    ) -> dict[str, InterpretedField]:
        """Write the four language columns for the blanks the dictionary cannot serve."""
        if not blanks or not self.available():
            return {}
        page_lines = self._page_context(layout)
        briefing = context.summary() if context is not None else ""
        results: dict[str, InterpretedField] = {}
        for batch in self._batches(blanks, self.describe_batch):
            results.update(self._describe_batch(batch, form_title, page_lines, classified, briefing))

        kept: dict[str, InterpretedField] = {}
        for blank_id, interpreted in results.items():
            cleaned = self._keep_native_languages(interpreted)
            if cleaned is None or not cleaned.is_field:
                self.stats.fields_rejected += 1
                continue
            kept[blank_id] = cleaned
        self.stats.described_by_model += len(kept)
        self.stats.fields_interpreted += len(kept)
        return kept

    def _describe_batch(
        self,
        batch: list[Blank],
        form_title: str,
        page_lines: list[str],
        classified: dict[str, ClassifiedField],
        briefing: str,
    ) -> dict[str, InterpretedField]:
        """Describe one batch, splitting it in half rather than losing it on failure.

        A batch is answered as a single JSON object, so one unusable reply used to cost
        every field in it: on a thirty-field form that left four fields with nothing but
        a generic "this asks for a number" where the rest had full descriptions. Bisecting
        turns the all-or-nothing into a partial loss at worst, and usually no loss at all,
        since a shorter request is likelier to come back well-formed.
        """
        key = "d:" + self._cache_key(form_title + briefing, page_lines, batch)
        cached = self.cache.get(key)
        if isinstance(cached, InterpretedPage):
            self.stats.cache_hits += 1
            return cached.by_id()

        self.stats.cache_misses += 1
        page = self._call(
            prompt=self._describe_prompt_for(form_title, page_lines, batch, classified, briefing),
            system=self.describe_prompt,
            expected={blank.id for blank in batch},
            model=InterpretedPage,
            max_tokens=DESCRIBE_MAX_TOKENS,
        )
        if page is not None:
            self.cache.put(key, page)
            answered = page.by_id()
            missing = [blank for blank in batch if blank.id not in answered]
            if missing and len(batch) > 1:
                # A partial answer. Ask again only for what it left out.
                logger.info("Describe reply covered %s of %s fields; retrying the rest", len(answered), len(batch))
                answered.update(
                    self._describe_batch(missing, form_title, page_lines, classified, briefing)
                )
            return answered

        if len(batch) <= 1:
            logger.info("Giving up on describing field %s", batch[0].id if batch else "?")
            return {}

        if not self.breaker.allow():
            # The provider is refusing. Splitting the batch would only ask it the same
            # question twice more, so stop here and let the offline path take over.
            logger.info("Not splitting a failed batch of %s: circuit is open", len(batch))
            return {}

        middle = len(batch) // 2
        logger.info("Describe batch of %s failed; splitting", len(batch))
        recovered = self._describe_batch(batch[:middle], form_title, page_lines, classified, briefing)
        recovered.update(self._describe_batch(batch[middle:], form_title, page_lines, classified, briefing))
        return recovered

    # --- request building ---------------------------------------------------------

    @staticmethod
    def _batches(blanks: list[Blank], size: int) -> list[list[Blank]]:
        return [blanks[i : i + size] for i in range(0, len(blanks), size)]

    @staticmethod
    def _page_context(layout: PageLayout) -> list[str]:
        lines = [line.text.strip()[:MAX_LINE_CHARS] for line in layout.text_lines if line.text.strip()]
        for table in layout.tables:
            for cell in sorted(table.cells, key=lambda item: (item.row, item.column)):
                if cell.text:
                    lines.append(cell.text.strip()[:MAX_LINE_CHARS])
        return lines[:MAX_CONTEXT_LINES]

    @staticmethod
    def _blank_payload(blank: Blank) -> dict[str, object]:
        payload: dict[str, object] = {"id": blank.id, "caption": blank.caption or ""}
        if blank.column_header:
            payload["column_header"] = blank.column_header
        if blank.sub_header:
            payload["sub_heading"] = blank.sub_header
        if blank.section:
            payload["section"] = blank.section
        if blank.nearby_text:
            payload["nearby_text"] = blank.nearby_text[:200]
        payload["shape"] = blank.origin
        if blank.table_index >= 0:
            payload["table"] = blank.table_index
            payload["row"] = blank.row
            payload["column"] = blank.column
        return payload

    def _classify_prompt_for(
        self,
        form_title: str,
        page_lines: list[str],
        batch: list[Blank],
        vocabulary: list[str],
        briefing: str = "",
    ) -> str:
        payload = {
            "form_title": form_title or "unknown",
            "page_text_in_reading_order": page_lines,
            "concept_vocabulary": vocabulary,
            "blanks": [self._blank_payload(blank) for blank in batch],
        }
        if briefing:
            # What the document is, established before any field was looked at. This is
            # what distinguishes an Assembly Constituency number from an account number
            # when both are captioned "AC No.".
            payload["what_this_form_is"] = briefing
        return json.dumps(payload, ensure_ascii=False)

    def _describe_prompt_for(
        self,
        form_title: str,
        page_lines: list[str],
        batch: list[Blank],
        classified: dict[str, ClassifiedField],
        briefing: str = "",
    ) -> str:
        blanks = []
        for blank in batch:
            payload = self._blank_payload(blank)
            known = classified.get(blank.id)
            if known is not None:
                # Carry the first pass's reading forward so the two stages agree.
                payload["understood_as"] = known.label
                payload["english_instruction"] = known.what_to_enter
            blanks.append(payload)
        payload = {
            "form_title": form_title or "unknown",
            "languages_required": [language.value for language in ALL_LANGUAGES],
            "page_text_in_reading_order": page_lines,
            "blanks": blanks,
        }
        if briefing:
            payload["what_this_form_is"] = briefing
        return json.dumps(payload, ensure_ascii=False)

    def _cache_key(self, form_title: str, context: list[str], batch: list[Blank]) -> str:
        payload = json.dumps(
            {
                "title": form_title or "unknown",
                "context": context,
                "blanks": [self._blank_payload(blank) for blank in batch],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # --- the call -----------------------------------------------------------------

    def _call(self, *, prompt: str, system: str, expected: set[str], model, max_tokens: int):
        """One provider round-trip, with a repair retry and the circuit breaker."""
        if not self.breaker.allow():
            self.stats.breaker_open_skips += 1
            logger.info("Skipping interpreter call: circuit open")
            return None

        started = time.monotonic()
        for attempt in range(self.max_attempts):
            try:
                self.stats.requests += 1
                raw = self.provider.generate_sync(
                    system_prompt=system,
                    user_prompt=prompt if attempt == 0 else self._repair_prompt(prompt),
                    max_tokens=max_tokens,
                )
            except LLMRateLimitedError:
                self.stats.failures += 1
                self.breaker.record_failure()
                logger.warning("Form interpreter rate-limited; falling back to offline guidance")
                return None
            except LLMUnavailableError:
                self.stats.failures += 1
                self.breaker.record_failure()
                return None
            except Exception:
                self.stats.failures += 1
                self.breaker.record_failure()
                logger.exception("Form interpreter call failed")
                return None

            parsed = self._parse(raw, expected, model)
            if parsed is not None:
                self.breaker.record_success()
                self.stats.total_seconds += time.monotonic() - started
                return parsed
            logger.info("Form interpreter returned unusable JSON (attempt %s)", attempt + 1)

        self.stats.failures += 1
        self.breaker.record_failure()
        return None

    @staticmethod
    def _repair_prompt(prompt: str) -> str:
        return (
            "Your previous reply was not valid JSON matching the required schema. "
            "Return only the JSON object, with one entry per blank id.\n\n" + prompt
        )

    @staticmethod
    def _parse(raw: str, expected: set[str], model):
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            payload = json.loads(raw[start : end + 1] if start >= 0 and end > start else raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        try:
            parsed = model.model_validate(payload)
        except ValidationError:
            return None
        if not hasattr(parsed, "fields"):
            # A whole-document answer (the form context), not a list of fields.
            return parsed
        # Ignore any id the model invented; the page analysis decides which blanks exist.
        parsed.fields = [item for item in parsed.fields if item.id in expected]
        return parsed if parsed.fields else None

    def _keep_native_languages(self, interpreted: InterpretedField) -> InterpretedField | None:
        """Drop any language the model did not actually write in the right script.

        Asked for Hindi, a model will often reply in romanised Hindi. That is not a Hindi
        translation, and showing it under a Hindi heading is worse than showing a gap,
        because it looks like one.
        """
        kept = {}
        for language in ALL_LANGUAGES:
            text = (interpreted.what_to_enter.get(language.value) or "").strip()
            if not text:
                continue
            if dominant_script(text) != EXPECTED_SCRIPT[language]:
                self.stats.dropped_wrong_script += 1
                continue
            kept[language.value] = text
        if not kept:
            return None
        interpreted.what_to_enter = kept
        for attribute in ("label", "why_needed", "format_hint"):
            current = getattr(interpreted, attribute) or {}
            setattr(interpreted, attribute, {k: v for k, v in current.items() if k in kept})
        return interpreted
