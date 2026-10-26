"""Label-pattern heuristics.

These do not identify *which* field a label is. They recognise the shape of the answer a
label asks for, so a completely unrecognised field still gets an honest description, a
sensible input type, and a validation rule instead of a blank 'unavailable'. Every
heuristic description says plainly that it is inferred from the printed wording.
"""

from __future__ import annotations

from . import t

INFERRED_NOTE = t(
    "This wording is not in FormSathi's dictionary, so the description below is inferred from the printed label. Check the form's own instructions before you rely on it.",
    "यह शब्दावली FormSathi के शब्दकोश में नहीं है, इसलिए नीचे दिया विवरण छपे लेबल से अनुमानित है। इस पर भरोसा करने से पहले फ़ॉर्म के निर्देश देख लें।",
    "ಈ ಪದಪ್ರಯೋಗ FormSathi ನ ನಿಘಂಟಿನಲ್ಲಿ ಇಲ್ಲ, ಆದ್ದರಿಂದ ಕೆಳಗಿನ ವಿವರಣೆ ಮುದ್ರಿತ ಲೇಬಲ್‌ನಿಂದ ಊಹಿಸಿದ್ದು. ಇದನ್ನು ನಂಬುವ ಮೊದಲು ಅರ್ಜಿಯ ಸೂಚನೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.",
    "یہ الفاظ FormSathi کی ڈکشنری میں نہیں ہیں، اس لیے نیچے دی گئی تفصیل چھپے لیبل سے اندازہ لگائی گئی ہے۔ اس پر بھروسہ کرنے سے پہلے فارم کی ہدایات دیکھ لیں۔",
)


def pattern(
    pattern_id: str,
    field_type: str,
    markers: dict[str, list[str]],
    what_to_enter: dict[str, str],
    validation: dict | None = None,
    format_hint: dict[str, str] | None = None,
    weight: float = 1.0,
) -> dict:
    return {
        "id": pattern_id,
        "type": field_type,
        "markers": markers,
        "what_to_enter": what_to_enter,
        "validation": validation or {"kind": "non_empty"},
        "format_hint": format_hint or {},
        "weight": weight,
    }


