"""
Vectorstore FAISS local con persistencia en disco.

Estrategia:
- build_and_save_vectorstore(chunks): genera embeddings y guarda FAISS en disco
- load_vectorstore(): carga el índice desde disco (lazy)
- get_vectorstore(): helper que carga o construye según corresponda
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.config import VECTORSTORE_DIR, get_settings
from src.rag.embeddings import get_embeddings
from src.utils.logger import log


def build_and_save_vectorstore(
    chunks: list[Document],
    embeddings: Optional[Embeddings] = None,
) -> int:
    """
    Construye el índice FAISS desde una lista de chunks y lo guarda en disco.
    Devuelve el número de chunks indexados.
    """
    if not chunks:
        raise ValueError("Lista de chunks vacía")

    embeddings = embeddings or get_embeddings()
    settings = get_settings()

    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"[bold cyan]🔧 Generando embeddings[/] ({len(chunks)} chunks)...")
    vs = FAISS.from_documents(chunks, embeddings)

    log.info(f"[bold cyan]💾 Guardando FAISS en[/] {VECTORSTORE_DIR}")
    vs.save_local(
        folder_path=str(VECTORSTORE_DIR),
        index_name="index",
    )
    return len(chunks)


def load_vectorstore(embeddings: Optional[Embeddings] = None) -> FAISS:
    """Carga el vectorstore FAISS desde disco."""
    settings = get_settings()
    if not settings.vectorstore_ready:
        raise RuntimeError(
            "Vectorstore no encontrado. Ejecuta primero: python -m src.ingestion.ingest"
        )
    embeddings = embeddings or get_embeddings()
    return FAISS.load_local(
        folder_path=str(VECTORSTORE_DIR),
        embeddings=embeddings,
        index_name="index",
        allow_dangerous_deserialization=True,  # Necesario para FAISS pickle local
    )


def get_vectorstore(embeddings: Optional[Embeddings] = None) -> FAISS:
    """Carga el vectorstore si existe; si no, lanza excepción informativa."""
    try:
        return load_vectorstore(embeddings)
    except RuntimeError:
        raise


def get_stats() -> dict:
    """Devuelve estadísticas básicas del vectorstore (sin cargarlo completo)."""
    settings = get_settings()
    return {
        "ready": settings.vectorstore_ready,
        "index_path": str(settings.vectorstore_path),
        "meta_path": str(settings.vectorstore_meta_path),
    }
