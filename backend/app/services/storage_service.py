from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.models.common import DocumentStatus, DocumentType, ProcessingStage
from app.models.document import DetectedField, DocumentRecord
from app.models.ocr import OCRResult

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.settings.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def create_pending(
        self,
        *,
        original_filename: str,
        original_path: str,
        mime_type: str,
    ) -> DocumentRecord:
        record = DocumentRecord(
            id=str(uuid4()),
            original_filename=original_filename,
            original_path=original_path,
            mime_type=mime_type,
        )
        self.save(record)
        return record

    def save(self, record: DocumentRecord) -> None:
        record.updated_at = datetime.utcnow()
        payload = record.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (
                    record.id,
                    payload,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
            connection.commit()

    def get(self, document_id: str) -> DocumentRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentRecord.model_validate_json(row["payload"])

    def delete(self, document_id: str) -> DocumentRecord | None:
        record = self.get(document_id)
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            connection.commit()
        if record:
            self._unlink(record.original_path)
            if record.processed_path:
                self._unlink(record.processed_path)
        return record

    def update_stage(self, document_id: str, stage: ProcessingStage) -> DocumentRecord | None:
        record = self.get(document_id)
        if record is None:
            return None
        record.stage = stage
        if stage == ProcessingStage.READY:
            record.status = DocumentStatus.READY
        elif stage == ProcessingStage.FAILED:
            record.status = DocumentStatus.FAILED
        else:
            record.status = DocumentStatus.PROCESSING
        self.save(record)
        return record

    def store_processed(
        self,
        document_id: str,
        *,
        processed_path: str,
        detection_succeeded: bool,
        ocr: OCRResult,
        fields: list[DetectedField],
        document_type: DocumentType,
    ) -> DocumentRecord:
        record = self.get(document_id)
        if record is None:
            raise KeyError(document_id)
        record.processed_path = processed_path
        record.detection_succeeded = detection_succeeded
        record.ocr = ocr
        record.fields = fields
        record.document_type = document_type
        record.stage = ProcessingStage.READY
        record.status = DocumentStatus.READY
        record.error_message = None
        self.save(record)
        return record

    def mark_failed(self, document_id: str, message: str) -> DocumentRecord | None:
        record = self.get(document_id)
        if record is None:
            return None
        record.status = DocumentStatus.FAILED
        record.stage = ProcessingStage.FAILED
        record.error_message = message
        self.save(record)
        return record

    @staticmethod
    def _unlink(path: str) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete file %s", path)
