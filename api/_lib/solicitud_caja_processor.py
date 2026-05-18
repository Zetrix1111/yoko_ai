"""
Procesamiento de archivos para solicitudes de caja chica.

Fuente de verdad de extracción: template `caja_chica` en `_lib.extraction`.
Este módulo lo usan tanto tools locales OpenAI como endpoints/tool-calls
de Managed Agents para evitar duplicar OCR/Vision.
"""

import base64
import os
from typing import Any

from . import yoko_cart_store
from .extraction import extract_with_template


def _files_from_args(args: dict[str, Any]) -> list[dict]:
    files = args.get("files")
    if isinstance(files, list) and files:
        return [f for f in files if isinstance(f, dict)]

    session_id = str(args.get("session_id_for_cart") or "").strip()
    if session_id:
        return yoko_cart_store.get_files(session_id)
    return []


def _decode_file(file_item: dict) -> tuple[str, bytes]:
    filename = str(file_item.get("filename") or "archivo").strip() or "archivo"
    raw_b64 = str(file_item.get("content_b64") or "").strip()
    if not raw_b64:
        raise ValueError(f"El archivo {filename} no trae content_b64.")
    try:
        return filename, base64.b64decode(raw_b64)
    except Exception as e:
        raise ValueError(f"No se pudo decodificar {filename}: {type(e).__name__}") from e


def _merge_campos(resultados: list[dict]) -> dict:
    merged: dict[str, Any] = {}
    for item in resultados:
        campos = item.get("campos") or {}
        if not isinstance(campos, dict):
            continue
        for key, value in campos.items():
            if key == "confianza":
                continue
            if key not in merged and value not in (None, ""):
                merged[key] = value

    confianzas = [
        (item.get("campos") or {}).get("confianza")
        for item in resultados
        if isinstance(item.get("campos"), dict)
    ]
    confianzas = [c for c in confianzas if c]
    if confianzas:
        if "baja" in confianzas:
            merged["confianza"] = "baja"
        elif "media" in confianzas:
            merged["confianza"] = "media"
        else:
            merged["confianza"] = "alta"
    return merged


def _normalize_campos(campos: dict) -> dict:
    if not isinstance(campos, dict):
        return {}
    out = dict(campos)
    return out


def procesar_solicitud_caja(args: dict[str, Any]) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY no configurada."}

    files = _files_from_args(args or {})
    if not files:
        return {
            "ok": False,
            "error": "No hay archivos para procesar.",
            "detail": "Envía `files` o `session_id_for_cart` con archivos en carrito.",
        }

    resultados: list[dict] = []
    for file_item in files:
        filename, file_bytes = _decode_file(file_item)
        if not file_bytes:
            raise ValueError(f"El archivo {filename} está vacío.")
        result = extract_with_template(file_bytes, filename, "caja_chica", api_key)
        campos = _normalize_campos(result.get("campos") or {})
        resultados.append({
            "filename": filename,
            "campos": campos,
            "raw_text": result.get("raw_text") or "",
            "template": result.get("template") or "caja_chica",
        })

    return {
        "ok": True,
        "template": "caja_chica",
        "total_archivos": len(resultados),
        "campos": _merge_campos(resultados),
        "archivos": resultados,
    }
