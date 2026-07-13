"""
Retriever con filtro de similitud coseno.

Mejoras sobre agente_alura:
- Devuelve los chunks con score de similitud
- Filtra chunks por debajo del threshold configurable
- Enriquece el resultado con metadata para citar archivo + página + sección
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.config import get_settings
from src.rag.vectorstore import get_vectorstore
from src.utils.logger import log


@dataclass
class RetrievedChunk:
    """Chunk recuperado con score y metadata lista para citar."""
    content: str
    score: float
    source: str       # nombre del archivo
    doc_id: str       # id corto
    page: int
    section: str

    @property
    def citation(self) -> str:
        """Cita formateada para mostrar al usuario."""
        return f"[{self.source}, pág. {self.page}, § {self.section}]"


def retrieve(
    query: str,
    k: Optional[int] = None,
    threshold: Optional[float] = None,
    embeddings: Optional[Embeddings] = None,
) -> list[RetrievedChunk]:
    """
    Recupera los k chunks más relevantes para la query, filtrando por similitud.

    Returns:
        Lista de RetrievedChunk ordenada por score descendente.
        Solo incluye chunks con score >= threshold.
    """
    s = get_settings()
    k = k or s.top_k
    threshold = threshold if threshold is not None else s.similarity_threshold

    vs = get_vectorstore(embeddings)

    # similarity_search_with_score devuelve (Document, float) donde float es
    # la DISTANCIA L2 (no similitud coseno). Convertimos a similitud.
    # FAISS con embeddings normalizados: similitud_coseno ≈ 1 - distancia_L2/2
    results = vs.similarity_search_with_score(query, k=k)

    retrieved: list[RetrievedChunk] = []
    for doc, distance in results:
        # Conversión aproximada L2 → coseno similitud
        # (válido para embeddings de Gemini que vienen normalizados)
        similarity = max(0.0, 1.0 - distance / 2.0)

        if similarity < threshold:
            log.debug(f"  ↓ descartado (sim={similarity:.3f} < {threshold}): "
                      f"{doc.metadata.get('source', '?')} p.{doc.metadata.get('page', '?')}")
            continue

        retrieved.append(RetrievedChunk(
            content=doc.page_content,
            score=similarity,
            source=doc.metadata.get("source", "desconocido"),
            doc_id=doc.metadata.get("doc_id", "desconocido"),
            page=doc.metadata.get("page", 0),
            section=doc.metadata.get("section", "Sin sección"),
        ))

    log.info(
        f"[bold green]🔎 Recuperados:[/] {len(retrieved)}/{len(results)} chunks "
        f"(threshold={threshold:.2f}, top_k={k})"
    )
    for r in retrieved:
        log.debug(f"  • {r.citation} (sim={r.score:.3f})")

    return retrieved


def format_context(chunks: list[RetrievedChunk]) -> str:
    """
    Formatea los chunks recuperados como contexto para el LLM.
    Cada chunk se etiqueta con su cita para que el modelo pueda referenciarla.
    """
    if not chunks:
        return "(sin contexto relevante encontrado)"

    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"--- FUENTE {i}: {chunk.citation} (similitud={chunk.score:.2f}) ---\n"
            f"{chunk.content}\n"
        )
    return "\n".join(parts)
