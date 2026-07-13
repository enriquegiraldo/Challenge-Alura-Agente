"""
PDF Loader con extracción de metadatos enriquecidos.

Para cada PDF extrae:
- source: nombre del archivo
- page: número de página (1-indexed)
- total_pages: total de páginas del documento
- doc_id: identificador corto derivado del filename
- section: sección H2 detectada (propagada hacia adelante)

Mejoras sobre pypdf estándar:
- Limpia texto (colapsa espacios insertados por el extractor entre letras mayúsculas)
- Skipa la página 1 (cover con texto disperso del template HTML)
- Detecta secciones H2 con regex robusta
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from langchain_core.documents import Document
from pypdf import PdfReader

from src.utils.logger import log


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Patrones de sección H2
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Patrón base: número + punto + espacio + título
# Acepta posibles espacios insertados por el extractor (raro de pypdf)
SECTION_PATTERN = re.compile(
    r"^\s*(\d{1,2})\.\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,120}?)\s*$",
    re.MULTILINE,
)

# Patrón para detectar páginas de cover (skiparlas)
# El cover contiene "01/06", "02/06", etc. + "// POLÍTICA DE..." en mayúsculas dispersas
COVER_PATTERNS = [
    re.compile(r"\b\d{2}\s*/\s*0?6\b"),           # "01/06", "02/06"...
    re.compile(r"//\s*[A-ZÁÉÍÓÚÑ\s]{5,}"),        # "// POLÍTICA DE PRIVACIDAD"
    re.compile(r"Aurora\s*AI\s*Studio\s*S\.?\s*A\.?\s*S\.?", re.IGNORECASE),
]


def extract_doc_id(file_path: Path) -> str:
    """Genera un ID corto desde el filename. Ej: 'aurora-01-politica-privacidad.pdf' -> 'politica-privacidad'."""
    name = file_path.stem
    name = re.sub(r"^aurora-\d+-", "", name)
    return name


def clean_pdf_text(text: str) -> str:
    """
    Limpia texto extraído de PDF:
    - Colapsa espacios múltiples
    - Corrige "P O L Í T I C A" → "POLÍTICA" (espacios entre letras de una palabra)
    - Remueve caracteres de control
    - Normaliza saltos de línea
    """
    if not text:
        return ""

    # 1. Remover caracteres de control (excepto \n y \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 2. Corregir "P O L Í T I C A" → "POLÍTICA"
    # Detecta secuencias de letras mayúsculas o acentuadas separadas por espacios
    # Solo si la secuencia tiene 3+ letras (evita romper "I A" en "Inteligencia Artificial")
    def collapse_upper(match: re.Match) -> str:
        chars = match.group(0).replace(" ", "")
        return chars

    # Letras mayúsculas + acentuadas, separadas por espacios individuales
    text = re.sub(
        r"(?:[A-ZÁÉÍÓÚÑ]\s){2,}[A-ZÁÉÍÓÚÑ]",
        collapse_upper,
        text,
    )

    # 3. Colapsar espacios múltiples (pero preservar indentación de lista)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 4. Normalizar saltos de línea: múltiples \n → máximo 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. Remover espacios al inicio/final de líneas
    text = "\n".join(line.strip() for line in text.split("\n"))

    return text.strip()


def is_cover_page(text: str, page_num: int = 0) -> bool:
    """
    Detecta si una página es el cover.

    Heurística combinada:
    - Página 1 de PDFs generados con template de cover → siempre es cover
    - Patrones de texto del template: "01/06", "// POLÍTICA...", "Aurora AI Studio S.A.S." + "OCTUBRE 2025"
    """
    if page_num == 1:
        # Por convención, la página 1 de los PDFs generados es siempre el cover
        return True
    if not text:
        return False
    matches = sum(1 for pat in COVER_PATTERNS if pat.search(text))
    return matches >= 2


def detect_section(text: str) -> str | None:
    """Detecta si las primeras líneas del texto contienen un encabezado H2."""
    if not text:
        return None
    # Buscar en todo el texto (la sección puede aparecer en cualquier punto)
    # pero priorizar las primeras líneas
    lines = text.strip().split("\n")[:10]
    for line in lines:
        match = SECTION_PATTERN.match(line.strip())
        if match:
            num = match.group(1)
            title = match.group(2).strip()
            # Colapsar espacios internos del título
            title = re.sub(r"\s+", " ", title)
            return f"{num}. {title}"
    return None


def load_pdf(file_path: Path, skip_cover: bool = True) -> list[Document]:
    """
    Carga un PDF página por página, devolviendo un Document por página
    con metadatos enriquecidos (source, page, total_pages, doc_id, section).

    Args:
        file_path: ruta al PDF
        skip_cover: si True, detecta y omite páginas de cover (default True)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {file_path}")

    doc_id = extract_doc_id(file_path)
    reader = PdfReader(str(file_path))
    total_pages = len(reader.pages)

    documents: list[Document] = []
    current_section: str | None = None
    skipped_cover = 0

    log.info(f"[bold cyan]📄 Cargando[/] {file_path.name} ({total_pages} págs)")

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception as e:
            log.warning(f"  ⚠️  Error extrayendo página {page_num}: {e}")
            raw_text = ""

        # Limpiar texto
        text = clean_pdf_text(raw_text)

        if not text:
            continue

        # Skipar cover si está habilitado
        if skip_cover and is_cover_page(raw_text, page_num):
            log.debug(f"  ↩️  Pág {page_num} detectada como cover, omitida")
            skipped_cover += 1
            continue

        # Detectar sección en esta página y actualizar current_section
        detected = detect_section(text)
        if detected:
            current_section = detected

        doc = Document(
            page_content=text,
            metadata={
                "source": file_path.name,
                "doc_id": doc_id,
                "page": page_num,
                "total_pages": total_pages,
                "section": current_section or "Sin sección",
            },
        )
        documents.append(doc)

    log.info(
        f"  ✅ {len(documents)} páginas útiles "
        f"(cover omitido: {skipped_cover}, sección final: {current_section or 'N/A'})"
    )
    return documents


def load_documents_from_dir(documents_dir: Path) -> list[Document]:
    """Carga todos los PDFs de un directorio."""
    documents_dir = Path(documents_dir)
    if not documents_dir.exists():
        raise FileNotFoundError(f"Directorio no encontrado: {documents_dir}")

    pdf_files = sorted(documents_dir.glob("*.pdf"))
    if not pdf_files:
        raise ValueError(f"No se encontraron PDFs en {documents_dir}")

    log.info(f"[bold]📂 Cargando {len(pdf_files)} PDFs de[/] {documents_dir}")
    all_docs: list[Document] = []
    for pdf in pdf_files:
        docs = load_pdf(pdf)
        all_docs.extend(docs)

    log.info(f"[bold green]Total:[/] {len(all_docs)} páginas de {len(pdf_files)} PDFs")
    return all_docs


def iter_pdf_files(documents_dir: Path) -> Iterator[Path]:
    """Iterador sobre PDFs ordenados alfabéticamente."""
    yield from sorted(Path(documents_dir).glob("*.pdf"))
