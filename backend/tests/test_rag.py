from app.services.rag_service import RAGService
from tests.test_extraction import ocr_from_lines


def test_document_chunk_indexing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    from app.config import Settings

    settings = Settings(
        app_env="test",
        data_dir=tmp_path / "data",
        knowledge_base_dir=tmp_path / "kb",
        use_light_embeddings=True,
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb" / "bills.md").write_text("Electricity bills include a due date and amount payable.", encoding="utf-8")
    rag = RAGService(settings)
    assert rag.seed_knowledge_base() >= 1
    ocr = ocr_from_lines(["ELECTRICITY BILL", "Account Number: 12345678", "Bill Amount: Rs 2450"])
    assert rag.index_document("doc-rag", ocr) >= 1
    hits = rag.retrieve_document("What is the account number?", "doc-rag")
    assert hits
    knowledge = rag.retrieve_knowledge("What is a due date on a bill?")
    assert knowledge
