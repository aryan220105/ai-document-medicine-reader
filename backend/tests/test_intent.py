from app.models.chat import QuestionIntent
from app.services.intent_service import IntentService


def test_intent_expiry_and_location() -> None:
    intent, location = IntentService().detect("Where is the expiry date?")
    assert intent == QuestionIntent.FIND_EXPIRY
    assert location is True


def test_intent_amount() -> None:
    intent, location = IntentService().detect("How much do I need to pay?")
    assert intent == QuestionIntent.FIND_AMOUNT
    assert location is False
