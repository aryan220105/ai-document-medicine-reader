from app.models.common import DocumentType
from app.services.classification_service import ClassificationService
from tests.test_extraction import ocr_from_lines


def test_medicine_classification() -> None:
    ocr = ocr_from_lines(
        ["PARACETAMOL TABLETS", "500 mg", "Batch: ABC123", "EXP: DEC 2027", "Dosage: As directed by physician."]
    )
    assert ClassificationService().classify(ocr) == DocumentType.MEDICINE_LABEL


def test_electricity_bill_classification() -> None:
    ocr = ocr_from_lines(
        ["ELECTRICITY BILL", "Account Number: 12345678", "Bill Amount: Rs 2450", "Due Date: 25 September 2026", "Units Consumed: 180 kWh"]
    )
    assert ClassificationService().classify(ocr) == DocumentType.ELECTRICITY_BILL
