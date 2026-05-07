"""
api/parse_file.py
Serverless function: recibe un archivo multipart (foto, PDF, Excel, Word),
extrae los campos relevantes usando:
  - OpenAI Vision (GPT-4o) para imágenes y PDFs página-a-imagen
  - openpyxl para archivos Excel
  - python-docx para documentos Word
  - pdfplumber para PDFs con texto nativo

Soporta dos modos:
  1. Caja chica (default): extrae campos de solicitud de caja chica
  2. Facturas: extrae campos de comprobantes de pago (query param ?tipo=factura)

Devuelve:
    {
      "campos": {
        // Campos específicos según el tipo
      },
      "confianza": "alta|media|baja",
      "raw_text": "..."   ← texto crudo extraído, para debug
    }

Los campos que no se puedan inferir vendrán como null.
"""

import base64
import cgi
import io
import json
import os
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth                 # noqa: E402
from _lib.auth import AuthError       # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# Prompts de extracción para OpenAI
# ─────────────────────────────────────────────────────────────────────────

_EXTRACTION_PROMPT_CAJA_CHICA = """Eres un asistente experto en extraer datos de documentos para solicitudes de caja chica.

Analiza el documento/imagen adjunto y extrae los siguientes campos si están presentes:
- motivo: Descripción general del gasto o propósito de la solicitud
- obra: Nombre del proyecto, obra o área
- total_general: Monto total numérico (sin símbolos de moneda)
- moneda: PEN, USD, EUR o CNY (infiere desde el contexto)
- plazo: Período de tiempo o fechas (ej. "Del 01/05 al 31/05")
- tipo_gasto: Uno de: CAJA CHICA, PASAJES AEREOS, CAJA EXTRAORDINARIA
- detalle_gasto: Lista de ítems de gasto con montos

Responde ÚNICAMENTE con un JSON con esta estructura exacta (usa null para campos no encontrados):
{
  "motivo": "...",
  "obra": "...",
  "total_general": 0.0,
  "moneda": "PEN",
  "plazo": "...",
  "tipo_gasto": "...",
  "detalle_gasto": "...",
  "confianza": "alta|media|baja"
}

"confianza" debe ser:
- "alta" si la mayoría de campos están claramente presentes
- "media" si algunos campos hay que inferirlos
- "baja" si el documento no es relevante o tiene muy poca información
"""

_EXTRACTION_PROMPT_FACTURA = """Eres un asistente experto en extraer datos de comprobantes de pago peruanos (facturas, boletas, notas de crédito/débito, recibos por honorarios).

Analiza el documento/imagen adjunto y extrae los siguientes campos si están presentes:

CAMPOS A EXTRAER:
1. fecha_emision: Fecha de emisión en formato DD/MM/YYYY
2. ruc: RUC del emisor (11 dígitos numéricos)
3. proveedor: Razón social completa del emisor
4. tipo_doc: Tipo de comprobante - UNO de estos valores exactos:
   - "Factura"
   - "Boleta"
   - "Nota de Crédito"
   - "Nota de Débito"
   - "Boleto Aéreo"
   - "Recibo por Honorarios"
   - "Ticket"
5. serie: Código de serie del comprobante (ej: F001, B002, E001)
6. numero: Número correlativo del comprobante (ej: 00012345)
7. concepto: Descripción breve del bien o servicio (máximo 100 caracteres)
8. moneda: Código de moneda - UNO de: PEN, USD, EUR, CNY
9. monto_total: Monto total INCLUYENDO IGV (número decimal con 2 decimales)
10. monto_tributo: Monto del IGV o tributo aplicable (número decimal con 2 decimales)

INSTRUCCIONES IMPORTANTES:
- Si no puedes detectar un campo con certeza, usa null
- Los montos deben ser números puros sin símbolos de moneda ni comas (ej: 1234.56)
- La fecha debe estar en formato DD/MM/YYYY (ej: 15/04/2026)
- El tipo_doc debe ser exactamente uno de los valores listados arriba
- El concepto debe ser conciso y descriptivo

Responde ÚNICAMENTE con un JSON válido (sin markdown, sin explicaciones):

{
  "fecha_emision": "DD/MM/YYYY",
  "ruc": "12345678901",
  "proveedor": "NOMBRE DE LA EMPRESA SAC",
  "tipo_doc": "Factura",
  "serie": "F001",
  "numero": "00012345",
  "concepto": "Descripción del servicio o producto",
  "moneda": "PEN",
  "monto_total": 1234.56,
  "monto_tributo": 222.22,
  "confianza": "alta"
}

NIVEL DE CONFIANZA:
- "alta": 90%+ de los campos están claramente legibles y presentes
- "media": 70-89% de campos detectados o algunos requieren inferencia
- "baja": <70% de campos o documento de baja calidad/no relevante
"""

