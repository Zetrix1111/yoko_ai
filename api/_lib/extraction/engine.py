"""
api/_lib/extraction/engine.py

Motor genérico de extracción. Reúne las funciones de bajo nivel que
hablan con OpenAI (Vision + texto plano) y los lectores de archivo
(PDF, Excel, Word) que antes vivían en `api/parse_file.py`.

API pública del módulo:
  - `extract_from_file(file_bytes, filename, prompt, api_key, **kwargs)`
    Rutea por extensión y devuelve `(campos, raw_text)`.
  - `extract_with_template(file_bytes, filename, template_name, api_key)`
    API de alto nivel: resuelve el template del registry, aplica el
    prompt + enrich opcional, y devuelve un dict normalizado.

Funciones privadas reusables (re-exportadas por `parse_file.py` para
compatibilidad legacy con `facturas_processor.py`):
  - `_extract_via_vision(file_bytes, mime_type, api_key, prompt, model, max_tokens)`
  - `_extract_from_excel(file_bytes)`
  - `_extract_from_pdf(file_bytes)`
  - `_extract_pdf_pages(file_bytes)`
  - `_extract_from_docx(file_bytes)`
  - `_text_to_campos(raw_text, api_key, prompt, model, max_tokens, text_limit)`

NOTA: las funciones de bajo nivel se copiaron literalmente desde
`parse_file.py` con un único cambio: parámetros opcionales `model`,
`max_tokens`, `text_limit` con defaults que matchean el comportamiento
hardcoded anterior (gpt-4o, 1000/800 tokens, 6000 chars). Esto permite
que cada template configure su modelo si lo necesita.
"""

import base64
import io
import json
import sys
import urllib.request


_DEFAULT_MODEL              = "gpt-4o"
_DEFAULT_MAX_TOKENS_VISION  = 1000
_DEFAULT_MAX_TOKENS_TEXT    = 800
_DEFAULT_TEXT_LIMIT         = 6000
_DEFAULT_PDF_TEXT_THRESHOLD = 100  # chars de texto nativo necesarios para no caer en Vision


# ─────────────────────────────────────────────────────────────────────────
# Funciones de bajo nivel (movidas literalmente desde parse_file.py)
# ─────────────────────────────────────────────────────────────────────────

def _extract_via_vision(
    file_bytes: bytes,
    mime_type: str,
    api_key: str,
    prompt: str,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS_VISION,
) -> tuple[dict, str]:
    """Usa GPT-4o Vision para imágenes y PDFs convertidos a imagen."""
    b64 = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "model": model,
        "max_tokens": max_tokens,
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
    """
    Extrae texto nativo de un PDF con pdfplumber, concatenando todas las
    páginas con \\n. Para flujos que necesitan procesar página por página
    (ej. PDF con múltiples facturas), usar `_extract_pdf_pages`.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    except ImportError:
        return ""


def _extract_pdf_pages(file_bytes: bytes) -> list[str]:
    """
    Como `_extract_from_pdf` pero devuelve una lista con el texto de cada
    página por separado. Útil cuando un PDF contiene múltiples documentos
    independientes (ej. lote de facturas) y queremos procesar cada página
    como un documento aparte.

    Devuelve [] si pdfplumber no está disponible o si el archivo no se
    puede abrir.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except ImportError:
        return []
    except Exception as e:
        print(f"[extraction.engine] _extract_pdf_pages falló: {e}", file=sys.stderr)
        return []


