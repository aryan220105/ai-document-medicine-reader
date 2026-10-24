from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.api.errors import bad_request, conflict, not_found
from app.config import Settings
from app.models.common import ALL_LANGUAGES, DocumentCategory, DocumentStatus, Language, ProcessingStage
from app.models.document import DocumentPage, DocumentRecord, DocumentResponse
from app.models.fields import DetectedField, FieldAnswer, ValidationResult
from app.models.ocr import OCRResult
from app.models.guidance import (
    AskRequest,
    AskResponse,
    FieldGuidance,
    GuidanceBundleRequest,
    GuidanceBundleResponse,
    GuidanceRequest,
)
from app.models.preview import PreviewRequest, PreviewResult
from app.repositories.document_repository import DocumentRepository
from app.services.field_detection_service import FieldDetectionService
from app.services.field_semantics_service import FieldSemanticsService
from app.services.form_identification_service import FormIdentificationService
from app.services.guidance_service import GuidanceService
from app.services.image_service import ImageService
from app.services.label_association_service import LabelAssociationService
from app.services.ocr_service import OCRService
from app.services.pdf_service import PdfService
from app.services.preview_service import PreviewService
from app.services.sir_form_service import SirFormService
from app.services.storage_service import StorageService
from app.services.validation_service import ValidationService
from app.utils.text_normalization import match_tokens

logger = logging.getLogger(__name__)

# How far from a blank to look when re-reading a missing label. Matches the label search
# span used during association.
LABEL_REGION_SPAN = 0.42

