from __future__ import annotations

from app.models.chat import QuestionIntent
from app.models.common import DocumentType, Language
from app.models.document import DetectedField


FIELD_ANSWERS = {
    QuestionIntent.FIND_EXPIRY: {
        "type": "expiry_date",
        Language.ENGLISH: "The expiry date shown is {value}.",
        Language.HINDI: "लेबल पर दिख रही समाप्ति तिथि {value} है।",
        Language.KANNADA: "ತೋರಿಸಿರುವ ಅವಧಿ ಮುಗಿಯುವ ದಿನಾಂಕ {value}.",
        "missing_en": "I could not confidently find an expiry date on this image.",
    },
    QuestionIntent.FIND_DOSAGE: {
        "type": "dosage",
        Language.ENGLISH: 'The label says: "{value}". Please verify the printed label or prescription if the text is unclear.',
        Language.HINDI: 'लेबल पर लिखा है: "{value}"। यदि अस्पष्ट हो तो छपे हुए लेबल या पर्ची से जाँच करें।',
        Language.KANNADA: 'ಲೇಬಲ್‌ನಲ್ಲಿ ಬರೆದಿರುವುದು: "{value}". ಅಸ್ಪಷ್ಟವಿದ್ದರೆ ಮುದ್ರಿತ ಲೇಬಲ್ ಅಥವಾ ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್ ನೋಡಿ.',
        "missing_en": "I could not confidently find dosage instructions on this image.",
    },
    QuestionIntent.FIND_AMOUNT: {
        "type": "amount",
        Language.ENGLISH: "The bill amount shown is {value}.",
        Language.HINDI: "दस्तावेज़ में दिख रही राशि {value} है।",
        Language.KANNADA: "ತೋರಿಸಿರುವ ಬಿಲ್ ಮೊತ್ತ {value}.",
        "missing_en": "I could not confidently find a payment amount on this image.",
    },
    QuestionIntent.FIND_DUE_DATE: {
        "type": "due_date",
        Language.ENGLISH: "The due date shown is {value}.",
        Language.HINDI: "दस्तावेज़ में दिख रही अंतिम तिथि {value} है।",
        Language.KANNADA: "ತೋರಿಸಿರುವ ಕೊನೆಯ ದಿನಾಂಕ {value}.",
        "missing_en": "I could not confidently find a due date on this image.",
    },
    QuestionIntent.FIND_ACCOUNT_NUMBER: {
        "type": "account_number",
        Language.ENGLISH: "The account/reference number shown is {value}.",
        Language.HINDI: "दस्तावेज़ में दिख रहा खाता/संदर्भ संख्या {value} है।",
        Language.KANNADA: "ತೋರಿಸಿರುವ ಖಾತೆ/ಉಲ್ಲೇಖ ಸಂಖ್ಯೆ {value}.",
        "missing_en": "I could not confidently find an account number on this image.",
    },
    QuestionIntent.FIND_REFERENCE_NUMBER: {
        "type": "reference_number",
        Language.ENGLISH: "The reference number shown is {value}.",
        Language.HINDI: "दस्तावेज़ में दिख रहा संदर्भ संख्या {value} है।",
        Language.KANNADA: "ತೋರಿಸಿರುವ ಉಲ್ಲೇಖ ಸಂಖ್ಯೆ {value}.",
        "missing_en": "I could not confidently find a reference number on this image.",
    },
    QuestionIntent.FIND_MEDICINE_NAME: {
        "type": "medicine_name",
        Language.ENGLISH: "The medicine/product name appears to be {value}.",
        Language.HINDI: "दवा/उत्पाद का नाम {value} दिखाई देता है।",
        Language.KANNADA: "ಔಷಧ/ಉತ್ಪನ್ನದ ಹೆಸರು {value} ಎಂದು ಕಾಣುತ್ತದೆ.",
        "missing_en": "I could not confidently find a medicine name on this image.",
    },
    QuestionIntent.FIND_STRENGTH: {
        "type": "strength",
        Language.ENGLISH: "The printed strength is {value}.",
        Language.HINDI: "छपी हुई क्षमता {value} है।",
        Language.KANNADA: "ಮುದ್ರಿತ ಸಾಮರ್ಥ್ಯ {value}.",
        "missing_en": "I could not confidently find a strength on this image.",
    },
    QuestionIntent.FIND_BATCH: {
        "type": "batch_number",
        Language.ENGLISH: "The batch number shown is {value}.",
        Language.HINDI: "बैच संख्या {value} दिखाई देती है।",
        Language.KANNADA: "ಬ್ಯಾಚ್ ಸಂಖ್ಯೆ {value}.",
        "missing_en": "I could not confidently find a batch number on this image.",
    },
    QuestionIntent.FIND_MFG: {
        "type": "manufacturing_date",
        Language.ENGLISH: "The manufacturing date shown is {value}.",
        Language.HINDI: "निर्माण तिथि {value} दिखाई देती है।",
        Language.KANNADA: "ತಯಾರಿಕೆ ದಿನಾಂಕ {value}.",
        "missing_en": "I could not confidently find a manufacturing date on this image.",
    },
    QuestionIntent.FIND_WARNING: {
        "type": "warnings",
        Language.ENGLISH: "The printed warning/storage text is: {value}",
        Language.HINDI: "छपा हुआ चेतावनी/भंडारण पाठ: {value}",
        Language.KANNADA: "ಮುದ್ರಿತ ಎಚ್ಚರಿಕೆ/ಸಂಗ್ರಹ ಪಠ್ಯ: {value}",
        "missing_en": "I could not confidently find a warning on this image.",
    },
}

