from dataclasses import dataclass

from app.config import Settings, get_settings
from app.providers.embeddings.hashing import HashingEmbeddingProvider
from app.providers.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from app.providers.llm.disabled import DisabledLLMProvider
from app.providers.llm.groq_provider import GroqProvider
from app.providers.ocr.tesseract import TesseractOCRProvider
from app.repositories.document_repository import DocumentRepository
from app.repositories.field_dictionary_repository import FieldDictionaryRepository
from app.repositories.form_knowledge_repository import FormKnowledgeRepository
from app.repositories.vector_repository import VectorRepository
from app.services.document_service import DocumentService
from app.services.field_detection_service import FieldDetectionService
from app.services.field_assembly_service import FieldAssemblyService
from app.services.field_semantics_service import FieldSemanticsService
from app.services.form_interpretation_service import FormInterpretationService
from app.services.page_structure_service import PageStructureService
from app.services.rate_limit_service import RateLimiter
from app.services.form_identification_service import FormIdentificationService
from app.services.guidance_service import GuidanceService
from app.services.image_service import ImageService
from app.services.label_association_service import LabelAssociationService
from app.services.llm_service import LLMService
from app.services.ocr_service import OCRService
from app.services.pdf_service import PdfService
from app.services.preview_service import PreviewService
from app.services.retrieval_service import RetrievalService
from app.services.storage_service import StorageService
from app.services.translation_service import TranslationService
from app.services.validation_service import ValidationService


@dataclass
class AppContainer:
    settings: Settings
    documents: DocumentRepository
    knowledge: FormKnowledgeRepository
    dictionary: FieldDictionaryRepository
    semantics: FieldSemanticsService
    interpreter: FormInterpretationService
    rate_limiter: RateLimiter
    vectors: VectorRepository
    ocr_service: OCRService
    llm_service: LLMService
    retrieval: RetrievalService
    document_service: DocumentService


def build_container(settings: Settings | None = None) -> AppContainer:
    settings = settings or get_settings()
    storage = StorageService(settings)
    documents = DocumentRepository(settings)
    knowledge = FormKnowledgeRepository(settings)
    dictionary = FieldDictionaryRepository(settings)
    semantics = FieldSemanticsService(dictionary)
    embeddings = (
        HashingEmbeddingProvider()
        if settings.use_light_embeddings
        else SentenceTransformerEmbeddings(settings.embedding_model)
    )
    vectors = VectorRepository(settings, embeddings)  # type: ignore[arg-type]
    retrieval = RetrievalService(knowledge, vectors, dictionary)
    ocr_service = OCRService(TesseractOCRProvider(settings))
    provider = (
        GroqProvider(settings.llm_api_keys(), settings.llm_models(), settings.groq_base_url, settings.groq_timeout_seconds)
        if settings.llm_configured
        else DisabledLLMProvider()
    )
    llm_service = LLMService(provider)
    interpreter = FormInterpretationService(
        provider if settings.llm_configured else None,
        dictionary=dictionary,
        classify_batch=settings.interpreter_classify_batch,
        describe_batch=settings.interpreter_describe_batch,
        web_search_model=settings.groq_web_search_model if settings.web_context_configured else "",
    )
    rate_limiter = RateLimiter(settings.upload_rate_limit, settings.upload_rate_window_seconds)
    translation = TranslationService()
    guidance = GuidanceService(
        knowledge=knowledge,
        dictionary=dictionary,
        semantics=semantics,
        retrieval=retrieval,
        llm=llm_service,
        translation=translation,
        common_threshold=0.7,
        retrieval_threshold=settings.retrieval_min_score,
    )
    document_service = DocumentService(
        settings=settings,
        storage=storage,
        documents=documents,
        image_service=ImageService(),
        pdf_service=PdfService(),
        ocr_service=ocr_service,
        field_detection=FieldDetectionService(settings),
        label_association=LabelAssociationService(semantics),
        form_identification=FormIdentificationService(knowledge, settings),
        page_structure=PageStructureService(),
        field_assembly=FieldAssemblyService(),
        interpreter=interpreter,
        semantics=semantics,
        guidance=guidance,
        preview=PreviewService(settings, PdfService()),
        validation=ValidationService(translation),
        llm_configured=settings.llm_configured,
    )
    return AppContainer(
        settings=settings,
        documents=documents,
        knowledge=knowledge,
        dictionary=dictionary,
        semantics=semantics,
        interpreter=interpreter,
        rate_limiter=rate_limiter,
        vectors=vectors,
        ocr_service=ocr_service,
        llm_service=llm_service,
        retrieval=retrieval,
        document_service=document_service,
    )
