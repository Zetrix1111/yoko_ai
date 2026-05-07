"""
api/_lib/facturas_processor.py

Procesador de múltiples archivos de facturas en paralelo.
Orquesta la extracción de datos usando parse_file.py y agrega metadata.

Funciones principales:
- process_multiple_files(): Procesa un array de archivos en paralelo
- add_metadata(): Enriquece los datos extraídos con campos adicionales
- generate_mock_factura(): Mock data para testing sin llamar a OpenAI
"""

import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

# Agregar directorio padre (api/) al path para poder hacer `from parse_file ...`.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# Reusar las funciones de extracción y el prompt de facturas que ya tiene
# parse_file.py (Fase 1). No duplicamos lógica de OCR ni el prompt.
from parse_file import (                                              # noqa: E402
    _extract_via_vision,
    _extract_pdf_pages,
    _extract_from_excel,
    _extract_from_docx,
    _text_to_campos,
    _enrich_factura_data,
    _EXTRACTION_PROMPT_FACTURA,
)


# ─────────────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────────────

MAX_WORKERS = 5         # Máximo de archivos procesándose simultáneamente
TIMEOUT_PER_FILE = 30   # Segundos máximo por archivo
MAX_FILES_PER_BATCH = 50


# ─────────────────────────────────────────────────────────────────────────
# Procesamiento de archivo individual
# ─────────────────────────────────────────────────────────────────────────

