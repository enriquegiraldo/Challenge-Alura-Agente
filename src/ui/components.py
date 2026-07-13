"""
Componentes UI reutilizables para Streamlit.
"""
from __future__ import annotations

import streamlit as st

from src.config import get_settings


def render_sidebar() -> str | None:
    """
    Renderiza la barra lateral con:
    - Selector de idioma
    - Configuración del agente
    - Estado del vectorstore
    - Enlaces útiles

    Returns:
        Idioma seleccionado ('es' o 'en') o None si falta configuración.
    """
    st.sidebar.title("⚙️ Configuración")

    # ── Selector de idioma (efecto espejo UI) ────────────────────────────────
    s = get_settings()
    language = st.sidebar.radio(
        "🌐 Idioma del agente / Agent language",
        options=["es", "en"],
        format_func=lambda x: "🇪🇸 Español" if x == "es" else "🇬🇧 English",
        index=0 if s.default_language == "es" else 1,
        horizontal=True,
        help="Fuerza el idioma de la respuesta independientemente del input.",
    )

    st.sidebar.divider()

    # ── Estado del agente ────────────────────────────────────────────────────
    st.sidebar.subheader("📊 Estado")

    # API keys
    has_google = s.has_google_key
    has_tavily = s.has_tavily_key
    vs_ready = s.vectorstore_ready

    st.sidebar.markdown(
        f"**Gemini API Key:** {'✅ Configurada' if has_google else '❌ Falta'}\n\n"
        f"**Tavily API Key:** {'✅ Configurada' if has_tavily else '⚠️ Opcional'}\n\n"
        f"**Vectorstore FAISS:** {'✅ Listo' if vs_ready else '❌ Sin indexar'}"
    )

    if not has_google:
        st.sidebar.error(
            "Configura `GOOGLE_API_KEY` en tu archivo `.env`. "
            "Consíguela gratis en https://aistudio.google.com/apikey"
        )
    if not vs_ready and has_google:
        st.sidebar.warning(
            "El vectorstore no está indexado. Ejecuta en una terminal:\n\n"
            "```\npython -m src.ingestion.ingest\n```"
        )
        if st.sidebar.button("🔧 Indexar ahora", type="primary", use_container_width=True):
            _run_ingestion_from_ui()

    st.sidebar.divider()

    # ── Parámetros avanzados ─────────────────────────────────────────────────
    with st.sidebar.expander("🎛️ Parámetros avanzados"):
        new_threshold = st.slider(
            "Umbral de similitud",
            min_value=0.0,
            max_value=1.0,
            value=s.similarity_threshold,
            step=0.05,
            help="Chunks con similitud menor a este valor se descartan.",
        )
        new_top_k = st.slider(
            "Top-K (chunks a recuperar)",
            min_value=1,
            max_value=10,
            value=s.top_k,
            step=1,
        )
        # Persistir en session_state para que el retriever los use
        st.session_state["similarity_threshold"] = new_threshold
        st.session_state["top_k"] = new_top_k

    # ── Documentos cargados ──────────────────────────────────────────────────
    with st.sidebar.expander("📚 Documentos en la base"):
        from src.config import DOCUMENTS_DIR
        pdfs = sorted(DOCUMENTS_DIR.glob("*.pdf"))
        for pdf in pdfs:
            size_kb = pdf.stat().st_size / 1024
            st.sidebar.markdown(f"• `{pdf.name}` ({size_kb:.0f} KB)")

    # ── Enlaces ──────────────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.markdown(
        "🔗 **Enlaces útiles**\n\n"
        "- [Gemini API](https://aistudio.google.com/apikey)\n"
        "- [Tavily](https://tavily.com)\n"
        "- [Documentación LangChain](https://python.langchain.com)"
    )

    # Bloquear UI si falta configuración crítica
    if not has_google or not vs_ready:
        return None

    return language


def _run_ingestion_from_ui():
    """Ejecuta la ingesta desde la UI (con feedback)."""
    with st.spinner("Indexando documentos... esto puede tardar 1-2 minutos."):
        try:
            from src.ingestion.ingest import run_ingestion
            n = run_ingestion()
            st.success(f"✅ {n} chunks indexados. Recarga la página para chatear.")
        except Exception as e:
            st.error(f"❌ Error: {e}")


def render_sources_panel(sources: list[dict]):
    """Renderiza el panel de fuentes recuperadas debajo de la respuesta."""
    if not sources:
        return

    with st.expander(f"📚 Fuentes citadas ({len(sources)})", expanded=False):
        for i, src in enumerate(sources, start=1):
            score = src.get("score", 0)
            score_pct = int(score * 100)
            score_color = "🟢" if score >= 0.7 else "🟡" if score >= 0.5 else "🔴"
            st.markdown(
                f"**{i}. {src['source']}** "
                f"`pág. {src['page']}` · `§ {src['section']}` "
                f"{score_color} {score_pct}%"
            )


def render_web_badge(web_searched: bool):
    """Muestra un badge si la respuesta incluyó búsqueda web."""
    if web_searched:
        st.info(
            "ℹ️ Esta respuesta incluye un complemento de búsqueda web. "
            "Verifica la vigencia de la información web, ya que puede cambiar."
        )
