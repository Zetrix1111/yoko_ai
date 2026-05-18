"""
Tool: yoko_procesar_solicitud_caja

Procesa documentos de solicitud de caja chica con el template `caja_chica`.
Lo ejecuta el orquestador llamando a
`POST /api/solicitudes?action=procesar-solicitud-caja-chat`.
"""

TOOL_DEFINITION: dict = {
    "type": "custom",
    "name": "yoko_procesar_solicitud_caja",
    "description": (
        "Procesa documentos adjuntos de solicitud de caja chica (PDF, imagen, "
        "Excel o Word) usando el template caja_chica. Devuelve campos "
        "extraídos como motivo, centro_costo, total_general, moneda, plazo y "
        "detalle_gasto para que el agente confirme con el usuario."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "description": (
                    "Lista opcional de archivos con filename/content_b64. "
                    "En Yoko normalmente se omite porque el orquestador "
                    "inyecta el carrito de la sesión."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content_b64": {"type": "string"},
                    },
                },
            },
        },
    },
}
