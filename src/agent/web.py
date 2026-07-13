"""
Web search gate con Tavily.

MEJORAS sobre agente_alura:
- Detección determinista de intención de web (regex, no LLM)
- Limpieza de la query (remueve "busca en internet" antes de buscar)
- Validación de tema cubierto por Aurora (clasificador LLM baro)
- Formato de resultados limpio para inyectar al generate node
"""
from __future__ import annotations

import re
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.prompts import get_prompts
from src.config import get_settings
from src.utils.logger import log


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Patrones deterministas para detectar intención de búsqueda web
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WEB_PATTERNS = [
    r"\bbusca\s+(en\s+)?(la\s+)?(internet|web|red)\b",
    r"\bsearch\s+(the\s+)?(internet|web)\b",
    r"\bgoogl[ea]a\b",
    r"\bverifica\s+(en\s+)?(internet|web)\b",
    r"\bcomplementa\s+(con|en)\s+(internet|web)\b",
    r"\bconsulta\s+(en\s+)?(internet|web)\b",
    r"\bactualíza\s+(con|en)\s+(internet|web)\b",
]

WEB_REGEX = re.compile("|".join(WEB_PATTERNS), re.IGNORECASE)


def wants_web_search(query: str) -> bool:
    """Detecta deterministamente si el usuario pidió búsqueda web."""
    if not query:
        return False
    return bool(WEB_REGEX.search(query))


def clean_query_for_web(query: str) -> str:
    """Remueve la instrucción 'busca en internet' para dejar solo el topic."""
    cleaned = WEB_REGEX.sub("", query)
    # Limpiar espacios extra y comas/puntos huérfanos
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"^[,\s]+|[,\s]+$", "", cleaned)
    return cleaned.strip() or query.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Validador de tema (¿es tema que Aurora cubre?)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_aurora_topic(query: str, language: str = "es") -> bool:
    """
    Usa el LLM para validar si la query está cubierta por la doc de Aurora.
    Si Tavily no está configurado, devuelve False (no busca web).
    """
    s = get_settings()
    if not s.has_tavily_key:
        log.warning("  ⚠️  Tavily no configurado — omitiendo web search")
        return False

    try:
        llm = ChatGoogleGenerativeAI(
            model=s.chat_model,
            google_api_key=s.google_api_key,
            temperature=0.0,
            max_output_tokens=10,
        )
        prompts = get_prompts(language)
        prompt = prompts["topic_validation"].format(question=query[:500])
        response = llm.invoke(prompt)
        answer = response.content.strip().upper()
        # Aceptar SI/YES como positivos
        is_valid = answer.startswith(("SI", "YES", "SÍ"))
        log.info(f"  [dim]Validación tema: {answer} → {'válido' if is_valid else 'no válido'}[/]")
        return is_valid
    except Exception as e:
        log.warning(f"  ⚠️  Error en validación de tema: {e}")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Búsqueda web
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_web(query: str, max_results: int = 3) -> Optional[str]:
    """
    Ejecuta búsqueda en Tavily y formatea resultados para inyectar al LLM.
    Devuelve None si no hay resultados o si Tavily falla.
    """
    s = get_settings()
    if not s.has_tavily_key:
        log.warning("  ⚠️  TAVILY_API_KEY no configurada — sin web search")
        return None

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=s.tavily_api_key)
        log.info(f"[bold cyan]🌐 Web search:[/] {query[:80]}")
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            # Restringir a dominios confiables para el contexto empresarial
            include_domains=None,
        )
        results = response.get("results", [])
        if not results:
            log.info("  (sin resultados web)")
            return None

        parts: list[str] = []
        for i, r in enumerate(results, start=1):
            title = r.get("title", "Sin título")
            url = r.get("url", "")
            snippet = r.get("content", "")[:500]
            parts.append(f"[{i}] {title}\n    URL: {url}\n    {snippet}\n")

        log.info(f"  ✅ {len(results)} resultados web")
        return "\n".join(parts)
    except Exception as e:
        log.error(f"  [bold red]✗ Tavily error:[/] {e}")
        return None