# Mapeo de tipo de documento a código interno (2 letras).
TIPO_DOC_MAP = {
    "factura":               "FT",
    "boleta":                "BV",
    "nota de crédito":       "NC",
    "nota de credito":       "NC",
    "nota de débito":        "ND",
    "nota de debito":        "ND",
    "boleto aéreo":          "BA",
    "boleto aereo":          "BA",
    "recibo por honorarios": "RH",
    "honorarios":            "RH",
    "ticket":                "TK",
}


# ─────────────────────────────────────────────────────────────────────────
# Helpers de enriquecimiento (modo factura)
# ─────────────────────────────────────────────────────────────────────────

def _get_tipo_doc_codigo(tipo_nombre: str) -> str:
    """
    Convierte nombre de tipo de documento a código interno de 2 letras.
    Default a "FT" (Factura) si el nombre no calza con el mapeo.
    """
    if not tipo_nombre:
        return "FT"
    return TIPO_DOC_MAP.get(tipo_nombre.lower().strip(), "FT")


def _enrich_factura_data(campos: dict) -> dict:
    """
    Enriquece los datos extraídos de una factura con campos derivados:
      - tipo_doc_codigo: 2 letras (FT, BV, NC, ND, BA, RH, TK)
      - tipo_doc_nombre: nombre completo para display
      - obra_area: vacío (lo completa el usuario)
      - estado: placeholder hasta que se implemente validación SUNAT
      - confianza: float 0-1 (normalizado del enum alta/media/baja del LLM)
    """
    tipo_doc_nombre = campos.get("tipo_doc", "Factura")
    tipo_doc_codigo = _get_tipo_doc_codigo(tipo_doc_nombre)

    confianza_str = campos.get("confianza", "media")
    if confianza_str == "alta":
        confianza_float = 0.95
    elif confianza_str == "baja":
        confianza_float = 0.60
    else:
        confianza_float = 0.80

    return {
        "fecha_emision":   campos.get("fecha_emision"),
        "ruc":             campos.get("ruc"),
        "proveedor":       campos.get("proveedor"),
        "tipo_doc_codigo": tipo_doc_codigo,
        "tipo_doc_nombre": tipo_doc_nombre,
        "serie":           campos.get("serie"),
        "numero":          campos.get("numero"),
        "concepto":        campos.get("concepto"),
        "moneda":          campos.get("moneda", "PEN"),
        "monto_total":     campos.get("monto_total"),
        "monto_tributo":   campos.get("monto_tributo"),
        "obra_area":       "",  # lo completa el usuario
        "estado":          "Por implementar validación",  # futuro: SUNAT
        "confianza":       confianza_float,
    }


# ─────────────────────────────────────────────────────────────────────────
# Extracción por tipo de archivo
# ─────────────────────────────────────────────────────────────────────────

def _extract_via_vision(file_bytes: bytes, mime_type: str, api_key: str, prompt: str) -> tuple[dict, str]:
    """Usa GPT-4o Vision para imágenes y PDFs convertidos a imagen."""
    b64 = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "model": "gpt-4o",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())

    raw = data["choices"][0]["message"]["content"].strip()
    # Limpiar markdown si la IA lo envuelve en ```json ... ```
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip()), raw


