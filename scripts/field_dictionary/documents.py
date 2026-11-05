"""Identity-document number fields."""

from __future__ import annotations

from . import entry, t

VERIFY_EN = "Copy the number digit by digit from the card itself. Do not write it from memory."
VERIFY_HI = "संख्या को कार्ड से देखकर अंक दर अंक लिखें। स्मृति से न लिखें।"
VERIFY_KN = "ಸಂಖ್ಯೆಯನ್ನು ಕಾರ್ಡ್‌ನಿಂದಲೇ ನೋಡಿ ಅಂಕಿ ಅಂಕಿಯಾಗಿ ಬರೆಯಿರಿ. ನೆನಪಿನಿಂದ ಬರೆಯಬೇಡಿ."
VERIFY_UR = "نمبر کو کارڈ سے دیکھ کر ہندسہ بہ ہندسہ لکھیں۔ یاد سے نہ لکھیں۔"

ENTRIES = [
    entry(
        "aadhaar_number",
        "text",
        aliases={
            "en": ["aadhaar number", "aadhar number", "aadhaar no", "uid number", "aadhaar", "aadhaar card number"],
            "hi": ["आधार संख्या", "आधार नंबर", "आधार", "आधार कार्ड संख्या"],
            "kn": ["ಆಧಾರ್ ಸಂಖ್ಯೆ", "ಆಧಾರ್ ನಂಬರ್", "ಆಧಾರ್", "ಆಧಾರ್ ಕಾರ್ಡ್ ಸಂಖ್ಯೆ"],
            "ur": ["آدھار نمبر", "آدھار", "آدھار کارڈ نمبر"],
        },
        keywords={"en": ["aadhaar", "aadhar", "uid"], "hi": ["आधार"], "kn": ["ಆಧಾರ್"], "ur": ["آدھار"]},
        simple_label=t("Aadhaar number", "आधार संख्या", "ಆಧಾರ್ ಸಂಖ್ಯೆ", "آدھار نمبر"),
        what_to_enter=t(
            f"Write the twelve-digit number printed on your Aadhaar card. {VERIFY_EN}",
            f"अपने आधार कार्ड पर छपी बारह अंकों की संख्या लिखें। {VERIFY_HI}",
            f"ನಿಮ್ಮ ಆಧಾರ್ ಕಾರ್ಡ್‌ನಲ್ಲಿ ಮುದ್ರಿತವಾದ ಹನ್ನೆರಡು ಅಂಕಿಗಳ ಸಂಖ್ಯೆಯನ್ನು ಬರೆಯಿರಿ. {VERIFY_KN}",
            f"اپنے آدھار کارڈ پر چھپا بارہ ہندسوں کا نمبر لکھیں۔ {VERIFY_UR}",
        ),
        why_needed=t(
            "Offices use this number to check your identity against official records.",
            "कार्यालय इस संख्या से आधिकारिक अभिलेखों में आपकी पहचान जाँचते हैं।",
            "ಕಚೇರಿಗಳು ಈ ಸಂಖ್ಯೆಯಿಂದ ಅಧಿಕೃತ ದಾಖಲೆಗಳಲ್ಲಿ ನಿಮ್ಮ ಗುರುತನ್ನು ಪರಿಶೀಲಿಸುತ್ತವೆ.",
            "دفاتر اس نمبر سے سرکاری ریکارڈ میں آپ کی شناخت جانچتے ہیں۔",
        ),
        example="9999 8888 7777",
        format_hint=t("12 digits", "12 अंक", "12 ಅಂಕಿಗಳು", "12 ہندسے"),
        validation={"kind": "aadhaar_in", "format": "12 digits"},
    ),
    entry(
        "pan_number",
        "text",
        aliases={
            "en": ["pan number", "pan", "pan card number", "permanent account number", "pan no"],
            "hi": ["पैन संख्या", "पैन नंबर", "पैन", "स्थायी खाता संख्या"],
            "kn": ["ಪ್ಯಾನ್ ಸಂಖ್ಯೆ", "ಪ್ಯಾನ್", "ಶಾಶ್ವತ ಖಾತೆ ಸಂಖ್ಯೆ"],
            "ur": ["پین نمبر", "پین", "مستقل اکاؤنٹ نمبر"],
        },
        keywords={"en": ["pan"], "hi": ["पैन"], "kn": ["ಪ್ಯಾನ್"], "ur": ["پین"]},
        simple_label=t("PAN number", "पैन संख्या", "ಪ್ಯಾನ್ ಸಂಖ್ಯೆ", "پین نمبر"),
        what_to_enter=t(
            f"Write the ten-character code printed on your PAN card. {VERIFY_EN}",
            f"अपने पैन कार्ड पर छपा दस अक्षरों का कोड लिखें। {VERIFY_HI}",
            f"ನಿಮ್ಮ ಪ್ಯಾನ್ ಕಾರ್ಡ್‌ನಲ್ಲಿ ಮುದ್ರಿತವಾದ ಹತ್ತು ಅಕ್ಷರಗಳ ಸಂಕೇತವನ್ನು ಬರೆಯಿರಿ. {VERIFY_KN}",
            f"اپنے پین کارڈ پر چھپا دس حروف کا کوڈ لکھیں۔ {VERIFY_UR}",
        ),
        example="ABCDE1234F",
        format_hint=t("5 letters, 4 digits, 1 letter", "5 अक्षर, 4 अंक, 1 अक्षर", "5 ಅಕ್ಷರ, 4 ಅಂಕಿ, 1 ಅಕ್ಷರ", "5 حروف، 4 ہندسے، 1 حرف"),
        validation={"kind": "pan_in", "format": "ABCDE1234F"},
    ),
    entry(
        "voter_id",
        "text",
        aliases={
            "en": ["voter id", "epic number", "voter id number", "election card number", "voter card no"],
            "hi": ["मतदाता पहचान पत्र संख्या", "वोटर आईडी", "निर्वाचन कार्ड संख्या"],
            "kn": ["ಮತದಾರರ ಗುರುತಿನ ಚೀಟಿ ಸಂಖ್ಯೆ", "ವೋಟರ್ ಐಡಿ", "ಚುನಾವಣಾ ಕಾರ್ಡ್ ಸಂಖ್ಯೆ"],
            "ur": ["ووٹر شناختی نمبر", "ووٹر آئی ڈی", "الیکشن کارڈ نمبر"],
        },
        keywords={"en": ["voter", "epic", "election"], "hi": ["मतदाता", "वोटर", "निर्वाचन"], "kn": ["ಮತದಾರ", "ಚುನಾವಣಾ"], "ur": ["ووٹر", "الیکشن"]},
        simple_label=t("Voter ID number", "मतदाता पहचान संख्या", "ಮತದಾರರ ಗುರುತಿನ ಸಂಖ್ಯೆ", "ووٹر شناختی نمبر"),
        what_to_enter=t(
            f"Write the number printed on your voter identity card. {VERIFY_EN}",
            f"अपने मतदाता पहचान पत्र पर छपी संख्या लिखें। {VERIFY_HI}",
            f"ನಿಮ್ಮ ಮತದಾರರ ಗುರುತಿನ ಚೀಟಿಯಲ್ಲಿ ಮುದ್ರಿತವಾದ ಸಂಖ್ಯೆಯನ್ನು ಬರೆಯಿರಿ. {VERIFY_KN}",
            f"اپنے ووٹر شناختی کارڈ پر چھپا نمبر لکھیں۔ {VERIFY_UR}",
        ),
        example="DEM1234567",
        validation={"kind": "alphanumeric", "max_length": 20, "optional": True},
    ),
    entry(
        "passport_number",
        "text",
        aliases={
            "en": ["passport number", "passport no", "passport"],
            "hi": ["पासपोर्ट संख्या", "पासपोर्ट नंबर", "पासपोर्ट"],
            "kn": ["ಪಾಸ್‌ಪೋರ್ಟ್ ಸಂಖ್ಯೆ", "ಪಾಸ್‌ಪೋರ್ಟ್"],
            "ur": ["پاسپورٹ نمبر", "پاسپورٹ"],
        },
        keywords={"en": ["passport"], "hi": ["पासपोर्ट"], "kn": ["ಪಾಸ್‌ಪೋರ್ಟ್"], "ur": ["پاسپورٹ"]},
        simple_label=t("Passport number", "पासपोर्ट संख्या", "ಪಾಸ್‌ಪೋರ್ಟ್ ಸಂಖ್ಯೆ", "پاسپورٹ نمبر"),
        what_to_enter=t(
            f"Write the passport number from the first page of your passport. {VERIFY_EN}",
            f"अपने पासपोर्ट के पहले पृष्ठ से पासपोर्ट संख्या लिखें। {VERIFY_HI}",
            f"ನಿಮ್ಮ ಪಾಸ್‌ಪೋರ್ಟ್‌ನ ಮೊದಲ ಪುಟದಿಂದ ಪಾಸ್‌ಪೋರ್ಟ್ ಸಂಖ್ಯೆಯನ್ನು ಬರೆಯಿರಿ. {VERIFY_KN}",
            f"اپنے پاسپورٹ کے پہلے صفحے سے پاسپورٹ نمبر لکھیں۔ {VERIFY_UR}",
        ),
        example="Z1234567",
        validation={"kind": "alphanumeric", "max_length": 20, "optional": True},
    ),
    entry(
        "ration_card",
        "text",
        aliases={
            "en": ["ration card number", "ration card no", "pds card number", "family card number"],
            "hi": ["राशन कार्ड संख्या", "राशन कार्ड नंबर", "परिवार कार्ड संख्या"],
            "kn": ["ಪಡಿತರ ಚೀಟಿ ಸಂಖ್ಯೆ", "ರೇಷನ್ ಕಾರ್ಡ್ ಸಂಖ್ಯೆ", "ಕುಟುಂಬ ಚೀಟಿ ಸಂಖ್ಯೆ"],
            "ur": ["راشن کارڈ نمبر", "خاندانی کارڈ نمبر"],
        },
        keywords={"en": ["ration", "pds"], "hi": ["राशन"], "kn": ["ಪಡಿತರ", "ರೇಷನ್"], "ur": ["راشن"]},
        simple_label=t("Ration card number", "राशन कार्ड संख्या", "ಪಡಿತರ ಚೀಟಿ ಸಂಖ್ಯೆ", "راشن کارڈ نمبر"),
        what_to_enter=t(
            f"Write the number printed on your family's ration card. {VERIFY_EN}",
            f"अपने परिवार के राशन कार्ड पर छपी संख्या लिखें। {VERIFY_HI}",
            f"ನಿಮ್ಮ ಕುಟುಂಬದ ಪಡಿತರ ಚೀಟಿಯಲ್ಲಿ ಮುದ್ರಿತವಾದ ಸಂಖ್ಯೆಯನ್ನು ಬರೆಯಿರಿ. {VERIFY_KN}",
            f"اپنے خاندان کے راشن کارڈ پر چھپا نمبر لکھیں۔ {VERIFY_UR}",
        ),
        example="DEM0001234",
        validation={"kind": "alphanumeric", "max_length": 24, "optional": True},
    ),
    entry(
        "driving_licence",
        "text",
        aliases={
            "en": ["driving licence number", "driving license number", "dl number", "licence number"],
            "hi": ["ड्राइविंग लाइसेंस संख्या", "चालक अनुज्ञप्ति संख्या", "लाइसेंस संख्या"],
            "kn": ["ಚಾಲನಾ ಪರವಾನಗಿ ಸಂಖ್ಯೆ", "ಡ್ರೈವಿಂಗ್ ಲೈಸೆನ್ಸ್ ಸಂಖ್ಯೆ"],
            "ur": ["ڈرائیونگ لائسنس نمبر", "لائسنس نمبر"],
        },
        keywords={"en": ["driving", "licence", "license"], "hi": ["लाइसेंस", "अनुज्ञप्ति"], "kn": ["ಪರವಾನಗಿ", "ಲೈಸೆನ್ಸ್"], "ur": ["لائسنس"]},
        simple_label=t("Driving licence number", "ड्राइविंग लाइसेंस संख्या", "ಚಾಲನಾ ಪರವಾನಗಿ ಸಂಖ್ಯೆ", "ڈرائیونگ لائسنس نمبر"),
        what_to_enter=t(
            f"Write the licence number from your driving licence card. {VERIFY_EN}",
            f"अपने ड्राइविंग लाइसेंस कार्ड से लाइसेंस संख्या लिखें। {VERIFY_HI}",
            f"ನಿಮ್ಮ ಚಾಲನಾ ಪರವಾನಗಿ ಕಾರ್ಡ್‌ನಿಂದ ಪರವಾನಗಿ ಸಂಖ್ಯೆಯನ್ನು ಬರೆಯಿರಿ. {VERIFY_KN}",
            f"اپنے ڈرائیونگ لائسنس کارڈ سے لائسنس نمبر لکھیں۔ {VERIFY_UR}",
        ),
        example="KA0120110001234",
        validation={"kind": "alphanumeric", "max_length": 24, "optional": True},
    ),
    entry(
        "application_number",
        "text",
        aliases={
            "en": ["application number", "application no", "reference number", "acknowledgement number", "registration number", "enrolment number", "token number", "file number"],
            "hi": ["आवेदन संख्या", "संदर्भ संख्या", "पंजीकरण संख्या", "पावती संख्या", "फाइल संख्या"],
            "kn": ["ಅರ್ಜಿ ಸಂಖ್ಯೆ", "ಉಲ್ಲೇಖ ಸಂಖ್ಯೆ", "ನೋಂದಣಿ ಸಂಖ್ಯೆ", "ಸ್ವೀಕೃತಿ ಸಂಖ್ಯೆ", "ಕಡತ ಸಂಖ್ಯೆ"],
            "ur": ["درخواست نمبر", "حوالہ نمبر", "رجسٹریشن نمبر", "رسید نمبر", "فائل نمبر"],
        },
        keywords={"en": ["application", "reference", "registration", "acknowledgement"], "hi": ["आवेदन", "संदर्भ", "पंजीकरण"], "kn": ["ಅರ್ಜಿ", "ಉಲ್ಲೇಖ", "ನೋಂದಣಿ"], "ur": ["درخواست", "حوالہ", "رجسٹریشن"]},
        simple_label=t("Application or reference number", "आवेदन अथवा संदर्भ संख्या", "ಅರ್ಜಿ ಅಥವಾ ಉಲ್ಲೇಖ ಸಂಖ್ಯೆ", "درخواست یا حوالہ نمبر"),
        what_to_enter=t(
            "Write the number the office already gave you for this application. If no number has been given to you yet, leave this blank for the office to fill.",
            "इस आवेदन के लिए कार्यालय ने आपको जो संख्या पहले दी है वह लिखें। यदि अभी कोई संख्या नहीं मिली है तो इसे कार्यालय के भरने के लिए खाली छोड़ दें।",
            "ಈ ಅರ್ಜಿಗೆ ಕಚೇರಿ ಈಗಾಗಲೇ ನೀಡಿರುವ ಸಂಖ್ಯೆಯನ್ನು ಬರೆಯಿರಿ. ಇನ್ನೂ ಸಂಖ್ಯೆ ಸಿಗದಿದ್ದರೆ ಕಚೇರಿ ಭರಿಸಲು ಖಾಲಿ ಬಿಡಿ.",
            "اس درخواست کے لیے دفتر نے آپ کو جو نمبر پہلے دیا ہے وہ لکھیں۔ اگر ابھی کوئی نمبر نہیں ملا تو اسے دفتر کے بھرنے کے لیے خالی چھوڑ دیں۔",
        ),
        example="APP/2026/000123",
        validation={"kind": "alphanumeric", "max_length": 32, "optional": True},
    ),
]
