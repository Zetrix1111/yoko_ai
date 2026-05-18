"""
Tool: consultar_solicitud_por_id

Busca una solicitud de caja chica por folio o record id. Lo ejecuta el
orquestador llamando a `POST /api/solicitudes?action=consultar-por-id-chat`.
"""

TOOL_DEFINITION: dict = {
    "type": "custom",
    "name": "consultar_solicitud_por_id",
    "description": (
        "Busca una solicitud de caja chica específica por folio NUMERO o por "
        "ID interno de Airtable. Úsala cuando el usuario da un identificador "
        "concreto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "Folio o ID interno de Airtable de la solicitud.",
            },
        },
        "required": ["id"],
    },
}