def _extract_from_excel(file_bytes: bytes) -> str:
    """Extrae texto de Excel y lo manda a OpenAI como texto plano."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        rows = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                line = "\t".join(str(c) if c is not None else "" for c in row)
                if line.strip():
                    rows.append(line)
        return "\n".join(rows)
    except ImportError:
        return ""


def _extract_from_pdf(file_bytes: bytes) -> str:
    """Extrae texto nativo de un PDF con pdfplumber."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    except ImportError:
        return ""


def _extract_from_docx(file_bytes: bytes) -> str:
    """Extrae texto de un documento Word."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return ""


def _text_to_campos(raw_text: str, api_key: str, prompt: str) -> tuple[dict, str]:
    """Envía texto plano a OpenAI para estructurar los campos."""
    payload = {
        "model": "gpt-4o",
        "max_tokens": 800,
        "messages": [
            {"role": "user", "content": prompt + f"\n\nContenido del documento:\n{raw_text[:6000]}"}
        ]
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())

    raw = data["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip()), raw_text


# ─────────────────────────────────────────────────────────────────────────
# Handler HTTP
# ─────────────────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return self._json(500, {"error": "OPENAI_API_KEY no configurada."})

        # Detectar modo: caja_chica (default) o factura.
        query_params = parse_qs(urlparse(self.path).query)
        tipo = (query_params.get("tipo") or ["caja_chica"])[0]
        prompt = _EXTRACTION_PROMPT_FACTURA if tipo == "factura" else _EXTRACTION_PROMPT_CAJA_CHICA

        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            # Parsear multipart para extraer el archivo
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(content_length),
            }
            fs = cgi.FieldStorage(
                fp=io.BytesIO(raw_body),
                environ=environ,
                keep_blank_values=True
            )

            file_item = fs.getvalue("file") if "file" in fs else None
            filename = ""
            if hasattr(fs["file"], "filename") if "file" in fs else False:
                filename = fs["file"].filename or ""
                file_bytes = fs["file"].file.read()
            elif file_item:
                file_bytes = file_item if isinstance(file_item, bytes) else file_item.encode()
            else:
                return self._json(400, {"error": "No se encontró el campo 'file' en el body."})

            ext = (filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

            campos = {}
            raw_text = ""

            # ── Ruteo por extensión ──────────────────────────────────────
            if ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
                mime = f"image/{ext if ext != 'jpg' else 'jpeg'}"
                campos, raw_text = _extract_via_vision(file_bytes, mime, api_key, prompt)

            elif ext == "pdf":
                # Intentar primero texto nativo; si hay suficiente contenido,
                # mandarlo como texto plano. Si no, fallback a Vision.
                text = _extract_from_pdf(file_bytes)
                if len(text.strip()) > 100:
                    campos, raw_text = _text_to_campos(text, api_key, prompt)
                else:
                    campos, raw_text = _extract_via_vision(file_bytes, "application/pdf", api_key, prompt)

            elif ext in ("xlsx", "xls"):
                text = _extract_from_excel(file_bytes)
                if text:
                    campos, raw_text = _text_to_campos(text, api_key, prompt)
                else:
                    return self._json(422, {"error": "No se pudo leer el Excel. Asegúrate de usar formato .xlsx"})

            elif ext in ("docx", "doc"):
                text = _extract_from_docx(file_bytes)
                if text:
                    campos, raw_text = _text_to_campos(text, api_key, prompt)
                else:
                    return self._json(422, {"error": "No se pudo leer el documento Word."})

            else:
                # Intentar como imagen genérica
                campos, raw_text = _extract_via_vision(file_bytes, "image/jpeg", api_key, prompt)

            # Modo factura: enriquecer con campos derivados (códigos, placeholders).
            if tipo == "factura":
                campos = _enrich_factura_data(campos)

            return self._json(200, {
                "campos": campos,
                "raw_text": raw_text[:500] if isinstance(raw_text, str) else "",
            })

        except json.JSONDecodeError as e:
            return self._json(422, {"error": f"No se pudo parsear la respuesta de IA: {e}"})
        except Exception as e:
            print(f"[parse_file] Error: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": f"Error al procesar el archivo: {type(e).__name__}"})

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
