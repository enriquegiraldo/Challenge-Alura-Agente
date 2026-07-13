"""
Chunker con RecursiveCharacterTextSplitter que preserva metadatos
y propaga la sección detectada a cada chunk.

Mejoras sobre el agente_alura:
- Usa RecursiveCharacterTextSplitter (respeta separadores naturales)
- Propaga metadatos (source, page, doc_id, section) a cada chunk
- Re-detecta sección dentro del chunk si el texto empieza con H2
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.ingestion.loader import detect_section
from src.utils.logger import log


def make_splitter(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> RecursiveCharacterTextSplitter:
    """Crea el splitter con configuración del proyecto."""
    s = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or s.chunk_size,
        chunk_overlap=chunk_overlap or s.chunk_overlap,
        # Separadores en orden de prioridad: respeta párrafos, luego frases
        separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )


def chunk_documents(documents: list[Document]) -> list[Document]:
    """
    Divide una lista de Documents (típicamente 1 por página PDF) en chunks
    más pequeños preservando metadatos.

    Por cada chunk, si el texto comienza con un patrón H2, actualiza el
    campo `section` del metadata. Esto permite citar la sección correcta
    incluso cuando un chunk cruza el límite de sección.
    """
    if not documents:
        return []

    splitter = make_splitter()
    chunks = splitter.split_documents(documents)

    # Re-detectar sección dentro de cada chunk
    for chunk in chunks:
        detected = detect_section(chunk.page_content[:300])
        if detected:
            chunk.metadata["section"] = detected

    log.info(
        f"[bold cyan]✂️  Chunked:[/] {len(documents)} páginas → {len(chunks)} chunks "
        f"(size={get_settings().chunk_size}, overlap={get_settings().chunk_overlap})"
    )
    return chunks
