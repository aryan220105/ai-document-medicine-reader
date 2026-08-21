from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import Settings
from app.models.common import DocumentType, ProcessingStage, confidence_level
from app.models.document import DocumentRecord, DocumentResponse
from app.services.classification_service import ClassificationService
from app.services.extraction_service import ExtractionService
from app.services.image_service import ImageService
from app.services.ocr_service import OCRService
from app.services.rag_service import RAGService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}


class DocumentService:
    def __init__(
        self,
        settings: Settings,
        storage: StorageService,
        image_service: ImageService,
        ocr_service: OCRService,
        extraction_service: ExtractionService,
        classification_service: ClassificationService,
        rag_service: RAGService,
        llm_configured: bool,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.image_service = image_service
        self.ocr_service = ocr_service
        self.extraction_service = extraction_service
        self.classification_service = classification_service
        self.rag_service = rag_service
        self.llm_configured = llm_configured

    async def create_from_upload(self, upload: UploadFile) -> DocumentRecord:
        content_type = (upload.content_type or "").lower()
        if content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Please upload a PNG, JPG, JPEG, or WEBP image.",
            )
        payload = await upload.read()
        if not payload:
            raise HTTPException(status_code=400, detail="The uploaded file was empty.")
        if len(payload) > self.settings.max_upload_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Please upload an image smaller than {self.settings.max_upload_mb} MB.",
            )
        suffix = ALLOWED_TYPES[content_type]
        filename = f"{uuid4().hex}{suffix}"
        destination = self.settings.uploads_dir / filename
        destination.write_bytes(payload)
        original_name = Path(upload.filename or "document").name
        record = self.storage.create_pending(
            original_filename=original_name,
            original_path=str(destination),
            mime_type=content_type,
        )
        logger.info("Stored upload document_id=%s stage=%s", record.id, record.stage.value)
        return record

    def process(self, document_id: str) -> DocumentRecord:
        record = self.storage.get(document_id)
        if record is None:
            raise KeyError(document_id)
        try:
            if not self.ocr_service.available():
                raise RuntimeError(
                    "Tesseract OCR is not installed on this machine. Install Tesseract and try again."
                )
            self.storage.update_stage(document_id, ProcessingStage.DETECTING)
            processed_name = f"{document_id}.png"
            processed_path = str(self.settings.processed_dir / processed_name)
            self.storage.update_stage(document_id, ProcessingStage.ENHANCING)
            preprocess = self.image_service.preprocess(record.original_path, processed_path)
            self.storage.update_stage(document_id, ProcessingStage.OCR)
            ocr = self.ocr_service.extract(preprocess.processed_path)
            if not ocr.has_useful_text:
                ocr = self.ocr_service.extract(record.original_path)
            self.storage.update_stage(document_id, ProcessingStage.EXTRACTING)
            fields = self.extraction_service.extract(ocr)
            document_type = self.classification_service.classify(ocr)
            self.storage.update_stage(document_id, ProcessingStage.INDEXING)
            try:
                self.rag_service.index_document(document_id, ocr)
            except Exception:
                logger.exception("Document indexing failed for %s", document_id)
            stored = self.storage.store_processed(
                document_id,
                processed_path=preprocess.processed_path,
                detection_succeeded=preprocess.detection_succeeded,
                ocr=ocr,
                fields=fields,
                document_type=document_type,
            )
            logger.info(
                "Processed document_id=%s type=%s ocr_words=%s",
                document_id,
                document_type.value,
                len(ocr.words),
            )
            return stored
        except Exception as exc:
            message = str(exc) or "Document processing failed."
            if "Tesseract" in message:
                friendly = message
            else:
                friendly = "I couldn't process this image. Try a clearer photo with better lighting."
            logger.exception("Processing failed for document_id=%s", document_id)
            failed = self.storage.mark_failed(document_id, friendly)
            return failed or record

    def get(self, document_id: str) -> DocumentRecord:
        record = self.storage.get(document_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        return record

    def delete(self, document_id: str) -> None:
        record = self.storage.delete(document_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        try:
            self.rag_service.delete_document(document_id)
        except Exception:
            logger.warning("Vector cleanup failed for %s", document_id)

    def override_type(self, document_id: str, document_type: DocumentType) -> DocumentRecord:
        record = self.get(document_id)
        record.user_document_type = document_type
        self.storage.save(record)
        return record

    def to_response(self, record: DocumentRecord) -> DocumentResponse:
        ocr = record.ocr
        return DocumentResponse(
            id=record.id,
            original_filename=record.original_filename,
            status=record.status,
            stage=record.stage,
            document_type=record.effective_type,
            detection_succeeded=record.detection_succeeded,
            average_confidence=ocr.average_confidence if ocr else 0.0,
            confidence_level=confidence_level(ocr.average_confidence).value if ocr else "low",
            ocr_text=ocr.full_text if ocr else "",
            fields=record.fields,
            error_message=record.error_message,
            original_image_url=f"/api/documents/{record.id}/image/original",
            processed_image_url=f"/api/documents/{record.id}/image/processed" if record.processed_path else None,
            llm_configured=self.llm_configured,
            created_at=record.created_at,
        )
