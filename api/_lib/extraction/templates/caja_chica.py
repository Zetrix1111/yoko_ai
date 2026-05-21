"""
api/_lib/extraction/templates/caja_chica.py

Template para extraer campos de una solicitud de caja chica.

Caja chica NO tiene función `enrich`: los campos extraídos son los
finales, no requieren post-procesamiento.
"""


NAME = "caja_chica"
DESCRIPTION = (
    "Solicitud de caja chica: extrae tipo, motivo, centro de costo, monto total, "
    "moneda, plazo y array detallado de ítems."
)
MODEL = "gpt-4o"
MAX_TOKENS_VISION = 1500
MAX_TOKENS_TEXT = 1200


PROMPT = """Eres un asistente experto en extraer datos de documentos para solicitudes de caja chica.

Analiza el documento/imagen adjunto y extrae los siguientes campos si están presentes:
- tipo: clasifica la solicitud como "CAJA CHICA", "EXTRAORDINARIO" o "PASAJES AEREOS". Heurística:
    * si el documento contiene pasajes aéreos, boletos de avión, vuelos, aerolíneas o destinos → "PASAJES AEREOS"
    * si el documento dice "extraordinaria"/"extraordinario" o el monto es inusualmente alto para gastos cotidianos → "EXTRAORDINARIO"
    * default: "CAJA CHICA"
- motivo: Descripción general del gasto o propósito de la solicitud
- centro_costo: Centro de costo asociado
- total_general: Monto total numérico (sin símbolos de moneda)
- moneda: PEN, USD, EUR o CNY (infiere desde el contexto)
- plazo: Período de tiempo o fechas (ej. "Del 01/05 al 31/05")
- detalle_gasto: ARRAY de ítems individuales del documento. Cada ítem tiene:
    * descripcion: qué es (ej. "LUZ", "AGUA", "Pasaje Lima-Iquitos")
    * unidad: unidad de medida (ej. "UND", "GLB", "KG"). Default "UND" si no se indica.
    * cantidad: cantidad numérica (ej. "1", "2"). Default "1" si no se indica.
    * precio_unitario: precio unitario numérico (sin símbolo de moneda)
    * total: total de la fila (cantidad × precio_unitario) numérico
    * proveedor: nombre del proveedor si aparece (ej. "PLUZ", "SEDAPAL"); si no aparece, null

Responde ÚNICAMENTE con un JSON con esta estructura exacta (usa null para campos no encontrados, y [] para detalle_gasto si no hay ítems):
{
  "tipo": "CAJA CHICA",
  "motivo": "...",
  "centro_costo": "...",
  "total_general": 0.0,
  "moneda": "PEN",
  "plazo": "...",
  "detalle_gasto": [
    {"descripcion": "...", "unidad": "UND", "cantidad": "1", "precio_unitario": "40", "total": "40.00", "proveedor": "..."}
  ],
  "confianza": "alta|media|baja"
}

"confianza" debe ser:
- "alta" si la mayoría de campos están claramente presentes y los ítems están bien tabulados
- "media" si algunos campos hay que inferirlos o los ítems no están claros
- "baja" si el documento no es relevante o tiene muy poca información
"""
