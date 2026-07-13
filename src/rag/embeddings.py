"""
Embeddings de Google Gemini con lazy init.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.config import get_settings
from src.utils.logger import log


@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Devuelve instancia singleton de embeddings de Gemini."""
    s = get_settings()
    if not s.has_google_key:
        raise RuntimeError(
            "GOOGLE_API_KEY no configurada. Copia .env.example a .env y agrega tu clave."
        )
    log.debug(f"Inicializando embeddings: {s.embedding_model}")
    return GoogleGenerativeAIEmbeddings(
        model=s.embedding_model,
        google_api_key=s.google_api_key,
    )
