"""
Tools del módulo `facturas-inteligentes` para el cerebro tradicional
de Yoko (OpenAI function calling).

Reemplazan funcionalmente a los custom tools de Anthropic Managed
Agents en `api/_yoko_agents/tools/`. Los endpoints HTTP (action=*-chat)
de `api/facturas.py` son los mismos para ambos cerebros — lo que cambia
es solo el "wrapper": acá usamos `@register` (registry global de
OpenAI) en vez de `TOOL_DEFINITION` (schema Anthropic).

Diseño:
  - `yoko_procesar_archivos(tipo, mes, files?)` — lee el carrito de la sesión actual,
    postea a `/api/facturas?action=procesar-chat` con los archivos en
    `session_id_for_cart`. Vacía el carrito si OK.
  - `yoko_generar_registro_contable(proceso_id)` — confirma que el Excel
    está listo para descargar; devuelve `download_marker`.
  - `yoko_recuperar_proceso(proceso_id)` — consulta detalles de un proceso
    previo (estado, comprobantes, alertas).
  - `cancelar_carrito()` — vacía el carrito explícitamente cuando el
    usuario expresa intención #3 del SKILL.

Reuso de infra existente:
  - `_lib/yoko_cart_store` mantiene el carrito en KV.
  - `_lib/tool_executor.execute_local_tool` hace el HTTP loopback con
    auth (mismo módulo que `handler_worker.py` de Managed).

Importante: para que las tools queden registradas en
`_yoko/_lib/tool_registry.TOOLS`, este módulo DEBE ser importado al
menos una vez. El import vive en `_yoko/_lib/prompt.py:build_tools_list`
junto con consulta/accion/navegacion.
"""

from _lib import tool_executor, yoko_cart_store
from _yoko._lib.tool_registry import register


# ─────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────

def _get_context_session(context: dict) -> str:
    """Devuelve `session_id_for_cart` del context, o '' si no está."""
    return (context or {}).get("session_id_for_cart") or ""


def _get_context_auth(context: dict) -> str:
    """Devuelve el header `Authorization` del context, o '' si no está."""
    return (context or {}).get("auth_header") or ""


# ─────────────────────────────────────────────────────────────────────────
# 1. yoko_procesar_archivos
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="yoko_procesar_archivos",
    description=(
        "Procesa el lote de comprobantes acumulados en el carrito de la "
        "sesión actual (que el usuario adjuntó turno a turno). Invocala "
        "SOLO cuando el usuario confirme que terminó de mandar archivos "
        "Y confirme el tipo (compra/venta) + mes. Devuelve `proceso_id` "
        "(formato proc-XXXXXXXXXXXX) y `revision_marker` que tu próxima "
        "respuesta DEBE incluir al final en línea aparte, EXACTAMENTE "
        "como `[ABRIR_REVISION:proc-xxx]` — sin backticks, sin emojis "
        "pegados, sin paréntesis. El frontend lo detecta y renderiza un "
        "botón clickeable que lleva a la pantalla de revisión."
    ),
    parameters={
        "type": "object",
        "properties": {
            "tipo": {
                "type": "string",
                "enum": ["compra", "venta"],
                "description": "Si los comprobantes son de compras o de ventas.",
            },
            "mes": {
                "type": "string",
                "pattern": r"^\d{4}-\d{2}$",
                "description": "Mes contable de los comprobantes en formato YYYY-MM.",
            },
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
        "required": ["tipo", "mes"],
    },
    category="accion",
)
def yoko_procesar_archivos(args: dict, context: dict) -> dict:
    session_id = _get_context_session(context)
    auth_header = _get_context_auth(context)

    # Mismo patrón que `handler_worker._run_turn_streaming`:
    # pasar `session_id_for_cart` al endpoint para que extraiga los
    # archivos del carrito del lado server.
    tool_input = {
        "tipo":                args["tipo"],
        "mes":                 args["mes"],
        "session_id_for_cart": session_id,
    }
    result = tool_executor.execute_local_tool(
        "procesar-chat", tool_input, auth_header,
    )

    # Si el procesamiento fue OK, vaciar el carrito (idem
    # handler_worker:226-243). Si falla, mantenemos los archivos para
    # que el usuario pueda reintentar sin reuploadearlos.
    if isinstance(result, dict) and result.get("ok") is True and session_id:
        try:
            yoko_cart_store.clear_cart(session_id)
        except Exception:
            pass

    return result