class DocumentService:
    def __init__(
        self,
        settings: Settings,
        storage: StorageService,
        documents: DocumentRepository,
        image_service: ImageService,
        pdf_service: PdfService,
        ocr_service: OCRService,
        field_detection: FieldDetectionService,
        label_association: LabelAssociationService,
        form_identification: FormIdentificationService,
        page_structure,
        field_assembly,
        interpreter,
        semantics: FieldSemanticsService,
        guidance: GuidanceService,
        preview: PreviewService,
        validation: ValidationService,
        llm_configured: bool,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.documents = documents
        self.image_service = image_service
        self.pdf_service = pdf_service
        self.ocr_service = ocr_service
        self.field_detection = field_detection
        self.label_association = label_association
        self.form_identification = form_identification
        self.page_structure = page_structure
        self.field_assembly = field_assembly
        self.interpreter = interpreter
        self.semantics = semantics
        self.guidance = guidance
        self.preview = preview
        self.validation = validation
        self.llm_configured = llm_configured
        self.sir_forms = SirFormService()

    async def create_from_upload(
        self,
        upload: UploadFile,
        category: DocumentCategory = DocumentCategory.OTHER,
    ) -> DocumentRecord:
        payload = await upload.read()
        if not payload:
            raise bad_request("empty_file", "The uploaded file was empty.")
        if len(payload) > self.settings.max_upload_bytes:
            raise bad_request(
                "file_too_large",
                f"Please upload a file smaller than {self.settings.max_upload_mb} MB.",
            )
        suffix, mime = self._sniff(payload, upload.content_type, upload.filename)
        document_id = str(uuid4())
        original_path = self.settings.uploads_dir / f"{document_id}{suffix}"
        original_path.write_bytes(payload)
        record = DocumentRecord(
            id=document_id,
            original_filename=Path(upload.filename or "form").name,
            original_path=str(original_path),
            mime_type=mime,
            category=category,
            status=DocumentStatus.PROCESSING,
            stage=ProcessingStage.VALIDATING,
        )
        self.documents.save(record)
        logger.info("Stored upload document_id=%s mime=%s", record.id, mime)
        return record

    def process(self, document_id: str) -> DocumentRecord:
        record = self.documents.get(document_id)
        if record is None:
            raise KeyError(document_id)
        try:
            if not self.ocr_service.available():
                raise RuntimeError("Tesseract OCR is not installed. Install Tesseract and try again.")
            self.documents.update_stage(document_id, ProcessingStage.PREPARING_PAGES)
            page_paths = self._prepare_pages(record)
            pages: list[DocumentPage] = []
            ocr_pages: list[OCRResult] = []
            fields: list[DetectedField] = []
            layouts: list = []
            for index, source in enumerate(page_paths):
                processed = self.storage.processed_page_path(document_id, index)
                preprocess = self.image_service.preprocess(str(source), str(processed))
                pages.append(
                    DocumentPage(
                        index=index,
                        original_path=str(source),
                        processed_path=preprocess.processed_path,
                        width=preprocess.processed_width,
                        height=preprocess.processed_height,
                        detection_succeeded=preprocess.detection_succeeded,
                    )
                )
                self.documents.update_stage(document_id, ProcessingStage.READING_TEXT)
                ocr = self.ocr_service.extract(preprocess.processed_path, page_index=index)
                if not ocr.has_useful_text:
                    ocr = self.ocr_service.extract(str(source), page_index=index)
                if record.mime_type == "application/pdf":
                    embedded = self.pdf_service.read_embedded_text(
                        Path(record.original_path),
                        index,
                        preprocess.processed_width,
                        preprocess.processed_height,
                    )
                    if embedded is not None:
                        ocr = embedded
                ocr_pages.append(ocr)
                self.documents.update_stage(document_id, ProcessingStage.DETECTING_FIELDS)
                layout = self.page_structure.analyse(preprocess.processed_path, ocr, index)
                layouts.append(layout)
                if layout.looks_like_prose:
                    # An instruction or information sheet. Inventing fields here is worse
                    # than finding none, so the page is carried for display and skipped.
                    logger.info("Page %s looks like instructions; no fields proposed", index)
                    continue
                self.page_structure.add_marks(
                    layout, self.field_detection.detect_marks(preprocess.processed_path, index)
                )
                legacy = self.label_association.associate(
                    self.field_detection.detect(preprocess.processed_path, index), ocr
                )
                page_fields = self.field_assembly.build(layout, legacy, index)
                recovered = self.recover_missing_labels(page_fields, preprocess.processed_path, ocr)
                if recovered:
                    logger.info("Recovered %s label(s) by region re-read on page %s", recovered, index)
                fields.extend(page_fields)
            if not any(page.full_text.strip() for page in ocr_pages):
                raise RuntimeError("No useful printed text could be read from this form.")
            self.documents.update_stage(document_id, ProcessingStage.MATCHING_FORM)
            match = self.form_identification.match(ocr_pages, fields, record.category)
            if match.form_id:
                for field in fields:
                    found = self.guidance.knowledge.find_field(match.form_id, [field.label], Language.ENGLISH)
                    if found:
                        field.known_field_id = found["field"]["field_id"]
            # Resolve every field against the multilingual dictionary, recognised form or
            # not. This is what makes an unknown form behave like a known one: each field
            # gains a semantic identity, an input type, and a validation rule, so answer
            # entry and the reference preview work the same way on both paths.
            self._resolve_semantics(fields)
            # Read the page in context. This is what disambiguates captions whose meaning
            # comes from a column header rather than the caption itself, and what keeps a
            # field that belongs to the office out of the applicant's list.
            self._interpret(record, fields, layouts, ocr_pages)
            fields = self.sir_forms.correct(fields, ocr_pages)
            renamed = [field for field in fields if "sir_layout" in field.confidence_reasons]
            for field in renamed:
                self.label_association.tag_script(field)
            self._resolve_semantics(renamed)
            record.pages = pages
            record.ocr = ocr_pages
            record.fields = fields
            record.form_match = match
            record.scripts = sorted({page.script for page in ocr_pages if page.script != "unknown"})
            record.suggested_language = self._suggested_language(fields, ocr_pages)
            record.stage = ProcessingStage.READY
            record.status = DocumentStatus.READY
            record.error_message = None
            self.documents.save(record)
            return record
        except Exception as exc:
            message = str(exc)
            friendly = message if "Tesseract" in message or "encrypted" in message.lower() or "PDF" in message else (
                "I could not process this form. Try a clearer scan or a simpler photograph."
            )
            logger.exception("Processing failed for document_id=%s", document_id)
            record.status = DocumentStatus.FAILED
            record.stage = ProcessingStage.FAILED
            record.error_message = friendly
            self.documents.save(record)
            return record

    def get(self, document_id: str) -> DocumentRecord:
        record = self.documents.get(document_id)
        if record is None:
            raise not_found("missing_document", "This form is no longer available.")
        return record

    def delete(self, document_id: str) -> None:
        record = self.documents.delete(document_id)
        if record is None:
            raise not_found("missing_document", "This form is no longer available.")
        self.storage.delete_tree(record.original_path)
        self.storage.delete_tree(self.settings.processed_dir / document_id)
        self.storage.delete_tree(self.settings.previews_dir / document_id)
        for page in record.pages:
            self.storage.delete_tree(page.original_path, page.processed_path)

    def field(self, record: DocumentRecord, field_id: str) -> DetectedField:
        for item in record.fields:
            if item.id == field_id:
                return item
        raise not_found("missing_field", "That field was not found on this form.")

    def guide(self, document_id: str, request: GuidanceRequest) -> FieldGuidance:
        record = self._ready(document_id)
        field = self.field(record, request.field_id)
        request.category = request.category or record.category
        if request.allow_external_ai and not self.llm_configured:
            request.allow_external_ai = False
        return self.guidance.for_field(
            field,
            request,
            record.form_match.form_id,
            record.ocr,
            interpreted=record.interpreted.get(field.id),
            classified=record.classified.get(field.id),
        )

    def ask(self, document_id: str, request: AskRequest) -> AskResponse:
        record = self._ready(document_id)
        field = self.field(record, request.field_id) if request.field_id else record.fields[0]
        if request.allow_external_ai and not self.llm_configured:
            request.allow_external_ai = False
        return self.guidance.ask(field, request, record.form_match.form_id, record.ocr)

    def validate_answer(
        self,
        document_id: str,
        answer: FieldAnswer,
        language: Language = Language.ENGLISH,
    ) -> ValidationResult:
        record = self._ready(document_id)
        return self.validation.validate(self.field(record, answer.field_id), answer, language)

    def create_preview(self, document_id: str, request: PreviewRequest) -> PreviewResult:
        record = self._ready(document_id)
        overflow = []
        for answer in request.answers:
            result = self.validation.validate(self.field(record, answer.field_id), answer, request.language)
            if not result.ok:
                overflow.append(result.message or "Invalid value")
        built = self.preview.render(record, request)
        if overflow:
            from app.models.preview import PreviewWarning

            built.warnings.extend(
                PreviewWarning(field_id="validation", code="invalid_value", message=item) for item in overflow if item
            )
        if built.pdf_path:
            built.pdf_url = f"/api/documents/{document_id}/previews/{built.preview_id}.pdf"
        return built

    def preview_pdf(self, document_id: str, preview_id: str) -> Path:
        path = self.settings.previews_dir / document_id / preview_id / "preview.pdf"
        resolved = path.resolve()
        root = self.settings.previews_dir.resolve()
        if root not in resolved.parents and resolved != root:
            raise not_found("missing_preview", "Preview not found.")
        if not resolved.exists():
            raise not_found("missing_preview", "Preview not found.")
        return resolved

    def page_image(self, document_id: str, page_index: int, kind: str) -> Path:
        record = self.get(document_id)
        if page_index < 0 or page_index >= len(record.pages):
            raise not_found("missing_page", "That page is not available.")
        page = record.pages[page_index]
        path = Path(page.processed_path if kind == "processed" and page.processed_path else page.original_path)
        if not path.exists():
            raise not_found("missing_page", "That page is not available.")
        return path

    def to_response(self, record: DocumentRecord) -> DocumentResponse:
        return DocumentResponse(
            id=record.id,
            original_filename=record.original_filename,
            status=record.status,
            stage=record.stage,
            category=record.category,
            page_count=len(record.pages),
            fields=record.fields,
            form_match=record.form_match,
            error_message=record.error_message,
            llm_configured=self.llm_configured,
            scripts=record.scripts,
            suggested_language=record.suggested_language,
            interpreter_used=record.interpreter_used,
            form_context=record.form_context,
            created_at=record.created_at,
        )

    def recover_missing_labels(
        self,
        fields: list[DetectedField],
        image_path: str,
        ocr: OCRResult,
    ) -> int:
        """Give every unlabelled field a second chance at its printed label.

        Whole-page segmentation occasionally refuses to see a caption that sits beside a
        large empty box, so a field arrives with no label at all and therefore no
        guidance. Here the region the label must occupy -- to the left of the blank, or to
        its right on a right-to-left page, and failing that the strip directly above it --
        is cropped and read on its own. Returns how many labels were recovered.
        """
        recovered = 0
        rtl = ocr.rtl
        lang = "+".join(ocr.languages_used) or None
        for field in fields:
            if (field.label or "").strip():
                continue
            if field.sub_header or field.column_header:
                # The grid already explains this cell. Re-reading the space beside it
                # finds the neighbouring cells' rules and returns noise like
                # "| Pie IMMERSE |", which would then become the field's name.
                continue
            box = field.input_box
            pad = max(box.height * 0.6, 0.012)
            right_edge = min(1.0, box.x + box.width)
            regions = []
            if rtl:
                regions.append(
                    (right_edge, box.y - pad, min(LABEL_REGION_SPAN, 1.0 - right_edge), box.height + 2 * pad)
                )
                # A label printed above a wide box is right-aligned on a right-to-left
                # page, so the strip has to hug the box's right edge, not its left one.
                above_x = max(0.0, right_edge - 0.6)
                regions.append((above_x, max(0.0, box.y - 0.045), right_edge - above_x, 0.042))
            else:
                start = max(0.0, box.x - LABEL_REGION_SPAN)
                regions.append((start, box.y - pad, box.x - start, box.height + 2 * pad))
                regions.append((box.x, max(0.0, box.y - 0.045), min(box.width, 0.6), 0.042))

            found = False
            for x, y, width, height in regions:
                if width <= 0 or height <= 0:
                    continue
                # Two segmentation modes: "one line" reads a clean caption best, but a
                # strip that still contains part of a rule or a box border defeats it,
                # and "uniform block" copes with that. The first plausible answer wins.
                for psm in (7, 6):
                    text = self.ocr_service.read_region(
                        image_path, x, max(0.0, y), width, height, lang=lang, psm=psm
                    )
                    cleaned = text.strip(" :.-۔।")
                    if self._plausible_label(cleaned):
                        found = True
                        break
                if not found:
                    continue
                field.label = cleaned
                field.confidence_reasons = [*field.confidence_reasons, "label_region_reread"]
                self.label_association.tag_script(field)
                recovered += 1
                break
        return recovered

    @staticmethod
    def _plausible_label(text: str) -> bool:
        """Reject a re-read that is noise rather than a label.

        Reading a narrow strip with single-line segmentation will happily turn a rule, a
        box border, or a smudge into a run of punctuation and stray diacritics. Keeping
        such a string would be worse than keeping nothing: it becomes the field's name in
        the interface and it can fuzzy-match a dictionary entry by accident.
        """
        if not text or not 3 <= len(text) <= 60:
            return False
        if "|" in text or text.count("_") > 2:
            # Table rules read as pipes and underscores. Whatever came back is the grid,
            # not a caption.
            return False
        words = match_tokens(text)
        if not any(len(word) >= 2 for word in words):
            return False
        # A smear such as "gtonimensetonlnthe" is longer than any real Latin label
        # word on these forms. Indic and Arabic words are not ASCII, so they stay.
        letters = "".join(
            ch if ch.isalpha() else " "
            for ch in text
            if unicodedata.category(ch) != "Cf"
        )
        for token in letters.split():
            if token.isascii() and len(token) >= 16:
                return False
        # Combining marks count as part of a letter. Indic vowel signs and Arabic
        # diacritics are not "alphabetic" to Python, so counting only `isalpha` would
        # reject a perfectly good Kannada or Urdu label such as "ವೃತ್ತಿ".
        meaningful = sum(
            1 for char in text if char.isalpha() or unicodedata.category(char).startswith("M")
        )
        total = sum(1 for char in text if not char.isspace())
        return total > 0 and meaningful / total >= 0.7

    def _interpret(self, record: DocumentRecord, fields: list[DetectedField], layouts: list, ocr_pages) -> None:
        """Read each page's blanks in context and attach what was understood.

        Work is divided to keep this cheap and mostly deterministic:

        * the model classifies every blank in English (one compact request per batch) and
          maps it onto a concept from the authored dictionary;
        * a blank that maps cleanly to a concept and needs no qualification is then
          described from the dictionary's hand-written text in all four languages, at no
          further cost and with the quality of authored prose;
        * only the remainder -- concepts we do not have, and fields the page qualifies
          (a parent's record, an office block, a value from an earlier roll) -- go back
          to the model for four-language text.

        If the interpreter is unavailable the whole step is skipped and the lexical
        dictionary path still applies, so the application keeps working without it.
        """
        if self.interpreter is None or not self.interpreter.available():
            return
        by_id = {field.id: field for field in fields}
        title = self._form_title(ocr_pages)

        # Establish what the document is before describing anything in it. Every page's
        # text goes in, instruction sheets included: those have no fields of their own,
        # which is why field detection skips them, but they are where the form explains
        # its abbreviations and says which earlier record a value must be copied from.
        document_lines = self._document_lines(ocr_pages, layouts)
        context = self.interpreter.read_context(document_lines)
        if context is not None:
            # Optional: look the form up on the web by its printed title, to fill gaps the
            # pages left -- an initialism the form never expands, an issuing body it never
            # names. Off unless a web-search model is configured, and it only ever adds to
            # what the paper said, never overrides it.
            web = self.interpreter.look_up_on_the_web(context, document_lines[:40])
            if web is not None:
                context.merge_web(web)
            record.form_context = context

        needs_description: dict[int, list] = {}

        for layout in layouts:
            if layout.looks_like_prose or not layout.blanks:
                continue
            classified = self.interpreter.classify(layout, form_title=title, context=context)
            if not classified:
                continue
            record.interpreter_used = True
            record.classified.update(classified)
            for blank in layout.blanks:
                reading = classified.get(blank.id)
                field = by_id.get(blank.id)
                if reading is None or field is None:
                    continue
                self._apply_classification(field, reading)
                if self._needs_model_description(reading):
                    needs_description.setdefault(layout.page_index, []).append(blank)
                else:
                    # Served from the dictionary's hand-written four-language text, with
                    # no further request. Counted so the saving is visible in /api/metrics.
                    self.interpreter.stats.served_from_dictionary += 1

        for layout in layouts:
            pending = needs_description.get(layout.page_index)
            if not pending:
                continue
            described = self.interpreter.describe(
                layout, pending, record.classified, form_title=title, context=context
            )
            record.interpreted.update(described)

        # Drop blanks the model judged not to be fields at all.
        rejected = {
            field_id
            for field_id, reading in record.classified.items()
            if not reading.is_field
        }
        if rejected:
            fields[:] = [field for field in fields if field.id not in rejected]
            logger.info("Interpreter rejected %s proposed blank(s)", len(rejected))

    def _needs_model_description(self, reading) -> bool:
        if not reading.is_field:
            return False
        if reading.concept is None:
            return True
        if reading.needs_detail:
            return True
        return reading.fill_by.value != "applicant"

    def _apply_classification(self, field: DetectedField, reading) -> None:
        field.display_label = reading.label or field.label
        field.filled_by = reading.fill_by.value
        if reading.concept:
            field.semantic_id = reading.concept
            field.semantic_source = "interpreter"
            field.semantic_score = reading.confidence
            entry = self.semantics.dictionary.get(reading.concept)
            if entry is not None:
                field.field_type = self.semantics.field_type_for(entry.field_type, field.field_type)
                field.validation_rule = self.semantics.validation_rule(entry.validation)
        else:
            # Reading the page found no concept for this blank. That judgement is better
            # than a lexical guess made from the caption alone, which is how "AC Name"
            # became a person's name, so the earlier guess is withdrawn.
            field.semantic_id = None
            field.semantic_source = "interpreter"
            field.label_pattern_id = None
        if reading.validation and reading.validation != "text":
            # The page's own reading of the expected format beats the concept's default.
            field.validation_rule = self.semantics.validation_rule({"kind": reading.validation})

    @staticmethod
    def _document_lines(ocr_pages, layouts) -> list[str]:
        """Every page's printed text in reading order, for the whole-document pass."""
        lines: list[str] = []
        for page in ocr_pages:
            for line in page.lines:
                text = line.text.strip()
                if text:
                    lines.append(text)
        return lines

    @staticmethod
    def _form_title(ocr_pages) -> str:
        for page in ocr_pages:
            lines = [line.text.strip() for line in page.lines if line.text.strip()]
            if lines:
                return " / ".join(lines[:3])[:200]
        return ""

    def _resolve_semantics(self, fields: list[DetectedField]) -> None:
        for field in fields:
            if not (field.label or "").strip():
                continue
            match = self.semantics.resolve(field.label, field.field_type)
            if match is not None:
                field.semantic_id = match.entry.id
                field.semantic_score = match.score
                field.semantic_source = match.how
                field.field_type = self.semantics.field_type_for(match.entry.field_type, field.field_type)
                field.validation_rule = self.semantics.validation_rule(match.entry.validation)
                continue
            pattern = self.semantics.match_pattern(field.label, field.field_type)
            if pattern is not None:
                field.label_pattern_id = pattern.pattern.id
                field.semantic_score = pattern.score
                field.semantic_source = "label_pattern"
                field.field_type = self.semantics.field_type_for(pattern.pattern.field_type, field.field_type)
                field.validation_rule = self.semantics.validation_rule(pattern.pattern.validation)

    def _suggested_language(self, fields: list[DetectedField], ocr_pages: list[OCRResult]) -> Language:
        """Which explanation language to open with.

        Chosen from the script the field labels are printed in, so an Urdu form opens with
        Urdu guidance. It is only a default: the user switches freely afterwards, and the
        choice never affects the form's own content.
        """
        votes: dict[str, int] = {}
        for field in fields:
            if field.label_language:
                votes[field.label_language] = votes.get(field.label_language, 0) + 1
        if not votes:
            for page in ocr_pages:
                code = self.semantics.label_language(page.full_text).value
                votes[code] = votes.get(code, 0) + 1
        if not votes:
            return Language.ENGLISH
        # Prefer a regional script over English: a bilingual form prints English headings
        # but the applicant reading it needs the regional column.
        regional = {code: count for code, count in votes.items() if code != Language.ENGLISH.value}
        chosen = max(regional or votes, key=lambda code: votes[code])
        try:
            return Language(chosen)
        except ValueError:
            return Language.ENGLISH

    def guidance_bundles(self, document_id: str, request: GuidanceBundleRequest) -> GuidanceBundleResponse:
        """Guidance for many fields in many languages in one call.

        The frontend takes the whole bundle up front so switching explanation language is
        instant and offline, and so a language switch cannot disturb the user's typed
        answers or the rendered form.
        """
        record = self._ready(document_id)
        languages = list(request.languages or ALL_LANGUAGES)
        allow_ai = request.allow_external_ai and self.llm_configured
        wanted = request.field_ids
        selected = [field for field in record.fields if wanted is None or field.id in wanted]
        bundles = [
            self.guidance.bundle_for_field(
                field,
                record.form_match.form_id,
                record.ocr,
                languages=languages,
                allow_external_ai=allow_ai,
                category=request.category or record.category,
                interpreted=record.interpreted.get(field.id),
                classified=record.classified.get(field.id),
            )
            for field in selected
        ]
        from app.models.common import GuidanceSource

        return GuidanceBundleResponse(
            document_id=document_id,
            bundles=bundles,
            languages=languages,
            llm_used=any(item.source == GuidanceSource.GENERAL_AI for item in bundles),
        )

    def _ready(self, document_id: str) -> DocumentRecord:
        record = self.get(document_id)
        if record.status != DocumentStatus.READY:
            raise conflict("not_ready", record.error_message or "The form is still being prepared.")
        return record

    def _prepare_pages(self, record: DocumentRecord) -> list[Path]:
        source = Path(record.original_path)
        if record.mime_type == "application/pdf":
            destination = self.settings.processed_dir / record.id / "rendered"
            return self.pdf_service.render_pages(source, destination, self.settings.max_pdf_pages)
        return [source]

    def _sniff(self, payload: bytes, content_type: str | None, filename: str | None) -> tuple[str, str]:
        header = payload[:16]
        if header.startswith(b"%PDF"):
            return ".pdf", "application/pdf"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png", "image/png"
        if header.startswith(b"\xff\xd8\xff"):
            return ".jpg", "image/jpeg"
        if header.startswith(b"RIFF") and payload[8:12] == b"WEBP":
            return ".webp", "image/webp"
        raise bad_request(
            "unsupported_type",
            "Please upload a PNG, JPG, JPEG, WEBP, or PDF form.",
            {"filename": Path(filename or "file").name, "content_type": content_type or ""},
        )
