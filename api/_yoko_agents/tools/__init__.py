"""
api/_yoko_agents/tools/

Cada submódulo declara una constante `TOOL_DEFINITION` con el shape que
espera la API de Managed Agents para custom tools:

    {"type": "custom", "name": "...", "description": "...", "input_schema": {...}}

Los tools NO se ejecutan en el sandbox de Anthropic. Cuando el agent dispara
un `agent.custom_tool_use`, el orquestador `api/_yoko/handler_managed.py`
lo intercepta y hace HTTP loopback al endpoint correspondiente de la
propia API Yoko en Vercel.

`recuperar_proceso` se incluye porque el skill `facturas-inteligentes`
permite consultar procesos anteriores por `proc-...`.
Las tools de `solicitud-caja` se declaran acá para que el agente Managed
vea el mismo contrato funcional que el registry legacy de OpenAI.
"""

from . import (  # noqa: F401
    consultar_aprobador,
    consultar_centros_costo,
    consultar_solicitud_por_id,
    consultar_solicitudes_por_dni,
    crear_solicitud,
    generar_registro_contable,
    procesar_archivos,
    procesar_solicitud_caja,
    recuperar_proceso,
)


ALL_TOOLS: list[dict] = [
    procesar_archivos.TOOL_DEFINITION,
    generar_registro_contable.TOOL_DEFINITION,
    recuperar_proceso.TOOL_DEFINITION,
    procesar_solicitud_caja.TOOL_DEFINITION,
    crear_solicitud.TOOL_DEFINITION,
    consultar_solicitud_por_id.TOOL_DEFINITION,
    consultar_solicitudes_por_dni.TOOL_DEFINITION,
    consultar_aprobador.TOOL_DEFINITION,
    consultar_centros_costo.TOOL_DEFINITION,
]


__all__ = [
    "ALL_TOOLS",
    "consultar_aprobador",
    "consultar_centros_costo",
    "consultar_solicitud_por_id",
    "consultar_solicitudes_por_dni",
    "crear_solicitud",
    "generar_registro_contable",
    "procesar_archivos",
    "procesar_solicitud_caja",
    "recuperar_proceso",
]
