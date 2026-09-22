from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    log_level: str = "INFO"

    groq_api_key: str = ""
    groq_api_key_2: str = ""
    groq_model: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_fallback_models: str = "openai/gpt-oss-20b,openai/gpt-oss-120b"
    groq_timeout_seconds: int = 30
    external_ai_enabled: bool = False

    max_upload_mb: int = 10
    max_pdf_pages: int = 5
    tesseract_lang: str = "eng+hin+kan"
    tesseract_cmd: str = ""

    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    knowledge_base_dir: Path = Field(default=BACKEND_DIR / "knowledge_base")
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    vector_store: str = "chroma"
    enable_lexical_retrieval_fallback: bool = True
    use_light_embeddings: bool = False
    persist_user_values: bool = False

    known_form_match_threshold: float = 0.42
    field_iou_merge: float = 0.45
    retrieval_min_score: float = 0.35
    low_confidence_threshold: float = 0.55

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def previews_dir(self) -> Path:
        return self.data_dir / "previews"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def knowledge_dir(self) -> Path:
        path = self.knowledge_base_dir
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        origins = {
            self.frontend_origin.rstrip("/"),
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
        return sorted(origins)

    def llm_api_keys(self) -> list[str]:
        keys: list[str] = []
        for key in (self.groq_api_key, self.groq_api_key_2):
            value = (key or "").strip()
            if value and value not in keys:
                keys.append(value)
        return keys

    def llm_models(self) -> list[str]:
        models: list[str] = []
        for item in [self.groq_model, *self.groq_fallback_models.split(",")]:
            value = item.strip()
            if value and value not in models:
                models.append(value)
        return models

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_keys()) and self.external_ai_enabled


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.previews_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return settings
