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

    groq_api_key: str = ""
    groq_api_key_2: str = ""
    openai_api_key: str = ""
    openai_model: str = "openai/gpt-oss-20b"
    openai_fallback_models: str = "openai/gpt-oss-120b,llama-3.3-70b-versatile"
    openai_base_url: str = "https://api.groq.com/openai/v1"

    max_upload_mb: int = 10
    tesseract_lang: str = "eng+hin+kan"
    tesseract_cmd: str = ""

    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    knowledge_base_dir: Path = Field(default=BACKEND_DIR / "knowledge_base")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    use_light_embeddings: bool = False

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

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
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        }
        return sorted(origins)

    def llm_api_keys(self) -> list[str]:
        keys: list[str] = []
        for key in (self.groq_api_key, self.groq_api_key_2, self.openai_api_key):
            value = (key or "").strip()
            if value and value not in keys:
                keys.append(value)
        return keys

    def llm_fallback_models(self) -> list[str]:
        return [part.strip() for part in self.openai_fallback_models.split(",") if part.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_keys())


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return settings
