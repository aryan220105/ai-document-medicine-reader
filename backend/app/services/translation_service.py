from app.models.common import Language


class TranslationService:
    def unavailable_message(self, language: Language) -> str:
        if language == Language.HINDI:
            return (
                "\u0907\u0938 \u092b\u093c\u0940\u0932\u094d\u0921 \u0915\u0947 \u0932\u093f\u090f "
                "\u092e\u093e\u0930\u094d\u0917\u0926\u0930\u094d\u0936\u0928 \u0909\u092a\u0932\u092c\u094d\u0927 "
                "\u0928\u0939\u0940\u0902 \u0939\u0948\u0964 \u0915\u0943\u092a\u092f\u093e \u092b\u0949\u0930\u094d\u092e "
                "\u0915\u0947 \u0906\u0927\u093f\u0915\u093e\u0930\u093f\u0915 \u0928\u093f\u0930\u094d\u0926\u0947\u0936 \u0926\u0947\u0916\u0947\u0902\u0964"
            )
        if language == Language.KANNADA:
            return (
                "\u0c88 \u0c95\u0ccd\u0cb7\u0cc7\u0ca4\u0ccd\u0cb0\u0c95\u0ccd\u0c95\u0cc6 "
                "\u0cae\u0cbe\u0cb0\u0ccd\u0c97\u0ca6\u0cb0\u0ccd\u0cb6\u0ca8 \u0cb2\u0cad\u0ccd\u0caf\u0cb5\u0cbf\u0cb2\u0ccd\u0cb2. "
                "\u0ca6\u0caf\u0cb5\u0cbf\u0c9f\u0ccd\u0c9f\u0cc1 \u0c85\u0ca7\u0cbf\u0c95\u0cc3\u0ca4 "
                "\u0cb8\u0cc2\u0c9a\u0ca8\u0cc6\u0c97\u0cb3\u0ca8\u0ccd\u0ca8\u0cc1 \u0caa\u0cb0\u0cbf\u0cb6\u0cc0\u0cb2\u0cbf\u0cb8\u0cbf."
            )
        return "Guidance is unavailable for this field. Check the official printed instructions."
