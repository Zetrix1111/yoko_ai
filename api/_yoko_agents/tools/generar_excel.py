"""
Tool: yoko_generar_excel

Genera el Excel del registro de compras/ventas en el formato contable de la
empresa (CONCAR para cmejia) a partir de un proceso ya validado. Lo ejecuta
el orquestador llamando a `POST /api/facturas?action=download-chat`.
"""

TOOL_DEFINITION: dict = {
    "name": "yoko_generar_excel",
    "description": (
        "Genera el Excel del registro de compras/ventas en el formato contable "
        "de la empresa (CONCAR/SISCONT/etc.) a partir de un proceso ya "
        "procesado. Devuelve una URL temporal de descarga."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "proceso_id": {
                "type": "string",
                "description": "ID del proceso devuelto por yoko_procesar_archivos.",
            },
        },
        "required": ["proceso_id"],
    },
}
