"""
api/_lib/extraction/templates/caja_chica.py

Template para extraer campos de una solicitud de caja chica.

PROMPT es copia literal (byte-por-byte) de la constante
`_EXTRACTION_PROMPT_CAJA_CHICA` que vivía en `api/parse_file.py` antes
del refactor. NO modificar — está calibrada en producción.

Caja chica NO tiene función `enrich`: los campos extraídos son los
finales, no requieren post-procesamiento.
"""


NAME = "caja_chica"
DESCRIPTION = (
    "Solicitud de caja chica: extrae motivo, centro de costo, monto total, moneda, "
    "plazo y detalle."
)
MODEL = "gpt-4o"
MAX_TOKENS_VISION = 1000
MAX_TOKENS_TEXT = 800


PROMPT = """Eres un asistente experto en extraer datos de documentos para solicitudes de caja chica.

Analiza el documento/imagen adjunto y extrae los siguientes campos si están presentes:
- motivo: Descripción general del gasto o propósito de la solicitud
- centro_costo: Centro de costo asociado
- total_general: Monto total numérico (sin símbolos de moneda)
- moneda: PEN, USD, EUR o CNY (infiere desde el contexto)
- plazo: Período de tiempo o fechas (ej. "Del 01/05 al 31/05")
- detalle_gasto: Lista de ítems de gasto con montos

Responde ÚNICAMENTE con un JSON con esta estructura exacta (usa null para campos no encontrados):
{
  "motivo": "...",
  "centro_costo": "...",
  "total_general": 0.0,
  "moneda": "PEN",
  "plazo": "...",
  "detalle_gasto": "...",
  "confianza": "alta|media|baja"
}

"confianza" debe ser:
- "alta" si la mayoría de campos están claramente presentes
- "media" si algunos campos hay que inferirlos
- "baja" si el documento no es relevante o tiene muy poca información
"""
