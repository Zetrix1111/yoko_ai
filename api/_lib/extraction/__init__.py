"""
api/_lib/extraction/

Motor de extracción de datos desde archivos (PDF, imágenes, Excel, Word)
usando OpenAI Vision o texto plano + un sistema de templates registrables.

Uso típico desde código nuevo:

    from _lib.extraction import extract_with_template

    result = extract_with_template(file_bytes, filename, "factura", api_key)
    # → {"campos": {...post-enrich...}, "raw_text": "...", "template": "factura"}

Discovery de templates disponibles:

    from _lib.extraction import list_templates
    list_templates()
    # → [{"name": "caja_chica", "description": "...", "model": "gpt-4o"}, ...]
"""

from .engine import extract_with_template, extract_from_file
from .registry import (
    get_template,
    list_templates,
    register_template,
    reset_registry,
)

__all__ = [
    "extract_with_template",
    "extract_from_file",
    "get_template",
    "list_templates",
    "register_template",
    "reset_registry",
]
