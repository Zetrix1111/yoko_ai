"""
api/_yoko_agents/tools/

Cada submódulo declara una constante `TOOL_DEFINITION` con el JSON Schema
del tool (formato Anthropic API).

Los tools NO se ejecutan en el sandbox de Anthropic. Cuando el agent dispara
un `tool_use`, el orquestador (api/_yoko/handler_managed.py — Etapa F) lo
intercepta y hace HTTP al endpoint correspondiente de la propia API Yoko
en Vercel.
"""

from . import generar_excel, procesar_archivos, recuperar_proceso


ALL_TOOLS: list[dict] = [
    procesar_archivos.TOOL_DEFINITION,
    generar_excel.TOOL_DEFINITION,
    recuperar_proceso.TOOL_DEFINITION,
]


__all__ = ["ALL_TOOLS", "procesar_archivos", "generar_excel", "recuperar_proceso"]
