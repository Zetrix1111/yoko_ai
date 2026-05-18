"""
Tool: consultar_centros_costo

Consulta centros de costo activos. Lo ejecuta el
orquestador llamando a `POST /api/solicitudes?action=consultar-centros-costo-chat`.
"""

TOOL_DEFINITION: dict = {
    "type": "custom",
    "name": "consultar_centros_costo",
    "description": (
        "Consulta y devuelve los centros de costo activos de "
        "la empresa. Úsala bajo demanda cuando la solicitud requiera centro "
        "de costo o cuando el usuario necesite elegir uno. No inventes "
        "centros de costo ni esperes recibir la lista completa en el contexto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}
