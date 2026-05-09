"""
Tool: yoko_recuperar_proceso

Consulta los detalles de un proceso ya creado (estado, facturas extraídas,
totales, alertas). Lo ejecuta el orquestador llamando a
`POST /api/facturas?action=recuperar-chat`.
"""

TOOL_DEFINITION: dict = {
    "name": "yoko_recuperar_proceso",
    "description": (
        "Consulta los detalles de un proceso ya creado (estado, facturas "
        "extraídas, totales, alertas). Útil cuando el usuario pregunta por "
        "un proceso anterior o cuando hay que revisar qué se procesó antes "
        "de generar el Excel."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "proceso_id": {
                "type": "string",
                "description": "ID del proceso a consultar.",
            },
        },
        "required": ["proceso_id"],
    },
}