# ─────────────────────────────────────────────────────────────────────────
# 2. yoko_generar_registro_contable
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="yoko_generar_registro_contable",
    description=(
        "Confirma que el registro de compras o ventas (Excel del sistema "
        "contable de la empresa: CONCAR, SISCONT u otro) está listo para "
        "que el usuario lo descargue. Devuelve metadata: sistema contable "
        "resuelto, número de comprobantes, filas estimadas, y un "
        "`download_marker` que tu próxima respuesta DEBE incluir al final "
        "en línea aparte, EXACTAMENTE como `[DESCARGAR_REGISTRO:proc-xxx]` "
        "— sin backticks, sin emojis pegados, sin paréntesis. El frontend "
        "renderiza un botón 'Descargar registro contable'. "
        "Llamala SOLO cuando el usuario confirmó que terminó de revisar "
        "los comprobantes procesados y pide explícitamente el Excel."
    ),
    parameters={
        "type": "object",
        "properties": {
            "proceso_id": {
                "type": "string",
                "description": (
                    "ID del proceso devuelto por `yoko_procesar_archivos` "
                    "(formato proc-XXXXXXXXXXXX)."
                ),
            },
        },
        "required": ["proceso_id"],
    },
    category="accion",
)
def yoko_generar_registro_contable(args: dict, context: dict) -> dict:
    auth_header = _get_context_auth(context)
    return tool_executor.execute_local_tool(
        "registro-contable-chat", args, auth_header,
    )


# ─────────────────────────────────────────────────────────────────────────
# 3. yoko_recuperar_proceso
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="yoko_recuperar_proceso",
    description=(
        "Consulta los detalles de un proceso de facturas ya creado "
        "(estado, comprobantes extraídos, totales, alertas). Útil cuando "
        "el usuario pregunta por un proceso anterior usando su id "
        "(formato proc-XXXXX) o cuando hay que revisar qué se procesó "
        "antes de generar el Excel."
    ),
    parameters={
        "type": "object",
        "properties": {
            "proceso_id": {
                "type": "string",
                "description": "ID del proceso a consultar (formato proc-XXXXX).",
            },
        },
        "required": ["proceso_id"],
    },
    category="consulta",
)
def yoko_recuperar_proceso(args: dict, context: dict) -> dict:
    auth_header = _get_context_auth(context)
    return tool_executor.execute_local_tool(
        "recuperar-chat", args, auth_header,
    )


# ─────────────────────────────────────────────────────────────────────────
# 4. cancelar_carrito
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="cancelar_carrito",
    description=(
        "Vacía el carrito de archivos de la sesión actual. Invocala "
        "cuando el usuario expresa intención de cancelar (intención #3 "
        "del SKILL): 'cancela', 'borra todo', 'olvídalo', 'no, déjalo', "
        "'mejor no', 'ya no quiero'. Devuelve cuántos archivos había "
        "para que puedas confirmárselo. Idempotente: si el carrito ya "
        "estaba vacío, devuelve 0 sin error."
    ),
    parameters={"type": "object", "properties": {}},
    category="accion",
)
def cancelar_carrito(args: dict, context: dict) -> dict:
    session_id = _get_context_session(context)
    if not session_id:
        return {"ok": False, "borrados": 0, "detail": "session_id ausente en context."}
    try:
        n = yoko_cart_store.clear_cart(session_id)
    except Exception as e:
        return {"ok": False, "borrados": 0, "detail": f"{type(e).__name__}: {e}"}
    return {"ok": True, "borrados": int(n)}
