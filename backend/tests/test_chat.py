from datetime import datetime

import pytest

from app.models.chat import ChatRequest
from app.models.common import DocumentStatus, DocumentType, Language, ProcessingStage
from app.models.document import DocumentRecord
from app.providers.llm.openai_compatible import LLMUnavailableError
from app.services.answer_templates import LLM_UNAVAILABLE
from app.services.chat_service import ChatService
from app.services.extraction_service import ExtractionService
from app.services.highlight_service import HighlightService
from app.services.intent_service import IntentService
from tests.test_extraction import ocr_from_lines


class FakeDocuments:
    def __init__(self, record: DocumentRecord) -> None:
        self.record = record

    def get(self, document_id: str) -> DocumentRecord:
        return self.record


class DisabledLLM:
    configured = False

    async def generate_answer(self, **kwargs):
        raise LLMUnavailableError("LLM features require an API key.")


class SilentRAG:
    def retrieve_document(self, question: str, document_id: str, limit: int = 6):
        return []

    def retrieve_knowledge(self, question: str, limit: int = 4):
        return []


def medicine_record() -> DocumentRecord:
    ocr = ocr_from_lines(
        [
            "PARACETAMOL TABLETS",
            "500 mg",
            "Batch: ABC123",
            "EXP: DEC 2027",
            "Dosage: As directed by physician.",
        ]
    )
    return DocumentRecord(
        id="doc-1",
        original_filename="medicine.png",
        original_path="medicine.png",
        mime_type="image/png",
        status=DocumentStatus.READY,
        stage=ProcessingStage.READY,
        document_type=DocumentType.MEDICINE_LABEL,
        ocr=ocr,
        fields=ExtractionService().extract(ocr),
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_deterministic_expiry_without_llm() -> None:
    record = medicine_record()
    service = ChatService(FakeDocuments(record), IntentService(), HighlightService(), SilentRAG(), DisabledLLM())
    response = await service.ask("doc-1", ChatRequest(question="What is the expiry date?", language=Language.ENGLISH))
    assert "DEC 2027" in response.answer
    assert response.llm_used is False
    assert response.highlights


@pytest.mark.asyncio
async def test_missing_field_does_not_hallucinate() -> None:
    ocr = ocr_from_lines(["RANDOM NOTE", "HELLO WORLD DOCUMENT"])
    record = DocumentRecord(
        id="doc-2",
        original_filename="note.png",
        original_path="note.png",
        mime_type="image/png",
        status=DocumentStatus.READY,
        stage=ProcessingStage.READY,
        document_type=DocumentType.GENERAL_DOCUMENT,
        ocr=ocr,
        fields=[],
        created_at=datetime.utcnow(),
    )
    service = ChatService(FakeDocuments(record), IntentService(), HighlightService(), SilentRAG(), DisabledLLM())
    response = await service.ask("doc-2", ChatRequest(question="What is the expiry date?"))
    assert "could not confidently find" in response.answer.lower()
    assert "2029" not in response.answer


@pytest.mark.asyncio
async def test_llm_disabled_generative_question() -> None:
    record = medicine_record()
    service = ChatService(FakeDocuments(record), IntentService(), HighlightService(), SilentRAG(), DisabledLLM())
    response = await service.ask(
        "doc-1",
        ChatRequest(question="Explain the history of paracetamol in poetry"),
    )
    assert response.llm_unavailable is True
    assert "API key" in response.answer or response.answer == LLM_UNAVAILABLE[Language.ENGLISH]


def bill_record() -> DocumentRecord:
    ocr = ocr_from_lines(
        [
            "ELECTRICITY BILL",
            "Account Number: 12345678",
            "Bill Amount: Rs 2450",
            "Due Date: 25 September 2026",
        ]
    )
    return DocumentRecord(
        id="doc-bill",
        original_filename="bill.png",
        original_path="bill.png",
        mime_type="image/png",
        status=DocumentStatus.READY,
        stage=ProcessingStage.READY,
        document_type=DocumentType.ELECTRICITY_BILL,
        ocr=ocr,
        fields=ExtractionService().extract(ocr),
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_combined_amount_and_due_date() -> None:
    record = bill_record()
    service = ChatService(FakeDocuments(record), IntentService(), HighlightService(), SilentRAG(), DisabledLLM())
    response = await service.ask(
        "doc-bill",
        ChatRequest(question="How much do I need to pay? and Where is the due date?"),
    )
    assert "2450" in response.answer
    assert "2026" in response.answer
