"""
Tool: consultar_solicitudes_por_dni

Lista solicitudes de caja chica por DNI. Lo ejecuta el orquestador llamando a
`POST /api/solicitudes?action=consultar-por-dni-chat`.
"""

TOOL_DEFINITION: dict = {
    "type": "custom",
    "name": "consultar_solicitudes_por_dni",
    "description": (
        "Consulta las solicitudes de caja chica del usuario autenticado por "
        "DNI, con filtros opcionales de estado y periodo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "dni": {
                "type": "string",
                "description": "DNI del solicitante.",
            },
            "estado": {
                "type": "string",
                "enum": [
                    "pendiente_aprobacion",
                    "por_pagar",
                    "por_contabilizar",
                    "por_rendir",
                    "finalizado",
                    "rechazado",
                ],
                "description": "Filtro opcional por etapa del ciclo.",
            },
            "periodo": {
                "type": "string",
                "description": "Mes en formato YYYY-MM.",
            },
        },
        "required": ["dni"],
    },
}
