"""Settings loaded from frontend/.env via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Azure OpenAI (optional)
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-08-01-preview"
    AZURE_OPENAI_DEPLOYMENT: str = ""

    # Azure Translator (required for upload)
    AZURE_TRANSLATOR_KEY: str = ""
    AZURE_TRANSLATOR_REGION: str = ""
    AZURE_TRANSLATOR_ENDPOINT: str = "https://api.cognitive.microsofttranslator.com"

    # Azure Language (required for upload)
    AZURE_LANGUAGE_KEY: str = ""
    AZURE_LANGUAGE_ENDPOINT: str = ""

    # Gemini (required for chat + insights + fallback)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Paths
    PRECOMPUTED_ROOT: Path = Path("..")
    CACHE_DIR: Path = Path("./data/cache")
    LOG_LEVEL: str = "INFO"

    def precomputed_root_resolved(self) -> Path:
        root = self.PRECOMPUTED_ROOT
        if not root.is_absolute():
            root = (Path(__file__).resolve().parent / root).resolve()
        return root

    def cache_dir_resolved(self) -> Path:
        cache = self.CACHE_DIR
        if not cache.is_absolute():
            cache = (Path(__file__).resolve().parent / cache).resolve()
        cache.mkdir(parents=True, exist_ok=True)
        return cache

    def has_azure_openai(self) -> bool:
        return bool(self.AZURE_OPENAI_API_KEY and self.AZURE_OPENAI_ENDPOINT and self.AZURE_OPENAI_DEPLOYMENT)

    def has_azure_translator(self) -> bool:
        return bool(self.AZURE_TRANSLATOR_KEY and self.AZURE_TRANSLATOR_REGION)

    def has_azure_language(self) -> bool:
        return bool(self.AZURE_LANGUAGE_KEY and self.AZURE_LANGUAGE_ENDPOINT)

    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
