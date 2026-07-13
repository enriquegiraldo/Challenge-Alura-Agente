"""
Pipeline de ingesta: PDFs → chunks → embeddings → FAISS.

Uso:
    python -m src.ingestion.ingest            # desde la raíz del repo
    python scripts/ingest.py                  # atajo
"""
from __future__ import annotations

import sys
from pathlib import Path

from src.config import DOCUMENTS_DIR, get_settings
from src.ingestion.chunker import chunk_documents
from src.ingestion.loader import load_documents_from_dir
from src.rag.vectorstore import build_and_save_vectorstore
from src.utils.logger import log


def run_ingestion(documents_dir: Path | None = None) -> int:
    """
    Ejecuta la ingesta completa y guarda el vectorstore en disco.
    Devuelve el número de chunks indexados.
    """
    settings = get_settings()

    if not settings.has_google_key:
        log.error("[bold red]✗ GOOGLE_API_KEY no configurada.[/]")
        log.error("  Crea un archivo .env con tu clave (ver .env.example).")
        sys.exit(1)

    documents_dir = documents_dir or DOCUMENTS_DIR
    log.info("[bold magenta]━━━ Aurora RAG Agent — Ingesta ━━━[/]")

    # 1. Cargar PDFs
    documents = load_documents_from_dir(documents_dir)

    # 2. Chunking
    chunks = chunk_documents(documents)
    if not chunks:
        log.error("[bold red]✗ No se generaron chunks. Revisa los PDFs.[/]")
        sys.exit(1)

    # 3. Embeddings + FAISS
    n = build_and_save_vectorstore(chunks)

    log.info(f"[bold green]✓ Vectorstore listo.[/] {n} chunks indexados en:")
    log.info(f"  {settings.vectorstore_path}")
    log.info(f"  {settings.vectorstore_meta_path}")
    log.info("[bold magenta]━━━ Listo para chatear: streamlit run src/ui/app.py ━━━[/]")
    return n


if __name__ == "__main__":
    run_ingestion()