def _extract_from_docx(file_bytes: bytes) -> str:
    """Extrae texto de un documento Word."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return ""


def _text_to_campos(
    raw_text: str,
    api_key: str,
    prompt: str,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS_TEXT,
    text_limit: int = _DEFAULT_TEXT_LIMIT,
) -> tuple[dict, str]:
    """Envía texto plano a OpenAI para estructurar los campos."""
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt + f"\n\nContenido del documento:\n{raw_text[:text_limit]}"}
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
# API pública: ruteo por tipo de archivo
# ─────────────────────────────────────────────────────────────────────────

def extract_from_file(
    file_bytes: bytes,
    filename: str,
    prompt: str,
    api_key: str,
    *,
    model: str = _DEFAULT_MODEL,
    max_tokens_vision: int = _DEFAULT_MAX_TOKENS_VISION,
    max_tokens_text: int = _DEFAULT_MAX_TOKENS_TEXT,
    text_limit: int = _DEFAULT_TEXT_LIMIT,
    pdf_text_threshold: int = _DEFAULT_PDF_TEXT_THRESHOLD,
) -> tuple[dict, str]:
    """
    Rutea por extensión y devuelve (campos, raw_text).

    - Imágenes (jpg/jpeg/png/gif/webp/bmp) → `_extract_via_vision`.
    - PDF → primero intenta texto nativo (pdfplumber). Si tiene >threshold
      caracteres, usa `_text_to_campos`. Si no, fallback a Vision.
    - Excel (xlsx/xls) → `_extract_from_excel` + `_text_to_campos`. Si no
      se puede leer el archivo, lanza ValueError.
    - Word (docx/doc) → `_extract_from_docx` + `_text_to_campos`. Si no se
      puede leer, lanza ValueError.
    - Otros → fallback a Vision como image/jpeg.
    """
    ext = (filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
        mime = f"image/{ext if ext != 'jpg' else 'jpeg'}"
        return _extract_via_vision(file_bytes, mime, api_key, prompt, model=model, max_tokens=max_tokens_vision)

    if ext == "pdf":
        text = _extract_from_pdf(file_bytes)
        if len(text.strip()) > pdf_text_threshold:
            return _text_to_campos(text, api_key, prompt, model=model, max_tokens=max_tokens_text, text_limit=text_limit)
        # PDF escaneado o sin texto: fallback a Vision sobre el PDF directo.
        return _extract_via_vision(file_bytes, "application/pdf", api_key, prompt, model=model, max_tokens=max_tokens_vision)

    if ext in ("xlsx", "xls"):
        text = _extract_from_excel(file_bytes)
        if not text:
            raise ValueError("No se pudo leer el Excel. Asegúrate de usar formato .xlsx")
        return _text_to_campos(text, api_key, prompt, model=model, max_tokens=max_tokens_text, text_limit=text_limit)

    if ext in ("docx", "doc"):
        text = _extract_from_docx(file_bytes)
        if not text:
            raise ValueError("No se pudo leer el documento Word.")
        return _text_to_campos(text, api_key, prompt, model=model, max_tokens=max_tokens_text, text_limit=text_limit)

    # Fallback: tratar como imagen genérica.
    return _extract_via_vision(file_bytes, "image/jpeg", api_key, prompt, model=model, max_tokens=max_tokens_vision)


# ─────────────────────────────────────────────────────────────────────────
# API de alto nivel: extract_with_template
# ─────────────────────────────────────────────────────────────────────────

def extract_with_template(
    file_bytes: bytes,
    filename: str,
    template_name: str,
    api_key: str,
) -> dict:
    """
    Extrae datos usando un template registrado.

    Resuelve `template_name` en el registry, lee del módulo del template
    los atributos PROMPT (obligatorio), MODEL, MAX_TOKENS_VISION,
    MAX_TOKENS_TEXT (opcionales con defaults), y opcionalmente la
    función `enrich(campos)` que post-procesa los campos.

    Returns:
        {
            "campos":   <dict post-enrich>,
            "raw_text": <str, primeros 500 chars>,
            "template": <str>,
        }

    Raises:
        ValueError si el template no existe.
    """
    # Import local para evitar ciclo engine ↔ registry.
    from .registry import get_template

    template = get_template(template_name)

    prompt            = template.PROMPT
    model             = getattr(template, "MODEL", _DEFAULT_MODEL)
    max_tokens_vision = getattr(template, "MAX_TOKENS_VISION", _DEFAULT_MAX_TOKENS_VISION)
    max_tokens_text   = getattr(template, "MAX_TOKENS_TEXT", _DEFAULT_MAX_TOKENS_TEXT)

    campos, raw_text = extract_from_file(
        file_bytes,
        filename,
        prompt,
        api_key,
        model=model,
        max_tokens_vision=max_tokens_vision,
        max_tokens_text=max_tokens_text,
    )

    # Post-procesamiento opcional definido por el template.
    enrich_fn = getattr(template, "enrich", None)
    if callable(enrich_fn):
        campos = enrich_fn(campos)

    raw_preview = raw_text[:500] if isinstance(raw_text, str) else ""
    return {
        "campos":   campos,
        "raw_text": raw_preview,
        "template": template_name,
    }
