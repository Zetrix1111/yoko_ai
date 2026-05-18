"""
Tool: consultar_aprobador

Consulta empleados habilitados como aprobadores de caja chica. Lo ejecuta el
orquestador llamando a `POST /api/solicitudes?action=consultar-aprobador-chat`.
"""

TOOL_DEFINITION: dict = {
    "type": "custom",
    "name": "consultar_aprobador",
    "description": (
        "Consulta la tabla Empleados y devuelve solo personas con rol de "
        "aprobación para caja chica. Úsala para mostrar nombres al usuario "
        "y obtener el record id necesario para crear la solicitud. Si la "
        "configuración indica dos o más aprobadores, llama una sola vez con "
        "rol='todos' para obtener residentes y aprobadores en la misma respuesta."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "rol": {
                "type": "string",
                "enum": ["APROBADOR_1", "APROBADOR_2", "todos"],
                "description": (
                    "APROBADOR_1 = residente opcional. "
                    "APROBADOR_2 = aprobador obligatorio. "
                    "todos = devuelve ambas listas en una sola llamada."
                ),
            },
            "buscar": {
                "type": "string",
                "description": "Texto opcional para filtrar por nombre o cargo.",
            },
        },
    },
}
