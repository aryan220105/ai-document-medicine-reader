from __future__ import annotations

from app.models.common import Language

# Every message the backend can show a user, in all four supported languages. These are
# authored strings, not machine translations, and they describe only FormSathi's own
# behaviour -- never the content of an uploaded form.
MESSAGES: dict[str, dict[str, str]] = {
    "unavailable": {
        "en": "Guidance is unavailable for this field. Check the official printed instructions on the form.",
        "hi": "इस फ़ील्ड के लिए मार्गदर्शन उपलब्ध नहीं है। कृपया फ़ॉर्म पर छपे आधिकारिक निर्देश देखें।",
        "kn": "ಈ ಕ್ಷೇತ್ರಕ್ಕೆ ಮಾರ್ಗದರ್ಶನ ಲಭ್ಯವಿಲ್ಲ. ಅರ್ಜಿಯಲ್ಲಿ ಮುದ್ರಿತವಾದ ಅಧಿಕೃತ ಸೂಚನೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.",
        "ur": "اس خانے کے لیے رہنمائی دستیاب نہیں ہے۔ براہِ کرم فارم پر چھپی سرکاری ہدایات دیکھیں۔",
    },
    "unlabelled": {
        "en": "FormSathi found a blank space here but could not read a printed label next to it. Look at the form to see what belongs in this space.",
        "hi": "FormSathi को यहाँ एक रिक्त स्थान मिला, परंतु उसके पास छपा कोई लेबल पढ़ा नहीं जा सका। इस स्थान में क्या लिखना है यह जानने के लिए फ़ॉर्म देखें।",
        "kn": "FormSathi ಇಲ್ಲಿ ಖಾಲಿ ಜಾಗವನ್ನು ಕಂಡಿದೆ, ಆದರೆ ಅದರ ಪಕ್ಕದ ಮುದ್ರಿತ ಲೇಬಲ್ ಓದಲಾಗಲಿಲ್ಲ. ಈ ಜಾಗದಲ್ಲಿ ಏನು ಬರೆಯಬೇಕು ಎಂದು ಅರ್ಜಿಯನ್ನು ನೋಡಿ.",
        "ur": "FormSathi کو یہاں ایک خالی جگہ ملی، مگر اس کے پاس چھپا کوئی لیبل پڑھا نہیں جا سکا۔ اس جگہ میں کیا لکھنا ہے یہ جاننے کے لیے فارم دیکھیں۔",
    },
    "verify_notice": {
        "en": "This is general guidance. Always check the form's own instructions.",
        "hi": "यह सामान्य मार्गदर्शन है। फ़ॉर्म के अपने निर्देश सदैव देखें।",
        "kn": "ಇದು ಸಾಮಾನ್ಯ ಮಾರ್ಗದರ್ಶನ. ಅರ್ಜಿಯ ಸ್ವಂತ ಸೂಚನೆಗಳನ್ನು ಯಾವಾಗಲೂ ಪರಿಶೀಲಿಸಿ.",
        "ur": "یہ عمومی رہنمائی ہے۔ فارم کی اپنی ہدایات ہمیشہ دیکھیں۔",
    },
    "no_invented_value": {
        "en": "FormSathi will not invent the value you should write. Use the official instructions and your own records.",
        "hi": "FormSathi आपके लिए कोई मान नहीं गढ़ेगा। आधिकारिक निर्देशों और अपने अभिलेखों का उपयोग करें।",
        "kn": "ನೀವು ಬರೆಯಬೇಕಾದ ಮೌಲ್ಯವನ್ನು FormSathi ಸೃಷ್ಟಿಸುವುದಿಲ್ಲ. ಅಧಿಕೃತ ಸೂಚನೆಗಳು ಮತ್ತು ನಿಮ್ಮ ದಾಖಲೆಗಳನ್ನು ಬಳಸಿ.",
        "ur": "FormSathi آپ کے لیے کوئی قیمت نہیں گھڑے گا۔ سرکاری ہدایات اور اپنے ریکارڈ استعمال کریں۔",
    },
    "region_answer": {
        "en": "This is the printed region associated with the selected field.",
        "hi": "यह चयनित फ़ील्ड से जुड़ा छपा हुआ क्षेत्र है।",
        "kn": "ಇದು ಆಯ್ದ ಕ್ಷೇತ್ರಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಮುದ್ರಿತ ಪ್ರದೇಶ.",
        "ur": "یہ منتخب خانے سے منسلک چھپا ہوا حصہ ہے۔",
    },
    "sign_by_hand": {
        "en": "Sign the official form by hand. FormSathi never creates a signature.",
        "hi": "आधिकारिक फ़ॉर्म पर स्वयं हाथ से हस्ताक्षर करें। FormSathi कभी हस्ताक्षर नहीं बनाता।",
        "kn": "ಅಧಿಕೃತ ಅರ್ಜಿಯ ಮೇಲೆ ಕೈಯಿಂದಲೇ ಸಹಿ ಮಾಡಿ. FormSathi ಎಂದಿಗೂ ಸಹಿ ಸೃಷ್ಟಿಸುವುದಿಲ್ಲ.",
        "ur": "سرکاری فارم پر خود ہاتھ سے دستخط کریں۔ FormSathi کبھی دستخط نہیں بناتا۔",
    },
    "attachment": {
        "en": "Paste or attach the item yourself on the official form.",
        "hi": "आधिकारिक फ़ॉर्म पर यह वस्तु स्वयं चिपकाएँ या संलग्न करें।",
        "kn": "ಅಧಿಕೃತ ಅರ್ಜಿಯ ಮೇಲೆ ಈ ವಸ್ತುವನ್ನು ನೀವೇ ಅಂಟಿಸಿ ಅಥವಾ ಲಗತ್ತಿಸಿ.",
        "ur": "سرکاری فارم پر یہ چیز خود چسپاں یا منسلک کریں۔",
    },
    "office_use": {
        "en": "This space is marked for office use. Leave it blank.",
        "hi": "यह स्थान कार्यालय उपयोग हेतु अंकित है। इसे खाली छोड़ दें।",
        "kn": "ಈ ಜಾಗ ಕಚೇರಿ ಬಳಕೆಗೆ ಗುರುತಿಸಲಾಗಿದೆ. ಖಾಲಿ ಬಿಡಿ.",
        "ur": "یہ جگہ دفتری استعمال کے لیے مخصوص ہے۔ اسے خالی چھوڑ دیں۔",
    },
    "required": {
        "en": "This field looks required. Enter a value or mark the field as not applicable.",
        "hi": "यह फ़ील्ड आवश्यक लगती है। कोई मान भरें या फ़ील्ड को 'लागू नहीं' के रूप में चिह्नित करें।",
        "kn": "ಈ ಕ್ಷೇತ್ರ ಅಗತ್ಯವೆಂದು ತೋರುತ್ತದೆ. ಮೌಲ್ಯವನ್ನು ನಮೂದಿಸಿ ಅಥವಾ ಕ್ಷೇತ್ರವನ್ನು 'ಅನ್ವಯಿಸುವುದಿಲ್ಲ' ಎಂದು ಗುರುತಿಸಿ.",
        "ur": "یہ خانہ ضروری لگتا ہے۔ کوئی قیمت بھریں یا خانے کو 'لاگو نہیں' کے طور پر نشان زد کریں۔",
    },
    "bad_date": {
        "en": "Use a date such as {fmt}.",
        "hi": "{fmt} जैसी तिथि लिखें।",
        "kn": "{fmt} ರೀತಿಯ ದಿನಾಂಕವನ್ನು ಬಳಸಿ.",
        "ur": "{fmt} جیسی تاریخ لکھیں۔",
    },
    "bad_year": {
        "en": "Write a four-digit year, such as 2024.",
        "hi": "चार अंकों का वर्ष लिखें, जैसे 2024।",
        "kn": "ನಾಲ್ಕು ಅಂಕಿಗಳ ವರ್ಷ ಬರೆಯಿರಿ, ಉದಾಹರಣೆಗೆ 2024.",
        "ur": "چار ہندسوں کا سال لکھیں، جیسے 2024۔",
    },
    "digits_only": {
        "en": "Use digits only for this field.",
        "hi": "इस फ़ील्ड में केवल अंक लिखें।",
        "kn": "ಈ ಕ್ಷೇತ್ರದಲ್ಲಿ ಅಂಕಿಗಳನ್ನು ಮಾತ್ರ ಬಳಸಿ.",
        "ur": "اس خانے میں صرف ہندسے لکھیں۔",
    },
    "number_expected": {
        "en": "Write a number in this field.",
        "hi": "इस फ़ील्ड में एक संख्या लिखें।",
        "kn": "ಈ ಕ್ಷೇತ್ರದಲ್ಲಿ ಸಂಖ್ಯೆಯನ್ನು ಬರೆಯಿರಿ.",
        "ur": "اس خانے میں ایک عدد لکھیں۔",
    },
    "amount_expected": {
        "en": "Write the amount in figures, such as 5000.",
        "hi": "राशि अंकों में लिखें, जैसे 5000।",
        "kn": "ಮೊತ್ತವನ್ನು ಅಂಕಿಗಳಲ್ಲಿ ಬರೆಯಿರಿ, ಉದಾಹರಣೆಗೆ 5000.",
        "ur": "رقم ہندسوں میں لکھیں، جیسے 5000۔",
    },
    "out_of_range": {
        "en": "Enter a value between {low} and {high}.",
        "hi": "{low} और {high} के बीच का मान भरें।",
        "kn": "{low} ಮತ್ತು {high} ನಡುವಿನ ಮೌಲ್ಯವನ್ನು ನಮೂದಿಸಿ.",
        "ur": "{low} اور {high} کے درمیان قیمت بھریں۔",
    },
    "bad_mobile": {
        "en": "An Indian mobile number has ten digits and starts with 6, 7, 8, or 9.",
        "hi": "भारतीय मोबाइल नंबर दस अंकों का होता है और 6, 7, 8 या 9 से शुरू होता है।",
        "kn": "ಭಾರತೀಯ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ಹತ್ತು ಅಂಕಿಗಳದ್ದಾಗಿದ್ದು 6, 7, 8 ಅಥವಾ 9 ರಿಂದ ಪ್ರಾರಂಭವಾಗುತ್ತದೆ.",
        "ur": "بھارتی موبائل نمبر دس ہندسوں کا ہوتا ہے اور 6، 7، 8 یا 9 سے شروع ہوتا ہے۔",
    },
    "bad_phone": {
        "en": "Check this phone number. It has too few or too many digits.",
        "hi": "यह फ़ोन नंबर जाँचें। इसमें अंक बहुत कम या बहुत अधिक हैं।",
        "kn": "ಈ ದೂರವಾಣಿ ಸಂಖ್ಯೆಯನ್ನು ಪರಿಶೀಲಿಸಿ. ಇದರಲ್ಲಿ ಅಂಕಿಗಳು ತೀರಾ ಕಡಿಮೆ ಅಥವಾ ಹೆಚ್ಚು ಇವೆ.",
        "ur": "یہ فون نمبر جانچیں۔ اس میں ہندسے بہت کم یا بہت زیادہ ہیں۔",
    },
    "bad_pincode": {
        "en": "An Indian PIN code has six digits and does not start with 0.",
        "hi": "भारतीय पिन कोड छह अंकों का होता है और 0 से शुरू नहीं होता।",
        "kn": "ಭಾರತೀಯ ಪಿನ್ ಕೋಡ್ ಆರು ಅಂಕಿಗಳದ್ದಾಗಿದ್ದು 0 ರಿಂದ ಪ್ರಾರಂಭವಾಗುವುದಿಲ್ಲ.",
        "ur": "بھارتی پن کوڈ چھ ہندسوں کا ہوتا ہے اور 0 سے شروع نہیں ہوتا۔",
    },
    "bad_aadhaar": {
        "en": "An Aadhaar number has twelve digits and does not start with 0 or 1. Copy it from the card.",
        "hi": "आधार संख्या बारह अंकों की होती है और 0 या 1 से शुरू नहीं होती। इसे कार्ड से देखकर लिखें।",
        "kn": "ಆಧಾರ್ ಸಂಖ್ಯೆ ಹನ್ನೆರಡು ಅಂಕಿಗಳದ್ದಾಗಿದ್ದು 0 ಅಥವಾ 1 ರಿಂದ ಪ್ರಾರಂಭವಾಗುವುದಿಲ್ಲ. ಕಾರ್ಡ್‌ನಿಂದ ನೋಡಿ ಬರೆಯಿರಿ.",
        "ur": "آدھار نمبر بارہ ہندسوں کا ہوتا ہے اور 0 یا 1 سے شروع نہیں ہوتا۔ اسے کارڈ سے دیکھ کر لکھیں۔",
    },
    "bad_pan": {
        "en": "A PAN looks like ABCDE1234F: five letters, four digits, then one letter.",
        "hi": "पैन इस प्रकार होता है ABCDE1234F: पाँच अक्षर, चार अंक, फिर एक अक्षर।",
        "kn": "ಪ್ಯಾನ್ ABCDE1234F ರೀತಿ ಇರುತ್ತದೆ: ಐದು ಅಕ್ಷರ, ನಾಲ್ಕು ಅಂಕಿ, ನಂತರ ಒಂದು ಅಕ್ಷರ.",
        "ur": "پین اس طرح ہوتا ہے ABCDE1234F: پانچ حروف، چار ہندسے، پھر ایک حرف۔",
    },
    "bad_ifsc": {
        "en": "An IFSC looks like DEMO0001234: four letters, a zero, then six characters.",
        "hi": "आईएफएससी इस प्रकार होता है DEMO0001234: चार अक्षर, एक शून्य, फिर छह वर्ण।",
        "kn": "ಐಎಫ್‌ಎಸ್‌ಸಿ DEMO0001234 ರೀತಿ ಇರುತ್ತದೆ: ನಾಲ್ಕು ಅಕ್ಷರ, ಒಂದು ಸೊನ್ನೆ, ನಂತರ ಆರು ಅಕ್ಷರ.",
        "ur": "آئی ایف ایس سی اس طرح ہوتا ہے DEMO0001234: چار حروف، ایک صفر، پھر چھ حروف۔",
    },
    "bad_account": {
        "en": "Bank account numbers are usually 8 to 20 digits. Check it against your passbook.",
        "hi": "बैंक खाता संख्या सामान्यतः 8 से 20 अंकों की होती है। इसे अपनी पासबुक से जाँचें।",
        "kn": "ಬ್ಯಾಂಕ್ ಖಾತೆ ಸಂಖ್ಯೆ ಸಾಮಾನ್ಯವಾಗಿ 8 ರಿಂದ 20 ಅಂಕಿಗಳಿರುತ್ತದೆ. ಪಾಸ್‌ಬುಕ್‌ನೊಂದಿಗೆ ಪರಿಶೀಲಿಸಿ.",
        "ur": "بینک اکاؤنٹ نمبر عام طور پر 8 سے 20 ہندسوں کا ہوتا ہے۔ اسے اپنی پاس بک سے جانچیں۔",
    },
    "bad_email": {
        "en": "An email address looks like name@example.com.",
        "hi": "ईमेल पता इस प्रकार होता है name@example.com।",
        "kn": "ಇಮೇಲ್ ವಿಳಾಸ name@example.com ರೀತಿ ಇರುತ್ತದೆ.",
        "ur": "ای میل پتہ اس طرح ہوتا ہے name@example.com۔",
    },
    "bad_blood_group": {
        "en": "Write a blood group such as A+, B-, O+, or AB+.",
        "hi": "रक्त समूह इस प्रकार लिखें: A+, B-, O+ अथवा AB+।",
        "kn": "A+, B-, O+ ಅಥವಾ AB+ ರೀತಿಯ ರಕ್ತದ ಗುಂಪನ್ನು ಬರೆಯಿರಿ.",
        "ur": "خون کا گروپ اس طرح لکھیں: A+، B-، O+ یا AB+۔",
    },
    "bad_reference": {
        "en": "Use letters, digits, spaces, hyphens, or slashes only.",
        "hi": "केवल अक्षर, अंक, रिक्त स्थान, हाइफ़न या स्लैश का प्रयोग करें।",
        "kn": "ಅಕ್ಷರ, ಅಂಕಿ, ಜಾಗ, ಹೈಫನ್ ಅಥವಾ ಸ್ಲ್ಯಾಶ್ ಮಾತ್ರ ಬಳಸಿ.",
        "ur": "صرف حروف، ہندسے، خالی جگہ، ہائفن یا سلیش استعمال کریں۔",
    },
    "name_has_digits": {
        "en": "A name should not contain digits. Check this value.",
        "hi": "नाम में अंक नहीं होने चाहिए। इस मान को जाँचें।",
        "kn": "ಹೆಸರಿನಲ್ಲಿ ಅಂಕಿಗಳು ಇರಬಾರದು. ಈ ಮೌಲ್ಯವನ್ನು ಪರಿಶೀಲಿಸಿ.",
        "ur": "نام میں ہندسے نہیں ہونے چاہیے۔ اس قیمت کو جانچیں۔",
    },
    "name_has_symbols": {
        "en": "A name should not contain symbols. Check this value.",
        "hi": "नाम में चिह्न नहीं होने चाहिए। इस मान को जाँचें।",
        "kn": "ಹೆಸರಿನಲ್ಲಿ ಚಿಹ್ನೆಗಳು ಇರಬಾರದು. ಈ ಮೌಲ್ಯವನ್ನು ಪರಿಶೀಲಿಸಿ.",
        "ur": "نام میں علامات نہیں ہونی چاہیے۔ اس قیمت کو جانچیں۔",
    },
    "too_long": {
        "en": "This value is longer than {limit} characters and may not fit the printed space.",
        "hi": "यह मान {limit} वर्णों से अधिक लंबा है और छपे स्थान में नहीं समा सकता।",
        "kn": "ಈ ಮೌಲ್ಯ {limit} ಅಕ್ಷರಗಳಿಗಿಂತ ಉದ್ದವಾಗಿದ್ದು ಮುದ್ರಿತ ಜಾಗದಲ್ಲಿ ಹೊಂದದಿರಬಹುದು.",
        "ur": "یہ قیمت {limit} حروف سے زیادہ لمبی ہے اور چھپی جگہ میں سما نہیں سکتی۔",
    },
    "bad_format": {
        "en": "Check the format. The form expects {fmt}.",
        "hi": "प्रारूप जाँचें। फ़ॉर्म {fmt} की अपेक्षा करता है।",
        "kn": "ಸ್ವರೂಪವನ್ನು ಪರಿಶೀಲಿಸಿ. ಅರ್ಜಿ {fmt} ಅನ್ನು ನಿರೀಕ್ಷಿಸುತ್ತದೆ.",
        "ur": "فارمیٹ جانچیں۔ فارم {fmt} کی توقع کرتا ہے۔",
    },
}


class TranslationService:
    """Serves FormSathi's own authored strings in the requested language.

    This service does not translate user text or form content. It only selects between
    strings that were written by hand for each supported language.
    """

    def message(self, key: str, language: Language, **params: object) -> str:
        bundle = MESSAGES.get(key, {})
        template = bundle.get(language.value) or bundle.get(Language.ENGLISH.value) or ""
        if not params:
            return template
        try:
            return template.format(**params)
        except (KeyError, IndexError):
            return template

    def validation_message(self, key: str, language: Language, **params: object) -> str:
        return self.message(key, language, **params)

    def unavailable_message(self, language: Language) -> str:
        return self.message("unavailable", language)

    def unlabelled_message(self, language: Language) -> str:
        return self.message("unlabelled", language)

    def verify_notice(self, language: Language) -> str:
        return self.message("verify_notice", language)

    def coverage(self) -> dict[str, list[str]]:
        """Which keys are missing a language. Used by the test suite to keep the four
        languages in step as messages are added."""
        gaps: dict[str, list[str]] = {}
        for key, bundle in MESSAGES.items():
            missing = [language.value for language in Language if not bundle.get(language.value, "").strip()]
            if missing:
                gaps[key] = missing
        return gaps