PATTERNS = [
    pattern(
        "name_like",
        "text",
        markers={
            "en": ["name of", "name"],
            "hi": ["नाम"],
            "kn": ["ಹೆಸರು"],
            "ur": ["نام"],
        },
        what_to_enter=t(
            "The printed label asks for a name. Write the full name of the person or body it names, spelled as it appears on the matching document.",
            "छपा हुआ लेबल एक नाम मांग रहा है। जिस व्यक्ति या संस्था का नाम मांगा गया है उसका पूरा नाम उसी वर्तनी में लिखें जैसा संबंधित दस्तावेज़ पर है।",
            "ಮುದ್ರಿತ ಲೇಬಲ್ ಹೆಸರನ್ನು ಕೇಳುತ್ತಿದೆ. ಅದು ಹೇಳುವ ವ್ಯಕ್ತಿ ಅಥವಾ ಸಂಸ್ಥೆಯ ಪೂರ್ಣ ಹೆಸರನ್ನು ಸಂಬಂಧಿತ ದಾಖಲೆಯಲ್ಲಿರುವ ಕಾಗುಣಿತದಲ್ಲೇ ಬರೆಯಿರಿ.",
            "چھپا ہوا لیبل ایک نام مانگ رہا ہے۔ جس شخص یا ادارے کا نام مانگا گیا ہے اس کا پورا نام اسی ہجے میں لکھیں جیسا متعلقہ دستاویز پر ہے۔",
        ),
        validation={"kind": "person_name", "max_length": 100},
        weight=0.9,
    ),
    pattern(
        "number_like",
        "text",
        markers={
            "en": ["number", "no.", "no", "code", "id"],
            "hi": ["संख्या", "नंबर", "कोड"],
            "kn": ["ಸಂಖ್ಯೆ", "ನಂಬರ್", "ಕೋಡ್"],
            "ur": ["نمبر", "کوڈ", "عدد"],
        },
        what_to_enter=t(
            "The printed label asks for a number or code. Copy it exactly from the card, receipt, or notice it belongs to, character by character.",
            "छपा हुआ लेबल एक संख्या या कोड मांग रहा है। इसे संबंधित कार्ड, रसीद या सूचना से अक्षर दर अक्षर ठीक वैसा ही लिखें।",
            "ಮುದ್ರಿತ ಲೇಬಲ್ ಸಂಖ್ಯೆ ಅಥವಾ ಸಂಕೇತವನ್ನು ಕೇಳುತ್ತಿದೆ. ಸಂಬಂಧಿತ ಕಾರ್ಡ್, ರಸೀದಿ ಅಥವಾ ಸೂಚನೆಯಿಂದ ಅಕ್ಷರಶಃ ನಕಲಿಸಿ.",
            "چھپا ہوا لیبل ایک نمبر یا کوڈ مانگ رہا ہے۔ اسے متعلقہ کارڈ، رسید یا نوٹس سے حرف بہ حرف بالکل ویسا ہی لکھیں۔",
        ),
        validation={"kind": "alphanumeric", "max_length": 32},
    ),
    pattern(
        "date_like",
        "date",
        markers={
            "en": ["date", "dated", "dd/mm/yyyy", "day month year", "from", "to", "valid till", "expiry"],
            "hi": ["दिनांक", "तारीख", "तिथि", "से", "तक", "वैध"],
            "kn": ["ದಿನಾಂಕ", "ತಾರೀಖು", "ರಿಂದ", "ವರೆಗೆ", "ಮಾನ್ಯ"],
            "ur": ["تاریخ", "سے", "تک", "میعاد"],
        },
        what_to_enter=t(
            "The printed label asks for a date. Write the day, month, and year in the order the form prints beside the box.",
            "छपा हुआ लेबल एक तिथि मांग रहा है। खाने के पास फ़ॉर्म पर छपे क्रम में दिन, महीना और वर्ष लिखें।",
            "ಮುದ್ರಿತ ಲೇಬಲ್ ದಿನಾಂಕವನ್ನು ಕೇಳುತ್ತಿದೆ. ಚೌಕದ ಪಕ್ಕದಲ್ಲಿ ಅರ್ಜಿ ಮುದ್ರಿಸಿರುವ ಕ್ರಮದಲ್ಲಿ ದಿನ, ತಿಂಗಳು ಮತ್ತು ವರ್ಷ ಬರೆಯಿರಿ.",
            "چھپا ہوا لیبل ایک تاریخ مانگ رہا ہے۔ خانے کے پاس فارم پر چھپی ترتیب میں دن، مہینہ اور سال لکھیں۔",
        ),
        validation={"kind": "date", "format": "DD/MM/YYYY"},
        format_hint=t("DD/MM/YYYY", "DD/MM/YYYY", "DD/MM/YYYY", "DD/MM/YYYY"),
    ),
    pattern(
        "amount_like",
        "text",
        markers={
            "en": ["amount", "rupees", "rs.", "rs", "inr", "fee", "charges", "premium", "salary", "income", "cost", "price"],
            "hi": ["राशि", "रुपये", "शुल्क", "वेतन", "आय", "मूल्य"],
            "kn": ["ಮೊತ್ತ", "ರೂಪಾಯಿ", "ಶುಲ್ಕ", "ವೇತನ", "ಆದಾಯ", "ಬೆಲೆ"],
            "ur": ["رقم", "روپے", "فیس", "تنخواہ", "آمدنی", "قیمت"],
        },
        what_to_enter=t(
            "The printed label asks for a money amount. Write it in figures and check whether the form also wants it in words.",
            "छपा हुआ लेबल एक धनराशि मांग रहा है। इसे अंकों में लिखें और देख लें कि फ़ॉर्म इसे शब्दों में भी मांग रहा है या नहीं।",
            "ಮುದ್ರಿತ ಲೇಬಲ್ ಹಣದ ಮೊತ್ತವನ್ನು ಕೇಳುತ್ತಿದೆ. ಅಂಕಿಗಳಲ್ಲಿ ಬರೆಯಿರಿ ಮತ್ತು ಅರ್ಜಿ ಅದನ್ನು ಅಕ್ಷರಗಳಲ್ಲೂ ಕೇಳುತ್ತಿದೆಯೇ ಎಂದು ಪರಿಶೀಲಿಸಿ.",
            "چھپا ہوا لیبل ایک رقم مانگ رہا ہے۔ اسے ہندسوں میں لکھیں اور دیکھ لیں کہ فارم اسے الفاظ میں بھی مانگ رہا ہے یا نہیں۔",
        ),
        validation={"kind": "amount"},
    ),
    pattern(
        "address_like",
        "multiline",
        markers={
            "en": ["address", "street", "locality", "door no", "house no", "premises"],
            "hi": ["पता", "गली", "मोहल्ला", "मकान"],
            "kn": ["ವಿಳಾಸ", "ರಸ್ತೆ", "ಬಡಾವಣೆ", "ಮನೆ"],
            "ur": ["پتہ", "گلی", "محلہ", "مکان"],
        },
        what_to_enter=t(
            "The printed label asks for a place or address. Write it over as many lines as the box allows, starting with the house or door number.",
            "छपा हुआ लेबल कोई स्थान या पता मांग रहा है। खाने में जितनी पंक्तियाँ हैं उतने में, मकान या द्वार संख्या से शुरू करके लिखें।",
            "ಮುದ್ರಿತ ಲೇಬಲ್ ಸ್ಥಳ ಅಥವಾ ವಿಳಾಸವನ್ನು ಕೇಳುತ್ತಿದೆ. ಚೌಕದಲ್ಲಿ ಇರುವಷ್ಟು ಸಾಲುಗಳಲ್ಲಿ, ಮನೆ ಅಥವಾ ಬಾಗಿಲು ಸಂಖ್ಯೆಯಿಂದ ಆರಂಭಿಸಿ ಬರೆಯಿರಿ.",
            "چھپا ہوا لیبل کوئی مقام یا پتہ مانگ رہا ہے۔ خانے میں جتنی سطریں ہیں اتنی میں، مکان یا دروازہ نمبر سے شروع کر کے لکھیں۔",
        ),
        validation={"kind": "multiline", "max_length": 240},
    ),
    pattern(
        "choice_like",
        "radio",
        markers={
            "en": ["yes no", "tick", "select", "choose", "whether", "type of", "status"],
            "hi": ["हाँ नहीं", "निशान", "चुनें", "क्या", "प्रकार", "स्थिति"],
            "kn": ["ಹೌದು ಇಲ್ಲ", "ಗುರುತು", "ಆಯ್ಕೆ", "ಪ್ರಕಾರ", "ಸ್ಥಿತಿ"],
            "ur": ["ہاں نہیں", "نشان", "منتخب", "قسم", "حالت"],
        },
        what_to_enter=t(
            "The printed label offers a choice. Tick only the option that is true for you, using the choices printed on the form.",
            "छपा हुआ लेबल एक विकल्प देता है। फ़ॉर्म पर छपे विकल्पों में से जो आपके लिए सत्य है केवल उसी पर निशान लगाएँ।",
            "ಮುದ್ರಿತ ಲೇಬಲ್ ಆಯ್ಕೆಯನ್ನು ನೀಡುತ್ತಿದೆ. ಅರ್ಜಿಯಲ್ಲಿ ಮುದ್ರಿಸಿರುವ ಆಯ್ಕೆಗಳಲ್ಲಿ ನಿಮಗೆ ಸತ್ಯವಾದ ಒಂದಕ್ಕೆ ಮಾತ್ರ ಗುರುತು ಹಾಕಿ.",
            "چھپا ہوا لیبل ایک اختیار دیتا ہے۔ فارم پر چھپے اختیارات میں سے جو آپ کے لیے سچ ہے صرف اسی پر نشان لگائیں۔",
        ),
        validation={"kind": "choice"},
    ),
    pattern(
        "office_use",
        "text",
        markers={
            "en": ["for office use", "office use only", "official use", "for departmental use"],
            "hi": ["कार्यालय उपयोग हेतु", "केवल कार्यालय उपयोग", "विभागीय उपयोग"],
            "kn": ["ಕಚೇರಿ ಬಳಕೆಗೆ", "ಕಚೇರಿ ಬಳಕೆ ಮಾತ್ರ", "ಇಲಾಖಾ ಬಳಕೆ"],
            "ur": ["دفتری استعمال کے لیے", "صرف دفتری استعمال"],
        },
        what_to_enter=t(
            "This block is marked for office use. Leave it empty; the office staff fill it in.",
            "यह खंड कार्यालय के उपयोग के लिए अंकित है। इसे खाली छोड़ दें; इसे कार्यालय कर्मी भरते हैं।",
            "ಈ ಭಾಗ ಕಚೇರಿ ಬಳಕೆಗೆ ಗುರುತಿಸಲಾಗಿದೆ. ಖಾಲಿ ಬಿಡಿ; ಕಚೇರಿ ಸಿಬ್ಬಂದಿ ಇದನ್ನು ಭರ್ತಿ ಮಾಡುತ್ತಾರೆ.",
            "یہ حصہ دفتری استعمال کے لیے مخصوص ہے۔ اسے خالی چھوڑ دیں؛ اسے دفتری عملہ بھرتا ہے۔",
        ),
        validation={"kind": "office_use", "optional": True},
        weight=1.3,
    ),
]
