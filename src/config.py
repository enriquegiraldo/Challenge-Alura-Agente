"""
Aurora RAG Agent — Configuración central.
Carga variables de entorno con pydantic-settings y valida que las claves
críticas estén presentes antes de arrancar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Rutas base del proyecto
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
STORAGE_DIR = PROJECT_ROOT / "storage"
VECTORSTORE_DIR = STORAGE_DIR / "vectorstore"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Settings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Settings(BaseSettings):
    """Configuración cargada desde .env con defaults sensatos."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API keys (obligatorias para funcionamiento) ──────────────────────────
    google_api_key: str = Field(default="", description="Google Gemini API key")
    tavily_api_key: str = Field(default="", description="Tavily API key (web search)")

    # ── Modelos ──────────────────────────────────────────────────────────────
    chat_model: str = Field(
        default="gemini-1.5-flash-latest",
        description="Modelo de chat de Gemini",
    )
    embedding_model: str = Field(
        default="models/text-embedding-004",
        description="Modelo de embeddings de Gemini",
    )

    # ── RAG ──────────────────────────────────────────────────────────────────
    default_language: Literal["es", "en"] = Field(
        default="es",
        description="Idioma por defecto del agente",
    )
    similarity_threshold: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Umbral de similitud coseno para filtrar chunks",
    )
    top_k: int = Field(default=4, ge=1, le=20, description="Número de chunks a recuperar")
    chunk_size: int = Field(default=1000, ge=200, le=4000, description="Tamaño de chunk (caracteres)")
    chunk_overlap: int = Field(default=200, ge=0, le=500, description="Overlap entre chunks")

    # ── Server ───────────────────────────────────────────────────────────────
    streamlit_server_port: int = Field(default=8501)
    streamlit_server_address: str = Field(default="0.0.0.0")

    # ── Validadores ──────────────────────────────────────────────────────────
    @field_validator("google_api_key")
    @classmethod
    def validate_google_key(cls, v: str) -> str:
        if not v or v.strip() == "":
            # No levantar error aquí — se valida al instanciar el agente.
            # Permite que `streamlit run` muestre pantalla de configuración.
            return ""
        return v.strip()

    @field_validator("tavily_api_key")
    @classmethod
    def validate_tavily_key(cls, v: str) -> str:
        return v.strip()

    # ── Propiedades derivadas ────────────────────────────────────────────────
    @property
    def has_google_key(self) -> bool:
        return bool(self.google_api_key)

    @property
    def has_tavily_key(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def vectorstore_path(self) -> Path:
        return VECTORSTORE_DIR / "index.faiss"

    @property
    def vectorstore_meta_path(self) -> Path:
        return VECTORSTORE_DIR / "index.pkl"

    @property
    def vectorstore_ready(self) -> bool:
        """True si el índice FAISS ya fue construido."""
        return self.vectorstore_path.exists() and self.vectorstore_meta_path.exists()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Singleton
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_settings: Settings | None = None


def get_settings() -> Settings:
    """Devuelve la instancia singleton de Settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Fuerza recarga de settings (útil tras editar .env)."""
    global _settings
    _settings = Settings()
    return _settings
