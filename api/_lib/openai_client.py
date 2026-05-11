"""
Cliente OpenAI con loop de tool calling para gpt-4.1-mini-2025-04-14.
Agnóstico del agente: cada caller (Yoko o ventas) le pasa SU `executor`.

`run_chat` orquesta la conversación:
  1. Arranca con [system_prompt, ...messages] como contexto.
  2. Llama al modelo con las tools.
  3. Si el modelo pide ejecutar tools, las corre vía el `executor`
     pasado, reinyecta los resultados como mensajes de rol "tool" y
     vuelve a llamar al modelo.
  4. Cuando el modelo responde sin tool_calls → termina y devuelve
     `{"text": <respuesta>, "action": <ultima _action capturada o None>}`.

`_action` es un dict que las tools de navegación (y cualquier otra que
quiera mover el frontend) devuelven con la forma:
    {"type": "navigate", "path": "/modulos/...", "params": {...}}
La cliente captura la última y la incluye en la respuesta final para
que el frontend pueda hacer el routing además de mostrar el texto.

`_media_urls` es una lista de URLs públicas (imágenes) que las tools
pueden devolver para que el caller las propague al cliente final.
Lo usa el cerebro de ventas (tool `enviar_fotos_productos`) para que
bot-baileys mande las imágenes nativas por WhatsApp. Si varias tools
en un mismo turno emiten URLs, se acumulan en orden de aparición.
"""

import json
import os
import sys
from typing import Callable

from openai import OpenAI


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
    executor: ToolExecutor,
    max_iterations: int = 6,
) -> dict:
    """
    Ejecuta el loop de chat con tool calling. Devuelve dict con la
    forma `{"text": str, "action": dict | None}`.

    `messages` debe venir en el formato OpenAI:
        [{"role": "user"|"assistant", "content": "..."}]

    `tools` es la lista en formato OpenAI. Para Yoko viene de
    `yoko._lib.prompt.build_tools_list(config)`; para ventas, de
    `ventas._lib.tools.TOOLS_OPENAI`. Si está vacío, el modelo no puede
    llamar tools (chat plano).

    `context` se pasa tal cual al executor — típicamente
    `{"user": <dict>, "config": <dict>}` para Yoko, o
    `{"empresa_id": "..."}` para ventas.

    `executor` es la función que ejecuta tools. Cada caller pasa la
    suya: `yoko._lib.tool_registry.execute_tool` o
    `ventas._lib.tools.execute`. Mantiene este módulo agnóstico del
    agente que lo invoca.
    """
    full_messages: list[dict] = (
        [{"role": "system", "content": system_prompt}]
        + list(messages or [])
    )

    client = _client()
    captured_action: dict | None = None
    captured_media_urls: list[str] = []

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
                "text":       msg.content or "",
                "action":     captured_action,
                "media_urls": captured_media_urls,
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

            # Captura señales que el caller debe propagar al frontend:
            #   - _action: la última gana (siguiente sobrescribe).
            #   - _media_urls: se acumulan en orden.
            if isinstance(result, dict):
                if "_action" in result:
                    captured_action = result["_action"]
                if "_media_urls" in result and isinstance(result["_media_urls"], list):
                    for u in result["_media_urls"]:
                        if isinstance(u, str) and u.strip():
                            captured_media_urls.append(u.strip())

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
        "text":       _FALLBACK_MAX_ITER,
        "action":     captured_action,
        "media_urls": captured_media_urls,
    }
