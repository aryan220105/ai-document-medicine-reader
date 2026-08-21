from dataclasses import dataclass

from app.config import Settings, get_settings
from app.providers.llm.openai_compatible import OpenAICompatibleProvider
from app.providers.ocr.tesseract import TesseractOCRProvider
from app.services.chat_service import ChatService
from app.services.classification_service import ClassificationService
from app.services.document_service import DocumentService
from app.services.extraction_service import ExtractionService
from app.services.highlight_service import HighlightService
from app.services.image_service import ImageService
from app.services.intent_service import IntentService
from app.services.llm_service import LLMService
from app.services.ocr_service import OCRService
from app.services.rag_service import RAGService
from app.services.storage_service import StorageService


@dataclass
class AppContainer:
    settings: Settings
    storage: StorageService
    image_service: ImageService
    ocr_service: OCRService
    extraction_service: ExtractionService
    classification_service: ClassificationService
    rag_service: RAGService
    llm_service: LLMService
    document_service: DocumentService
    chat_service: ChatService


def build_container(settings: Settings | None = None) -> AppContainer:
    settings = settings or get_settings()
    storage = StorageService(settings)
    image_service = ImageService()
    ocr_service = OCRService(TesseractOCRProvider(settings))
    extraction_service = ExtractionService()
    classification_service = ClassificationService()
    rag_service = RAGService(settings)
    llm_provider = OpenAICompatibleProvider(
        api_keys=settings.llm_api_keys(),
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        fallback_models=settings.llm_fallback_models(),
    )
    llm_service = LLMService(settings, provider=llm_provider)
    document_service = DocumentService(
        settings=settings,
        storage=storage,
        image_service=image_service,
        ocr_service=ocr_service,
        extraction_service=extraction_service,
        classification_service=classification_service,
        rag_service=rag_service,
        llm_configured=llm_service.configured,
    )
    chat_service = ChatService(
        document_service=document_service,
        intent_service=IntentService(),
        highlight_service=HighlightService(),
        rag_service=rag_service,
        llm_service=llm_service,
    )
    return AppContainer(
        settings=settings,
        storage=storage,
        image_service=image_service,
        ocr_service=ocr_service,
        extraction_service=extraction_service,
        classification_service=classification_service,
        rag_service=rag_service,
        llm_service=llm_service,
        document_service=document_service,
        chat_service=chat_service,
    )
