"""
Aurora RAG Agent — Aplicación Streamlit principal.

Ejecutar:
    streamlit run src/ui/app.py

Características:
- Chat interactivo con historial (session_state)
- Selector de idioma ES/EN (efecto espejo UI)
- Sidebar con estado del agente y parámetros avanzados
- Panel de fuentes citadas debajo de cada respuesta
- Badge cuando la respuesta incluye complemento web
- Pantalla de bienvenida con preguntas de ejemplo
"""
from __future__ import annotations

import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto está en sys.path
# (para que `from src.xxx` funcione al ejecutar con streamlit run)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.config import get_settings
from src.utils.logger import log

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configuración de la página
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.set_page_config(
    page_title="Aurora RAG Agent",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

# CSS custom para look developer-friendly
st.markdown("""
<style>
    /* Header más compacto */
    .stChatMessage { padding-top: 1rem; padding-bottom: 1rem; }
    /* Botón de envío con color de marca */
    .stChatInput button {
        background-color: #366ea6;
        color: white;
    }
    /* Tipografía para code blocks */
    .stCodeBlock { font-family: 'JetBrains Mono', 'Fira Code', monospace; }
    /* Reducir margen superior */
    .block-container { padding-top: 1.5rem; max-width: 850px; }
    /* Título principal */
    h1 { color: #334250; }
    h2, h3 { color: #334250; }
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Header
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.title("🤖 Aurora RAG Agent")
st.caption(
    "Agente de IA basado en **RAG** (Retrieval-Augmented Generation) que responde "
    "preguntas sobre la documentación oficial de **Aurora AI Studio S.A.S.** — "
    "políticas, términos, guías y procedimientos."
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sidebar — configuración y estado
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from src.ui.components import render_sidebar, render_sources_panel, render_web_badge

language = render_sidebar()

# Si no hay configuración crítica, mostrar pantalla de setup y salir
if language is None:
    st.divider()
    st.warning("⚠️ Configuración incompleta")
    st.markdown(
        "Para que el agente funcione necesitas:\n\n"
        "1. **`GOOGLE_API_KEY`** en el archivo `.env` (consíguela gratis en "
        "[aistudio.google.com](https://aistudio.google.com/apikey)).\n"
        "2. **Vectorstore indexado** — ejecuta `python -m src.ingestion.ingest` "
        "en una terminal desde la raíz del proyecto.\n\n"
        "Revisa la barra lateral para más detalles."
    )
    st.stop()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Inicialización del estado de sesión
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if "messages" not in st.session_state:
    # Mensaje de bienvenida del asistente
    welcome_es = (
        "¡Hola! 👋 Soy **Aurora**, el asistente virtual de Aurora AI Studio S.A.S. "
        "Puedo responder preguntas sobre nuestras políticas, términos de uso, "
        "guías y procedimientos.\n\n"
        "Tengo acceso a **6 documentos**:\n"
        "- 📜 Política de Privacidad\n"
        "- 📋 Términos y Condiciones\n"
        "- 💰 Política de Reembolsos\n"
        "- 📖 Guía de Uso de la Plataforma\n"
        "- 🚨 Procedimiento de Incidentes\n"
        "- ❓ Preguntas Frecuentes (FAQ)\n\n"
        "¿En qué puedo ayudarte hoy?"
    )
    welcome_en = (
        "Hi! 👋 I'm **Aurora**, the virtual assistant of Aurora AI Studio S.A.S. "
        "I can answer questions about our policies, terms of use, guides, and procedures.\n\n"
        "I have access to **6 documents**:\n"
        "- 📜 Privacy Policy\n"
        "- 📋 Terms and Conditions\n"
        "- 💰 Refund Policy\n"
        "- 📖 Platform User Guide\n"
        "- 🚨 Incident Response Procedure\n"
        "- ❓ Frequently Asked Questions (FAQ)\n\n"
        "How can I help you today?"
    )
    st.session_state.messages = [
        {"role": "assistant", "content": welcome_es if language == "es" else welcome_en}
    ]

# Reset historial si cambió el idioma
if "last_language" not in st.session_state:
    st.session_state["last_language"] = language
elif st.session_state["last_language"] != language:
    # Cambió el idioma — resetear conversación
    st.session_state["last_language"] = language
    st.session_state.messages = [
        {"role": "assistant", "content": welcome_es if language == "es" else welcome_en}
    ]
    st.session_state.pop("last_sources", None)
    st.session_state.pop("last_web", None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Preguntas de ejemplo (chips clicables)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if len(st.session_state.messages) <= 1:
    st.markdown("### 💡 Prueba con estas preguntas de ejemplo")
    examples_es = [
        "¿Cuánto tiempo tienen mis datos después de cancelar la cuenta?",
        "¿Puedo pedir reembolso de un plan anual?",
        "¿Cómo creo mi primer proyecto RAG?",
        "¿Qué es un incidente SEV-1 y cuál es el SLA?",
        "¿Mis datos se usan para entrenar modelos?",
    ]
    examples_en = [
        "How long do you keep my data after I cancel?",
        "Can I get a refund for an annual plan?",
        "How do I create my first RAG project?",
        "What is a SEV-1 incident and what's the SLA?",
        "Is my data used to train models?",
    ]
    examples = examples_es if language == "es" else examples_en
    cols = st.columns(len(examples))
    for col, ex in zip(cols, examples):
        if col.button(ex, use_container_width=True, key=f"example_{ex}"):
            st.session_state["pending_input"] = ex


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Historial de chat
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Mostrar fuentes solo en el último mensaje del asistente
        if (
            msg["role"] == "assistant"
            and msg is st.session_state.messages[-1]
            and "last_sources" in st.session_state
            and st.session_state["last_sources"]
        ):
            render_sources_panel(st.session_state["last_sources"])
        if (
            msg["role"] == "assistant"
            and msg is st.session_state.messages[-1]
            and st.session_state.get("last_web", False)
        ):
            render_web_badge(True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Input del usuario
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Si viene de un botón de ejemplo, precargar el input
default_prompt = st.session_state.pop("pending_input", "")

user_input = st.chat_input(
    "Escribe tu pregunta sobre Aurora AI Studio..." if language == "es"
    else "Type your question about Aurora AI Studio..."
)

if default_prompt and not user_input:
    user_input = default_prompt

if user_input:
    # Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Invocar el agente
    with st.chat_message("assistant"):
        with st.spinner("Pensando..." if language == "es" else "Thinking..."):
            try:
                from src.agent.graph import ask
                # Sobrescribir settings con valores del sidebar si cambiaron
                state = ask(user_input, language=language)
                answer = state.get("answer", "")
                sources = state.get("sources", [])
                web_searched = state.get("web_searched", False)

                st.markdown(answer)
                if sources:
                    render_sources_panel(sources)
                if web_searched:
                    render_web_badge(True)

                # Guardar en historial
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state["last_sources"] = sources
                st.session_state["last_web"] = web_searched

            except Exception as e:
                log.error(f"Error en UI: {e}", exc_info=True)
                err = (
                    f"⚠️ Ocurrió un error: `{type(e).__name__}: {e}`\n\n"
                    "Revisa los logs en consola para más detalle."
                )
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
