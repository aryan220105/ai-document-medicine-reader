from __future__ import annotations

import re

from app.models.chat import QuestionIntent
from app.utils.text import fold


INTENT_KEYWORDS: list[tuple[QuestionIntent, tuple[str, ...]]] = [
    (QuestionIntent.EXPLAIN_SIMPLY, ("explain simply", "simple explanation", "explain this")),
    (QuestionIntent.SUMMARIZE, ("summarize", "summary", "what is this document")),
    (QuestionIntent.FIND_EXPIRY, ("expir", "exp date", "use before", "best before")),
    (QuestionIntent.FIND_MFG, ("mfg", "manufactur", "mfd")),
    (QuestionIntent.FIND_DOSAGE, ("dosage", "dose", "how should i take", "how to take")),
    (QuestionIntent.FIND_STRENGTH, ("strength", "how many mg", "mg printed")),
    (QuestionIntent.FIND_BATCH, ("batch", "lot number")),
    (QuestionIntent.FIND_AMOUNT, ("how much", "amount", "pay", "₹", "rupee", "total due", "bill amount")),
    (QuestionIntent.FIND_DUE_DATE, ("due date", "deadline", "last date", "pay by")),
    (QuestionIntent.FIND_ACCOUNT_NUMBER, ("account number", "consumer number", "a/c")),
    (QuestionIntent.FIND_REFERENCE_NUMBER, ("reference", "invoice number", "policy number", "bill number")),
    (QuestionIntent.FIND_MEDICINE_NAME, ("medicine name", "drug name", "what medicine", "product name")),
    (QuestionIntent.FIND_WARNING, ("warning", "caution", "storage", "store below")),
    (QuestionIntent.FOOD_INTERACTION, ("food", "empty stomach", "with food", "alcohol")),
    (QuestionIntent.SIDE_EFFECTS, ("side effect", "adverse")),
    (QuestionIntent.TRANSLATE, ("in hindi", "in kannada", "translate")),
]


LOCATION_RE = re.compile(r"\b(where|show|highlight|locate|point out|find on (the )?(image|label|document))\b", re.I)


class IntentService:
    def detect(self, question: str) -> tuple[QuestionIntent, bool]:
        text = fold(question)
        wants_location = bool(LOCATION_RE.search(question))
        for intent, keywords in INTENT_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                return intent, wants_location
        if wants_location:
            return QuestionIntent.VISUAL_LOCATION, True
        return QuestionIntent.GENERAL_QUESTION, False
