from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.api.errors import bad_request, conflict, not_found
from app.config import Settings
from app.models.common import DocumentCategory, DocumentStatus, Language, ProcessingStage
from app.models.document import DocumentPage, DocumentRecord, DocumentResponse
from app.models.fields import DetectedField, FieldAnswer, ValidationResult
from app.models.ocr import OCRResult
from app.models.guidance import AskRequest, AskResponse, FieldGuidance, GuidanceRequest
from app.models.preview import PreviewRequest, PreviewResult
from app.repositories.document_repository import DocumentRepository
from app.services.field_detection_service import FieldDetectionService
from app.services.form_identification_service import FormIdentificationService
from app.services.guidance_service import GuidanceService
from app.services.image_service import ImageService
from app.services.label_association_service import LabelAssociationService
from app.services.ocr_service import OCRService
from app.services.pdf_service import PdfService
from app.services.preview_service import PreviewService
from app.services.storage_service import StorageService
from app.services.validation_service import ValidationService

logger = logging.getLogger(__name__)

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
        self.guidance = guidance
        self.preview = preview
        self.validation = validation
        self.llm_configured = llm_configured

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
                ocr_pages.append(ocr)
                self.documents.update_stage(document_id, ProcessingStage.DETECTING_FIELDS)
                detected = self.field_detection.detect(preprocess.processed_path, index)
                associated = self.label_association.associate(detected, ocr)
                fields.extend(associated)
            if not any(page.full_text.strip() for page in ocr_pages):
                raise RuntimeError("No useful printed text could be read from this form.")
            self.documents.update_stage(document_id, ProcessingStage.MATCHING_FORM)
            match = self.form_identification.match(ocr_pages, fields, record.category)
            if match.form_id:
                for field in fields:
                    found = self.guidance.knowledge.find_field(match.form_id, [field.label], Language.ENGLISH)
                    if found:
                        field.known_field_id = found["field"]["field_id"]
            record.pages = pages
            record.ocr = ocr_pages
            record.fields = fields
            record.form_match = match
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
        return self.guidance.for_field(field, request, record.form_match.form_id, record.ocr)

    def ask(self, document_id: str, request: AskRequest) -> AskResponse:
        record = self._ready(document_id)
        field = self.field(record, request.field_id) if request.field_id else record.fields[0]
        if request.allow_external_ai and not self.llm_configured:
            request.allow_external_ai = False
        return self.guidance.ask(field, request, record.form_match.form_id, record.ocr)

    def validate_answer(self, document_id: str, answer: FieldAnswer) -> ValidationResult:
        record = self._ready(document_id)
        return self.validation.validate(self.field(record, answer.field_id), answer)

    def create_preview(self, document_id: str, request: PreviewRequest) -> PreviewResult:
        record = self._ready(document_id)
        overflow = []
        for answer in request.answers:
            result = self.validation.validate(self.field(record, answer.field_id), answer)
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
            created_at=record.created_at,
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
