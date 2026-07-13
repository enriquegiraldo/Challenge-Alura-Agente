#!/usr/bin/env python3
"""
Smoke tests para validar que el agente funciona correctamente.

Ejecuta 5 consultas representativas y verifica:
1. RAG puro (consulta sobre privacidad)
2. RAG puro (consulta sobre FAQ)
3. RAG puro (consulta sobre guía de uso)
4. Gate web (pide web sobre tema cubierto)
5. Gate web (pide web sobre tema NO cubierto)

Uso:
    python scripts/test_agent.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.panel import Panel

from src.agent.graph import ask
from src.config import get_settings

console = Console()

TESTS = [
    {
        "name": "1. RAG puro — Privacidad",
        "question": "¿Cuánto tiempo conservan mis datos después de cancelar la cuenta?",
        "lang": "es",
        "expect_web": False,
    },
    {
        "name": "2. RAG puro — FAQ",
        "question": "¿Qué modelos de lenguaje están disponibles en la plataforma?",
        "lang": "es",
        "expect_web": False,
    },
    {
        "name": "3. RAG puro — Guía de uso",
        "question": "¿Cómo creo mi primer proyecto RAG?",
        "lang": "es",
        "expect_web": False,
    },
    {
        "name": "4. Web gate (tema cubierto) — debe buscar en web",
        "question": "busca en internet buenas prácticas sobre RAG y embeddings",
        "lang": "es",
        "expect_web": True,
    },
    {
        "name": "5. Web gate (tema NO cubierto) — NO debe buscar",
        "question": "busca en internet la capital de Australia",
        "lang": "es",
        "expect_web": False,
    },
]


def run_tests():
    s = get_settings()
    if not s.has_google_key:
        console.print("[bold red]✗ GOOGLE_API_KEY no configurada. Abortando.[/]")
        sys.exit(1)
    if not s.vectorstore_ready:
        console.print("[bold red]✗ Vectorstore no indexado. Ejecuta primero: python scripts/ingest.py[/]")
        sys.exit(1)

    console.print(Panel.fit(
        "[bold magenta]Aurora RAG Agent — Smoke Tests[/]\n"
        f"Modelo: {s.chat_model}\n"
        f"Embeddings: {s.embedding_model}\n"
        f"Idioma: es\n"
        f"Threshold: {s.similarity_threshold}\n"
        f"Top-K: {s.top_k}",
        border_style="magenta",
    ))

    passed = 0
    failed = 0
    for test in TESTS:
        console.print(f"\n[bold cyan]━━━ {test['name']} ━━━[/]")
        console.print(f"[dim]Q:[/] {test['question']}")

        try:
            state = ask(test["question"], language=test["lang"])
            answer = state.get("answer", "")
            sources = state.get("sources", [])
            web_searched = state.get("web_searched", False)

            console.print(f"[dim]Fuentes:[/] {len(sources)} chunks")
            for src in sources[:3]:
                console.print(f"  • {src['citation']} ({src['score']:.2f})")
            console.print(f"[dim]Web searched:[/] {web_searched}")

            # Verificación
            if web_searched == test["expect_web"]:
                console.print(f"[bold green]✅ PASS[/] (web_searched={web_searched}, expected={test['expect_web']})")
                passed += 1
            else:
                console.print(f"[bold red]❌ FAIL[/] (web_searched={web_searched}, expected={test['expect_web']})")
                failed += 1

            # Mostrar respuesta (truncada)
            preview = answer[:500] + ("..." if len(answer) > 500 else "")
            console.print(Panel(preview, border_style="blue", title="Respuesta"))

        except Exception as e:
            console.print(f"[bold red]❌ ERROR: {e}[/]")
            failed += 1

    console.print(f"\n[bold magenta]━━━ Resultado: {passed} pass, {failed} fail ━━━[/]")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    run_tests()
