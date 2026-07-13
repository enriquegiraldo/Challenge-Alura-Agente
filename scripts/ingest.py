#!/usr/bin/env python3
"""
Atajo para ejecutar la ingesta desde la raíz del proyecto.

Uso:
    python scripts/ingest.py
"""
import sys
from pathlib import Path

# Asegurar que la raíz del proyecto está en sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ingestion.ingest import run_ingestion

if __name__ == "__main__":
    run_ingestion()