MISSING_TRANSLATIONS = {
    Language.HINDI: "इस चित्र पर यह जानकारी विश्वसनीय रूप से नहीं मिली।",
    Language.KANNADA: "ಈ ಚಿತ್ರದಲ್ಲಿ ಈ ಮಾಹಿತಿಯನ್ನು ವಿಶ್ವಾಸದಿಂದ ಕಂಡುಹಿಡಿಯಲಾಗಲಿಲ್ಲ.",
}

LLM_UNAVAILABLE = {
    Language.ENGLISH: (
        "AI explanation is currently unavailable because no LLM API key is configured. "
        "You can still view the OCR results and detected information."
    ),
    Language.HINDI: (
        "AI व्याख्या उपलब्ध नहीं है क्योंकि LLM API कुंजी सेट नहीं है। "
        "आप OCR पाठ और मिली जानकारी अभी भी देख सकते हैं।"
    ),
    Language.KANNADA: (
        "LLM API ಕೀ ಇಲ್ಲದ ಕಾರಣ AI ವಿವರಣೆ ಲಭ್ಯವಿಲ್ಲ. "
        "OCR ಪಠ್ಯ ಮತ್ತು ಪತ್ತೆಯಾದ ಮಾಹಿತಿಯನ್ನು ನೀವು ಇನ್ನೂ ನೋಡಬಹುದು."
    ),
}


def field_by_type(fields: list[DetectedField], field_type: str) -> DetectedField | None:
    for field in fields:
        if field.field_type == field_type:
            return field
    return None


def simple_explanation(fields: list[DetectedField], document_type: DocumentType, language: Language) -> str:
    def value(field_type: str) -> str | None:
        field = field_by_type(fields, field_type)
        return field.value if field else None

    if document_type == DocumentType.MEDICINE_LABEL:
        lines = [
            f"This appears to be a medicine label for {value('medicine_name') or 'a product printed on the pack'}.",
            f"Printed strength: {value('strength')}." if value("strength") else "No strength was confidently read.",
            f"Printed dosage/instructions: {value('dosage')}." if value("dosage") else "No dosage line was confidently read.",
            f"Printed expiry: {value('expiry_date')}." if value("expiry_date") else "No expiry date was confidently read.",
            f"Printed warnings/storage: {value('warnings') or value('storage') or 'none clearly found'}.",
        ]
    else:
        lines = [
            f"This appears to be a {document_type.value.replace('_', ' ')}.",
            f"Important amount: {value('amount')}." if value("amount") else "No amount was confidently read.",
            f"Deadline/due date: {value('due_date')}." if value("due_date") else "No deadline was confidently read.",
            f"Account/reference: {value('account_number') or value('reference_number') or 'not clearly found'}.",
            "If a payment or deadline is printed, complete it using the values on the document.",
        ]
    english = " ".join(lines)
    if language == Language.HINDI:
        return "यह सार छपे हुए पाठ पर आधारित है। " + english
    if language == Language.KANNADA:
        return "ಈ ಸಾರಾಂಶ ಮುದ್ರಿತ ಪಠ್ಯವನ್ನು ಆಧರಿಸಿದೆ. " + english
    return english
