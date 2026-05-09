"""
Tool: yoko_generar_registro_contable

Valida que el registro contable de un proceso esté listo para descargarse
y devuelve metadata para que el agent confirme al usuario. Lo ejecuta el
orquestador llamando a `POST /api/facturas?action=registro-contable-chat`,
que internamente usa el motor `_lib/registro_contable/engine.validate()`.

El motor resuelve el sistema contable (CONCAR/SISCONT/etc.) según
`Config_Empresa.basicos.sistema_contable` de la empresa. La descarga real
del .xlsx la hace el frontend via la pantalla "Facturas Inteligentes" (botón
de descarga existente) — esta tool NO devuelve los bytes al chat.
"""

TOOL_DEFINITION: dict = {
    "type": "custom",
    "name": "yoko_generar_registro_contable",
    "description": (
        "Confirma que el registro de compras/ventas (Excel del sistema "
        "contable de la empresa: CONCAR, SISCONT u otro) está listo para "
        "que el usuario lo descargue desde la pantalla Facturas Inteligentes. "
        "Devuelve metadata: sistema contable resuelto, número de comprobantes "
        "y filas estimadas. El agent debe llamar este tool solo cuando el "
        "usuario haya confirmado que terminó de revisar los comprobantes "
        "procesados y pida explícitamente generar/descargar el registro."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "proceso_id": {
                "type": "string",
                "description": (
                    "ID del proceso devuelto por yoko_procesar_archivos "
                    "(formato proc-XXXXXXXXXXXX)."
                ),
            },
        },
        "required": ["proceso_id"],
    },
}
