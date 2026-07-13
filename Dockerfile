# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Aurora RAG Agent — Dockerfile
# Multi-stage: build deps + runtime ligero (FAISS CPU, sin Oracle Wallet).
# Compatible con OCI Always Free (ARM64 y AMD64).
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FROM python:3.11-slim AS base

# Metadata
LABEL org.opencontainers.image.title="Aurora RAG Agent"
LABEL org.opencontainers.image.description="Agente RAG basado en la documentación de Aurora AI Studio"
LABEL org.opencontainers.image.source="https://github.com/tu-usuario/aurora-rag-agent"
LABEL org.opencontainers.image.licenses="MIT"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Instalar dependencias del sistema (mínimas)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar requirements primero (mejor cache de layers)
COPY requirements-prod.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copiar código fuente y datos
COPY src/ ./src/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY storage/ ./storage/

# Crear directorio de vectorstore si no existe
RUN mkdir -p storage/vectorstore

# Exponer puerto de Streamlit
EXPOSE 8501

# Healthcheck (Streamlit responde 200 en /)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Comando por defecto: Streamlit
# El vectorstore se carga desde el volumen montado (storage/vectorstore)
CMD ["streamlit", "run", "src/ui/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
