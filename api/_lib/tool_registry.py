"""
Registry global de tools para function calling de OpenAI.

Las tools se registran con el decorador `@register(...)` en módulos como
`api/_lib/tools/consulta.py`. El decorador puebla el dict global TOOLS,
que luego consume el handler de chat:

  • `get_openai_tools_array(modules_enabled)` → lista de tool definitions
    para pasar a la llamada `client.chat.completions.create(tools=...)`.
  • `execute_tool(name, arguments, context)` → ejecuta el handler de la
    tool y maneja errores (ValidationError vs. internos).

Cada tool registrada queda como:
    TOOLS[name] = {
        "description": str,
        "parameters":  dict (JSON Schema),
        "category":    str ("consulta" | "accion" | "navegacion"),
        "handler":     callable(args, context) → dict,
    }

Importante: para que las tools queden registradas, sus módulos deben
ser IMPORTADOS al menos una vez (el side-effect del decorador). El
handler de chat hace `import api._lib.tools.consulta` (etc.) en su top.
"""

from .validators import ValidationError


# Registro global. Poblado por @register en los módulos de tools/.
TOOLS: dict[str, dict] = {}


def register(name: str, description: str, parameters: dict, category: str):
    """
    Decorador que registra una tool. Uso:

        @register(
            name="consultar_solicitudes_por_dni",
            description="...",
            parameters={"type": "object", "properties": {...}, "required": [...]},
            category="consulta",
        )
        def consultar_solicitudes_por_dni(args, context):
            ...
            return {"solicitudes": [...]}

    El handler recibe siempre `(args: dict, context: dict)` y debe
    devolver un dict serializable a JSON.
    """
    def decorator(handler):
        if name in TOOLS:
            raise ValueError(f"Tool '{name}' ya está registrada.")
        TOOLS[name] = {
            "description": description,
            "parameters":  parameters,
            "category":    category,
            "handler":     handler,
        }
        return handler
    return decorator


def get_openai_tools_array(modules_enabled: list[str]) -> list[dict]:
    """
    Devuelve todas las tools registradas en el formato que espera la API
    de OpenAI Chat Completions (`tools=[...]`).

    Forma de cada item:
        {"type": "function", "function": {"name", "description", "parameters"}}

    TODO: filtrar por `modules_enabled` cuando definamos el mapeo
    módulo → tools. Por ahora se devuelven todas las registradas; el
    parámetro queda en la firma para no romper a los consumidores cuando
    se implemente el filtro.
    """
    _ = modules_enabled  # noqa: F841 — pendiente de uso
    return [
        {
            "type": "function",
            "function": {
                "name":        name,
                "description": tool["description"],
                "parameters":  tool["parameters"],
            },
        }
        for name, tool in TOOLS.items()
    ]


def execute_tool(name: str, arguments: dict, context: dict) -> dict:
    """
    Ejecuta el handler de la tool indicada y maneja errores.

    Retornos:
      - éxito                 → lo que devuelva el handler (dict)
      - tool inexistente      → {"error": "interno",    "detail": "..."}
      - ValidationError       → {"error": "validacion", "detail": "..."}
      - cualquier otra excep. → {"error": "interno",    "detail": "..."}
    """
    tool = TOOLS.get(name)
    if tool is None:
        return {
            "error":  "interno",
            "detail": f"Tool '{name}' no está registrada.",
        }

    handler = tool["handler"]
    try:
        result = handler(arguments or {}, context or {})
        if not isinstance(result, dict):
            return {
                "error":  "interno",
                "detail": f"La tool '{name}' devolvió un valor no-dict: {type(result).__name__}.",
            }
        return result
    except ValidationError as e:
        return {"error": "validacion", "detail": str(e)}
    except Exception as e:
        # Logueamos el tipo en stderr para diagnóstico, pero al LLM le
        # mandamos un resumen genérico (sin stack trace).
        import sys
        print(f"[tool_registry] Error en '{name}': {type(e).__name__}: {e}", file=sys.stderr)
        return {"error": "interno", "detail": f"{type(e).__name__}: {e}"}
