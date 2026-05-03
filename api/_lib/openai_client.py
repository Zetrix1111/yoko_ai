"""
Cliente OpenAI con loop de tool calling para gpt-4.1-mini-2025-04-14.

`run_chat` orquesta la conversación:
  1. Arranca con [system_prompt, ...messages] como contexto.
  2. Llama al modelo con las tools.
  3. Si el modelo pide ejecutar tools, las corre vía tool_registry,
     reinyecta los resultados como mensajes de rol "tool" y vuelve a
     llamar al modelo.
  4. Cuando el modelo responde sin tool_calls → termina y devuelve
     `{"text": <respuesta>, "action": <ultima _action capturada o None>}`.

`_action` es un dict que las tools de navegación (y cualquier otra que
quiera mover el frontend) devuelven con la forma:
    {"type": "navigate", "path": "/modulos/...", "params": {...}}
La cliente captura la última y la incluye en la respuesta final para
que el frontend pueda hacer el routing además de mostrar el texto.
"""

import json
import os
import sys
from typing import Callable

from openai import OpenAI

from . import tool_registry


_MODEL = "gpt-4.1-mini-2025-04-14"

# Tipo del executor de tools: callable(name, args, context) -> dict
ToolExecutor = Callable[[str, dict, dict], dict]

_FALLBACK_MAX_ITER = (
    "Lo siento, no pude resolver tu pedido en los pasos disponibles. "
    "Intenta reformularlo o pregúntame algo más simple."
)


def _client() -> OpenAI:
    """Construye el cliente OpenAI leyendo OPENAI_API_KEY del entorno."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no está configurado en el entorno.")
    return OpenAI(api_key=api_key)


def run_chat(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    context: dict,
    max_iterations: int = 6,
    executor: ToolExecutor | None = None,
) -> dict:
    """
    Ejecuta el loop de chat con tool calling. Devuelve dict con la
    forma `{"text": str, "action": dict | None}`.

    `messages` debe venir en el formato OpenAI:
        [{"role": "user"|"assistant", "content": "..."}]

    `tools` viene de `prompt_builder.build_tools_list(config)` para Yoko,
    o de `tools.ventas.VENTAS_TOOLS_OPENAI` para el agente de ventas.
    Si está vacío, el modelo no puede llamar tools (chat plano).

    `context` se pasa tal cual al executor — típicamente
    `{"user": <dict>, "config": <dict>}` para Yoko, o
    `{"empresa_id": "..."}` para ventas.

    `executor` es la función que ejecuta tools. Default: `tool_registry.execute_tool`
    (registry global de Yoko). Para el agente de ventas pasar
    `tools.ventas.execute_ventas_tool` para evitar contaminar el registry global.
    """
    if executor is None:
        executor = tool_registry.execute_tool
    full_messages: list[dict] = (
        [{"role": "system", "content": system_prompt}]
        + list(messages or [])
    )

    client = _client()
    captured_action: dict | None = None

    for iteration in range(max_iterations):
        kwargs = {
            "model":    _MODEL,
            "messages": full_messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        # Caso 1: el modelo respondió texto sin pedir tools → terminamos
        if not msg.tool_calls:
            return {
                "text":   msg.content or "",
                "action": captured_action,
            }

        # Caso 2: el modelo pidió tools. Append del assistant turn (con
        # tool_calls) y luego un mensaje "tool" por cada resultado.
        full_messages.append({
            "role":    "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id":   tc.id,
                    "type": "function",
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            result = executor(tc.function.name, args, context)

            # Captura la última _action (la siguiente sobrescribe).
            if isinstance(result, dict) and "_action" in result:
                captured_action = result["_action"]

            full_messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      json.dumps(result, ensure_ascii=False, default=str),
            })

        # Continuar el loop para que el modelo procese los resultados.

    # Llegamos al límite sin que el modelo cierre con texto.
    print(
        f"[openai_client] run_chat alcanzó max_iterations={max_iterations} "
        f"sin respuesta final. Devolviendo fallback.",
        file=sys.stderr,
    )
    return {
        "text":   _FALLBACK_MAX_ITER,
        "action": captured_action,
    }