def process_single_file(
    filename: str,
    file_bytes: bytes,
    api_key: str,
) -> Optional[List[Dict]]:
    """
    Procesa un solo archivo y extrae datos de factura(s).

    Devuelve una LISTA de dicts (1 o más facturas):
      - Imagen / Excel / Word / PDF de 1 página → 1 factura.
      - PDF de N páginas con texto extraíble → N facturas (1 por página).
      - PDF escaneado → 1 factura (Vision lee solo la 1ra página).
      - None si no se pudo extraer nada útil.

    Mensajes en stderr indican qué path se tomó para que se pueda inspeccionar
    el behaviour desde los logs de Vercel.
    """
    try:
        ext = (filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        prompt = _EXTRACTION_PROMPT_FACTURA

        # XML por ahora no se procesa por OCR — los comprobantes electrónicos
        # XML tienen estructura posicional bien definida (UBL 2.1 / SUNAT) y
        # merecen un parser dedicado, no extracción visual. Iteración futura.
        if ext == "xml":
            print(
                f"[facturas_processor] {filename}: XML no soportado por ahora "
                f"(usa PDF o imagen)",
                file=sys.stderr,
            )
            return None

        # ── PDF: tratamiento especial multi-página ──────────────────────
        if ext == "pdf":
            pages = _extract_pdf_pages(file_bytes)
            paginas_con_texto = sum(1 for p in pages if len(p.strip()) > 30)
            print(
                f"[facturas_processor] {filename}: PDF con {len(pages)} página(s), "
                f"{paginas_con_texto} con texto >30 chars",
                file=sys.stderr,
            )

            if paginas_con_texto > 0:
                # PDF text-nativo (lector PDF, NO Vision). Una factura por página.
                facturas: List[Dict] = []
                for i, page_text in enumerate(pages):
                    if len(page_text.strip()) < 30:
                        # Página sin contenido útil (separador, blank, etc.)
                        continue
                    try:
                        campos_pagina, _raw = _text_to_campos(page_text, api_key, prompt)
                        if campos_pagina:
                            facturas.append(_enrich_factura_data(campos_pagina))
                    except Exception as page_err:
                        print(
                            f"[facturas_processor] {filename} pág {i+1}: {page_err}",
                            file=sys.stderr,
                        )
                        continue
                print(
                    f"[facturas_processor] {filename}: {len(facturas)} factura(s) "
                    f"extraída(s) por lector PDF",
                    file=sys.stderr,
                )
                return facturas if facturas else None

            # PDF escaneado o sin texto → fallback a Vision.
            print(
                f"[facturas_processor] {filename}: PDF sin texto, usando Vision",
                file=sys.stderr,
            )
            campos, _raw = _extract_via_vision(
                file_bytes, "application/pdf", api_key, prompt
            )
            return [_enrich_factura_data(campos)] if campos else None

        # ── Resto de formatos: 1 factura por archivo ────────────────────
        campos: Dict = {}
        if ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
            mime = f"image/{ext if ext != 'jpg' else 'jpeg'}"
            campos, _raw = _extract_via_vision(file_bytes, mime, api_key, prompt)

        elif ext in ("xlsx", "xls"):
            text = _extract_from_excel(file_bytes)
            if not text:
                return None
            campos, _raw = _text_to_campos(text, api_key, prompt)

        elif ext in ("docx", "doc"):
            text = _extract_from_docx(file_bytes)
            if not text:
                return None
            campos, _raw = _text_to_campos(text, api_key, prompt)

        else:
            # Default: intentar como imagen genérica.
            campos, _raw = _extract_via_vision(
                file_bytes, "image/jpeg", api_key, prompt
            )

        return [_enrich_factura_data(campos)] if campos else None

    except Exception as e:
        print(f"[facturas_processor] Error procesando {filename}: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────────────
# Metadata y enriquecimiento
# ─────────────────────────────────────────────────────────────────────────

def add_metadata(campos: Dict, filename: str, tipo: str, mes: str) -> Dict:
    """
    Agrega metadata adicional a los datos extraídos:
      - id: UUID único de la factura
      - archivo_nombre: nombre del archivo original
      - tipo_operacion: "compra" o "venta"
      - periodo: YYYY-MM
    """
    return {
        "id":              str(uuid.uuid4()),
        "archivo_nombre":  filename,
        "tipo_operacion":  tipo,
        "periodo":         mes,
        **campos,
    }


# ─────────────────────────────────────────────────────────────────────────
# Procesamiento múltiple en paralelo
# ─────────────────────────────────────────────────────────────────────────

def process_multiple_files(
    files: List[Tuple[str, bytes]],
    tipo: str,
    mes: str,
    api_key: str,
) -> Dict[str, List]:
    """
    Procesa múltiples archivos de facturas en paralelo (hasta MAX_WORKERS
    simultáneos para no saturar OpenAI).

    Args:
        files: Lista de tuplas (filename, file_bytes)
        tipo:  "compra" o "venta"
        mes:   YYYY-MM (ej: "2026-05")
        api_key: OpenAI API key

    Returns:
        {
          "facturas": [<facturas exitosas con metadata>],
          "errores":  [<nombres de archivos que fallaron>]
        }

    Raises:
        ValueError si len(files) > MAX_FILES_PER_BATCH o api_key vacío.
    """
    if not files:
        return {"facturas": [], "errores": []}

    if len(files) > MAX_FILES_PER_BATCH:
        raise ValueError(f"Máximo {MAX_FILES_PER_BATCH} archivos por lote.")

    if not api_key:
        raise ValueError("OPENAI_API_KEY no configurada.")

    facturas_extraidas: List[Dict] = []
    archivos_fallidos: List[str] = []

    print(f"[facturas_processor] Procesando {len(files)} archivos...", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_filename = {
            executor.submit(process_single_file, filename, file_bytes, api_key): filename
            for filename, file_bytes in files
        }

        # Timeout total = (TIMEOUT_PER_FILE * N) — generoso porque corren en paralelo.
        for future in as_completed(future_to_filename, timeout=TIMEOUT_PER_FILE * len(files)):
            filename = future_to_filename[future]
            try:
                result = future.result(timeout=TIMEOUT_PER_FILE)
                # `result` es una List[Dict] (1+ facturas por archivo).
                # Un PDF multi-página puede generar N facturas a partir de un solo file.
                if result and isinstance(result, list) and len(result) > 0:
                    for factura_campos in result:
                        factura_completa = add_metadata(factura_campos, filename, tipo, mes)
                        facturas_extraidas.append(factura_completa)
                    print(
                        f"[facturas_processor] OK {filename}: {len(result)} factura(s)",
                        file=sys.stderr,
                    )
                else:
                    archivos_fallidos.append(filename)
                    print(f"[facturas_processor] FAIL {filename} (sin datos)", file=sys.stderr)
            except Exception as e:
                archivos_fallidos.append(filename)
                print(
                    f"[facturas_processor] FAIL {filename}: {type(e).__name__}",
                    file=sys.stderr,
                )

    print(
        f"[facturas_processor] Completado: {len(facturas_extraidas)} OK, "
        f"{len(archivos_fallidos)} fallidos",
        file=sys.stderr,
    )

    return {
        "facturas": facturas_extraidas,
        "errores":  archivos_fallidos,
    }


# ─────────────────────────────────────────────────────────────────────────
# Función auxiliar para debug/testing — NO llama a OpenAI
# ─────────────────────────────────────────────────────────────────────────

def generate_mock_factura(filename: str) -> Dict:
    """Genera una factura mock para testing sin llamar a OpenAI."""
    import random

    tipos = ["FT", "BV", "NC", "ND", "RH"]
    monedas = ["PEN", "USD", "EUR"]

    return {
        "id":              str(uuid.uuid4()),
        "archivo_nombre":  filename,
        "fecha_emision":   f"{random.randint(1, 28):02d}/04/2026",
        "ruc":             f"201234567{random.randint(10, 99)}",
        "proveedor":       f"PROVEEDOR MOCK {random.randint(1, 100)} SAC",
        "tipo_doc_codigo": random.choice(tipos),
        "tipo_doc_nombre": "Factura",
        "serie":           f"F{random.randint(1, 999):03d}",
        "numero":          f"{random.randint(1, 99999):08d}",
        "concepto":        f"Producto o servicio mock {random.randint(1, 50)}",
        "moneda":          random.choice(monedas),
        "monto_total":     round(random.uniform(100, 5000), 2),
        "monto_tributo":   round(random.uniform(18, 900), 2),
        "obra_area":       "",
        "estado":          "Por implementar validación",
        "confianza":       round(random.uniform(0.7, 0.99), 2),
    }
