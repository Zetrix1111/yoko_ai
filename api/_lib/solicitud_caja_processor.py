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


def _is_empty(value: Any) -> bool:
    """
    Considera vacío: None, string vacío, lista vacía, dict vacío.
    Listas/dicts no-vacíos NO son ignorados (caso `detalle_gasto`: array de
    items que el agent necesita ver aunque solo aparezcan en un archivo).
    """
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _merge_campos(resultados: list[dict]) -> dict:
    """
    Combina los campos extraídos de varios archivos en un solo dict.

    Reglas:
    - Para campos escalares (motivo, total_general, moneda, etc.): se queda
      con el primero no-vacío.
    - Para `detalle_gasto` (array de items): concatena los items de TODOS
      los archivos. Si subiste 3 PDFs cada uno con sus ítems, el resultado
      es el array completo unificado.
    - `confianza` se promedia (gana la peor).
    """
    merged: dict[str, Any] = {}
    items_acumulados: list[dict] = []

    for item in resultados:
        campos = item.get("campos") or {}
        if not isinstance(campos, dict):
            continue
        for key, value in campos.items():
            if key == "confianza":
                continue
            if key == "detalle_gasto" and isinstance(value, list):
                items_acumulados.extend(v for v in value if isinstance(v, dict))
                continue
            if key not in merged and not _is_empty(value):
                merged[key] = value

    if items_acumulados:
        merged["detalle_gasto"] = items_acumulados
    elif "detalle_gasto" not in merged:
        merged["detalle_gasto"] = []

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
