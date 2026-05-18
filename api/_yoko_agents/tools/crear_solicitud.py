"""
Tool: yoko_crear_solicitud

Registra una solicitud de caja chica. Lo ejecuta el orquestador llamando a
`POST /api/solicitudes?action=crear-chat`.
"""

TOOL_DEFINITION: dict = {
    "type": "custom",
    "name": "yoko_crear_solicitud",
    "description": (
        "Crea una nueva solicitud de caja chica después de que el usuario "
        "confirmó el resumen. Valida reglas de negocio en backend antes de "
        "escribir en Airtable."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "plazo": {
                "type": "string",
                "description": "Plazo para la caja chica, por ejemplo cantidad de días o fecha desde/hasta.",
            },
            "motivo": {
                "type": "string",
                "description": "Motivo general de la solicitud.",
            },
            "moneda": {
                "type": "string",
                "enum": ["PEN", "USD", "EUR", "CNY"],
                "description": "Moneda de la solicitud.",
            },
            "centro_costo": {
                "type": "string",
                "description": "Centro de costo asociado, si aplica.",
            },
            "total_general": {
                "type": "number",
                "description": "Monto total solicitado.",
            },
            "detalle_gasto": {
                "type": "string",
                "description": "Descripción detallada del gasto a realizar.",
            },
            "aprobador_id": {
                "type": "string",
                "description": (
                    "Record ID del APROBADOR_2 elegido por el usuario. "
                    "Obtén este id con consultar_aprobador antes de crear la solicitud."
                ),
            },
            "residente_id": {
                "type": "string",
                "description": (
                    "Record ID del APROBADOR_1/residente si corresponde. "
                    "Solo enviarlo si el usuario eligió residente."
                ),
            },
        },
        "required": ["plazo", "motivo", "moneda", "total_general", "detalle_gasto", "aprobador_id"],
    },
}
