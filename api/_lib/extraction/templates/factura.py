"""
api/_lib/extraction/templates/factura.py

Template para comprobantes de pago peruanos: factura, boleta, nota de
crédito/débito, recibo por honorarios, boleto aéreo, ticket.

PROMPT, _TIPO_DOC_MAP y `enrich` son copias literales (byte-por-byte) de
las constantes y funciones que vivían en `api/parse_file.py` antes del
refactor. NO modificar la lógica — está calibrada en producción.
"""


NAME = "factura"
DESCRIPTION = (
    "Comprobantes de pago peruanos: factura, boleta, nota de crédito/débito, "
    "recibo por honorarios, boleto aéreo, ticket."
)
MODEL = "gpt-4o"
MAX_TOKENS_VISION = 1000
MAX_TOKENS_TEXT = 800


PROMPT = """Eres un asistente experto en extraer datos de comprobantes de pago peruanos (facturas, boletas, notas de crédito/débito, recibos por honorarios).

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
_TIPO_DOC_MAP = {
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


def _get_tipo_doc_codigo(tipo_nombre: str) -> str:
    """
    Convierte nombre de tipo de documento a código interno de 2 letras.
    Default a "FT" (Factura) si el nombre no calza con el mapeo.
    """
    if not tipo_nombre:
        return "FT"
    return _TIPO_DOC_MAP.get(tipo_nombre.lower().strip(), "FT")


def enrich(campos: dict) -> dict:
    """
    Enriquece los datos extraídos de una factura con campos derivados:
      - tipo_doc_codigo: 2 letras (FT, BV, NC, ND, BA, RH, TK)
      - tipo_doc_nombre: nombre completo para display
      - centro_costo: vacío (lo completa el usuario)
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
        "centro_costo":    "",  # lo completa el usuario
        "estado":          "Por implementar validación",  # futuro: SUNAT
        "confianza":       confianza_float,
    }
