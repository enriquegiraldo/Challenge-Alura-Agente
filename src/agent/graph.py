"""
Nodos del grafo LangGraph.

Cada nodo recibe el AgentState y devuelve un dict con las actualizaciones.

Flujo:
    route → retrieve → ¿pidió web?
                       ├─ no  → generate (RAG puro)
                       └─ sí  → validate_topic → ¿es tema Aurora?
                                              ├─ no → generate (sin web)
                                              └─ sí → web_search → generate (RAG + web)
"""
from __future__ import annotations

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from src.agent.prompts import get_prompts
from src.agent.web import (
    clean_query_for_web,
    is_aurora_topic,
    search_web,
    wants_web_search,
)
from src.config import get_settings
from src.rag.retriever import format_context, retrieve
from src.utils.logger import log


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentState(TypedDict, total=False):
    """Estado que circula por el grafo."""
    # Input
    question: str                # pregunta original del usuario
    language: str                # "es" o "en"
    # Routing
    needs_web: bool              # ¿el usuario pidió web explícitamente?
    # Retrieval
    context: str                 # contexto formateado para el LLM
    sources: list[dict]          # metadata de chunks recuperados (para UI)
    # Web search
    web_context: str             # resultados web formateados
    web_searched: bool           # ¿se ejecutó web search?
    # Output
    answer: str                  # respuesta final del agente
    error: str                   # mensaje de error si aplica


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Nodos
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def route_node(state: AgentState) -> dict:
    """Detecta deterministamente si el usuario pidió búsqueda web."""
    question = state.get("question", "")
    needs_web = wants_web_search(question)
    log.info(f"[bold blue]🧭 ROUTE[/] needs_web={needs_web}")
    return {"needs_web": needs_web}


def retrieve_node(state: AgentState) -> dict:
    """Recupera chunks relevantes del vectorstore."""
    question = state.get("question", "")
    if not question:
        return {"context": "", "sources": []}

    chunks = retrieve(question)
    context = format_context(chunks)
    sources = [
        {
            "source": c.source,
            "doc_id": c.doc_id,
            "page": c.page,
            "section": c.section,
            "score": round(c.score, 3),
            "citation": c.citation,
        }
        for c in chunks
    ]
    return {"context": context, "sources": sources}


def validate_topic_node(state: AgentState) -> dict:
    """Valida si la query es tema cubierto por Aurora (solo si se pidió web)."""
    question = state.get("question", "")
    language = state.get("language", "es")
    cleaned = clean_query_for_web(question)

    if not is_aurora_topic(cleaned, language):
        log.info("[bold yellow]⚠️  Tema fuera de alcance — sin web search[/]")
        return {"web_context": "", "web_searched": False}

    # Es tema válido → buscar en web
    web_results = search_web(cleaned)
    return {
        "web_context": web_results or "",
        "web_searched": True,
    }


def generate_node(state: AgentState) -> dict:
    """Genera la respuesta final usando el LLM."""
    s = get_settings()
    question = state.get("question", "")
    context = state.get("context", "")
    web_context = state.get("web_context", "")
    web_searched = state.get("web_searched", False)
    language = state.get("language", s.default_language)

    prompts = get_prompts(language)

    # Construir contexto completo (RAG + web si aplica)
    full_context = context
    if web_searched and web_context:
        full_context += "\n\n## Complemento web (verificar vigencia)\n" + web_context

    # Si no hay contexto RAG ni web, responder que no hay info
    if not full_context.strip() or full_context.strip() == "(sin contexto relevante encontrado)":
        no_info_msg = (
            "No encontré información sobre ese tema en la documentación de Aurora AI Studio. "
            "¿Puedes reformular la pregunta o consultar el FAQ disponible en la plataforma?"
            if language == "es"
            else "I couldn't find information about that topic in Aurora AI Studio's documentation. "
            "Can you rephrase the question or check the FAQ available on the platform?"
        )
        return {"answer": no_info_msg}

    # Construir prompt final
    prompt_text = prompts["generation"].format(
        base_prompt=prompts["base"],
        context=full_context,
        question=question,
        output_lang=prompts["output_lang"],
    )

    try:
        llm = ChatGoogleGenerativeAI(
            model=s.chat_model,
            google_api_key=s.google_api_key,
            temperature=0.3,
            max_output_tokens=2048,
        )
        log.info(f"[bold magenta]✨ GENERATE[/] (model={s.chat_model}, lang={language})")
        response = llm.invoke(prompt_text)
        answer = response.content.strip()
        return {"answer": answer}
    except Exception as e:
        log.error(f"[bold red]✗ Error en generate:[/] {e}")
        err_msg = (
            f"Ocurrió un error al generar la respuesta. Intenta nuevamente. ({type(e).__name__})"
            if language == "es"
            else f"An error occurred while generating the response. Please try again. ({type(e).__name__})"
        )
        return {"answer": err_msg, "error": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Routing condicional
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def route_after_retrieve(state: AgentState) -> str:
    """Decide si ir a validate_topic (pidió web) o directo a generate (RAG puro)."""
    return "validate_topic" if state.get("needs_web", False) else "generate"


def route_after_validate(state: AgentState) -> str:
    """Después de validar tema y buscar web, ir a generate."""
    return "generate"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Construcción del grafo
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_graph():
    """Construye y compila el grafo LangGraph."""
    workflow = StateGraph(AgentState)

    # Nodos
    workflow.add_node("route", route_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("validate_topic", validate_topic_node)
    workflow.add_node("generate", generate_node)

    # Edges
    workflow.set_entry_point("route")
    workflow.add_edge("route", "retrieve")
    workflow.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "validate_topic": "validate_topic",
            "generate": "generate",
        },
    )
    workflow.add_edge("validate_topic", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helper de invocación
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_graph = None


def get_graph():
    """Singleton del grafo compilado."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def ask(
    question: str,
    language: str | None = None,
) -> AgentState:
    """
    Invoca el agente completo y devuelve el estado final.
    Útil para CLI y para la UI.
    """
    s = get_settings()
    if not s.has_google_key:
        raise RuntimeError("GOOGLE_API_KEY no configurada.")
    if not s.vectorstore_ready:
        raise RuntimeError(
            "Vectorstore no encontrado. Ejecuta: python -m src.ingestion.ingest"
        )

    lang = language or s.default_language
    graph = get_graph()
    initial_state: AgentState = {
        "question": question,
        "language": lang,
    }
    final_state = graph.invoke(initial_state)
    return final_state
