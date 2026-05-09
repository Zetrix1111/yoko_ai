"""
api/_yoko_agents/tools/

Cada submódulo declara una constante `TOOL_DEFINITION` con el shape que
espera la API de Managed Agents para custom tools:

    {"type": "custom", "name": "...", "description": "...", "input_schema": {...}}

Los tools NO se ejecutan en el sandbox de Anthropic. Cuando el agent dispara
un `agent.custom_tool_use`, el orquestador `api/_yoko/handler_managed.py`
lo intercepta y hace HTTP loopback al endpoint correspondiente de la
propia API Yoko en Vercel.

`recuperar_proceso` queda importado pero NO incluido en `ALL_TOOLS` —
decisión del owner: la activamos en una fase futura.
"""

from . import generar_registro_contable, procesar_archivos, recuperar_proceso  # noqa: F401


ALL_TOOLS: list[dict] = [
    procesar_archivos.TOOL_DEFINITION,
    generar_registro_contable.TOOL_DEFINITION,
    # recuperar_proceso.TOOL_DEFINITION,  # uso futuro — fuera del agent por ahora
]


__all__ = [
    "ALL_TOOLS",
    "generar_registro_contable",
    "procesar_archivos",
    "recuperar_proceso",
]
