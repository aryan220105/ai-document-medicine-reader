from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models.common import DocumentStatus, ProcessingStage
from app.models.document import DocumentRecord

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.settings.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
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

    def save(self, record: DocumentRecord) -> None:
        record.updated_at = datetime.utcnow()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (record.id, record.model_dump_json(), record.created_at.isoformat(), record.updated_at.isoformat()),
            )
            connection.commit()

    def get(self, document_id: str) -> DocumentRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT payload FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None:
            return None
        return DocumentRecord.model_validate_json(row["payload"])

    def delete(self, document_id: str) -> DocumentRecord | None:
        record = self.get(document_id)
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            connection.commit()
        return record

    def update_stage(self, document_id: str, stage: ProcessingStage) -> DocumentRecord | None:
        record = self.get(document_id)
        if record is None:
            return None
        record.stage = stage
        record.status = DocumentStatus.READY if stage == ProcessingStage.READY else (
            DocumentStatus.FAILED if stage == ProcessingStage.FAILED else DocumentStatus.PROCESSING
        )
        self.save(record)
        return record

    def unlink(self, path: str | None) -> None:
        if not path:
            return
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete %s", path)
