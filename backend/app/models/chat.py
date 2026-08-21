from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import BoundingBox, Language


class QuestionIntent(str, Enum):
    SUMMARIZE = "summarize"
    FIND_EXPIRY = "find_expiry"
    FIND_DOSAGE = "find_dosage"
    FIND_AMOUNT = "find_amount"
    FIND_DUE_DATE = "find_due_date"
    FIND_ACCOUNT_NUMBER = "find_account_number"
    FIND_REFERENCE_NUMBER = "find_reference_number"
    FIND_MEDICINE_NAME = "find_medicine_name"
    FIND_STRENGTH = "find_strength"
    FIND_BATCH = "find_batch"
    FIND_MFG = "find_mfg"
    FIND_WARNING = "find_warning"
    FOOD_INTERACTION = "food_interaction"
    SIDE_EFFECTS = "side_effects"
    TRANSLATE = "translate"
    EXPLAIN_SIMPLY = "explain_simply"
    VISUAL_LOCATION = "visual_location"
    GENERAL_QUESTION = "general_question"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    language: Language = Language.ENGLISH
    easy_read: bool = False


class ChatResponse(BaseModel):
    answer: str
    document_sources: list[str] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)
    highlights: list[BoundingBox] = Field(default_factory=list)
    confidence: float = 0.0
    intent: QuestionIntent = QuestionIntent.GENERAL_QUESTION
    llm_used: bool = False
    llm_unavailable: bool = False


class LLMStructuredOutput(BaseModel):
    answer: str
    document_evidence: list[str] = Field(default_factory=list)
    supplemental_evidence: list[str] = Field(default_factory=list)
    highlight_phrase: str | None = None
    confidence: float = 0.5
