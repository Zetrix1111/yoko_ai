"""
api/_yoko/handler_worker.py — worker function del chat async.

Invocado por `POST /api/chat?action=worker&task_id=<id>` desde
`handle_post` de `handler_managed.py` (fire-and-forget). Tiene su propio
presupuesto de Vercel (~300s con fluid compute), separado del POST inicial
del usuario que vuelve <2s.

Flujo:
  1. Verificar header `X-Internal-Token` (auth interna, no JWT).
  2. Leer task_id del query string.
  3. Cargar task del KV. Si no existe / no pending → salir (idempotencia).
  4. mark_running.
  5. Ejecutar `_run_turn_streaming` (igual al `_run_turn` de handler_managed,
     pero después de cada `agent.message` actualiza el `accumulated` del
     task en KV — el frontend pollea ese campo y muestra streaming).
  6. mark_done / mark_error según resultado.

Nunca devuelve texto al cliente HTTP que lo invocó (el dispatcher
`handle_post` no espera respuesta — fire-and-forget). Solo escribe al KV.
"""

import os
import sys
from urllib.parse import parse_qs, urlparse

from _lib import managed_agents_client as mac
from _lib import yoko_cart_store, yoko_task_store
from _lib._config import MAX_TURNS_PER_RUN as _MAX_TURNS  # centralizado
from _lib.tool_executor import TOOL_TO_ACTION, execute_local_tool


def handle_post(req) -> None:
    """Punto de entrada del worker. Invocado solo desde handle_post."""
    # 1) Auth interna: token compartido, no JWT del usuario.
    expected = os.environ.get("YOKO_INTERNAL_TOKEN")
    received = req.headers.get("X-Internal-Token") or ""
    if not expected:
        print("[chat/worker] YOKO_INTERNAL_TOKEN no configurado", file=sys.stderr)
        return req._json(500, {"error": "Server misconfigured"})
    if received != expected:
        print("[chat/worker] token interno inválido", file=sys.stderr)
        return req._json(401, {"error": "Unauthorized"})

    # 2) task_id del query
    parsed = urlparse(req.path)
    qs = parse_qs(parsed.query or "")
    task_id = (qs.get("task_id") or [""])[0].strip()
    if not task_id:
        return req._json(400, {"error": "task_id requerido"})

    # 3) Cargar task
    task = yoko_task_store.get(task_id)
    if task is None:
        print(f"[chat/worker] task {task_id} no encontrado / expirado", file=sys.stderr)
        return req._json(404, {"error": "Task not found"})

    if task.get("status") not in ("pending", None):
        # Idempotencia: si ya estaba running/done/error, no rehacemos.
        print(
            f"[chat/worker] task {task_id} ya estaba en {task.get('status')}; "
            "skip silencioso",
            file=sys.stderr,
        )
        return req._json(200, {"already": task.get("status")})

    # 4) Marcar running
    yoko_task_store.mark_running(task_id)
    print(f"[chat/worker] task {task_id} arrancando", file=sys.stderr)

    # 5) Run turn con streaming a KV
    try:
        final_text = _run_turn_streaming(
            task_id=task_id,
            session_id=task["session_id"],
            user_content=task["user_content"],
            auth_header=task.get("auth_header") or "",
        )
        yoko_task_store.mark_done(task_id, final_text)
        print(
            f"[chat/worker] task {task_id} done ({len(final_text)} chars)",
            file=sys.stderr,
        )
    except mac.ManagedAgentsError as e:
        msg = f"Error del servicio IA: {e}"
        yoko_task_store.mark_error(task_id, msg)
        print(f"[chat/worker] task {task_id} error: {e}", file=sys.stderr)
    except Exception as e:
        msg = f"Error interno: {type(e).__name__}: {e}"
        yoko_task_store.mark_error(task_id, msg)
        print(f"[chat/worker] task {task_id} error: {msg}", file=sys.stderr)

    return req._json(200, {"ok": True, "task_id": task_id})


def _run_turn_streaming(
    task_id: str,
    session_id: str,
    user_content: str,
    auth_header: str,
) -> str:
    """
    Versión del `_run_turn` original adaptada para escribir el texto
    parcial al task_store. Cada vez que llega un `agent.message` con
    texto, hacemos `append_accumulated` — así el polling del frontend
    ve el bot escribiendo "en vivo".

    El resto de la lógica (tool injection desde cart, clear cart tras
    éxito, manejo de session.status_idle, etc.) se mantiene igual al
    handler_managed._run_turn.
    """
    text_parts: list[str] = []
    pending_tools: dict[str, dict] = {}

    stream = mac.stream_session_events(session_id)
    print(f"[chat/worker] stream abierto session={session_id}", file=sys.stderr)

    mac.send_user_message(session_id, user_content)
    print(
        f"[chat/worker] user.message posteado ({len(user_content)} chars)",
        file=sys.stderr,
    )

    events_seen = 0
    turns = 0

    for evt in stream:
        events_seen += 1
        etype = evt.get("type") or ""
        if events_seen <= 3 or etype.startswith("session.") or etype == "session.error":
            print(f"[chat/worker] evt#{events_seen} type={etype}", file=sys.stderr)

        if etype == "agent.message":
            for block in evt.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text") or ""
                    if t:
                        text_parts.append(t)
                        # Streaming: publicar el chunk al task_store para
                        # que el polling del frontend lo vea.
                        try:
                            yoko_task_store.append_accumulated(task_id, t)
                        except Exception as e:
                            print(
                                f"[chat/worker] append_accumulated falló: {e}",
                                file=sys.stderr,
                            )

        elif etype == "agent.custom_tool_use":
            evt_id = evt.get("id") or ""
            name = evt.get("name") or ""
            tool_input = evt.get("input") or {}
            if evt_id and name:
                pending_tools[evt_id] = {"name": name, "input": tool_input}

        elif etype == "session.error":
            err = evt.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            print(f"[chat/worker] session.error: {msg}", file=sys.stderr)
            break

        elif etype == "session.status_idle":
            stop = evt.get("stop_reason") or {}
            stop_type = stop.get("type") if isinstance(stop, dict) else None

            if stop_type == "end_turn":
                break

            if stop_type == "requires_action":
                blocking_ids: list[str] = []
                if isinstance(stop, dict):
                    blocking_ids = list(stop.get("event_ids") or [])

                if not blocking_ids:
                    break

                turns += 1
                if turns > _MAX_TURNS:
                    print(
                        f"[chat/worker] cap de turnos ({_MAX_TURNS}); cortando loop",
                        file=sys.stderr,
                    )
                    break

                for eid in blocking_ids:
                    pending = pending_tools.get(eid)
                    if not pending:
                        mac.submit_custom_tool_result(
                            session_id, eid,
                            {"error": "tool_use no encontrado en el stream"},
                        )
                        continue

                    tool_name = pending["name"]
                    tool_input = dict(pending["input"] or {})

                    # Pass-by-reference del cart (mismo patrón que
                    # handler_managed actual).
                    if tool_name in ("yoko_procesar_archivos", "yoko_procesar_solicitud_caja"):
                        tool_input["session_id_for_cart"] = session_id
                        try:
                            cart_n = yoko_cart_store.cart_size(session_id)
                            print(
                                f"[chat/worker] {tool_name} invocado; "
                                f"carrito tiene {cart_n} archivo(s)",
                                file=sys.stderr,
                            )
                        except Exception:
                            pass

                    action = TOOL_TO_ACTION.get(tool_name)
                    if not action:
                        result: dict = {"error": f"Tool '{tool_name}' no soportado."}
                        print(
                            f"[chat/worker] tool desconocido: {tool_name}",
                            file=sys.stderr,
                        )
                    else:
                        tool_context = {
                            "user": task.get("user") or {},
                            "empresa_id": task.get("empresa_id") or "",
                            "modulos": task.get("modulos") or [],
                            "session_id_for_cart": session_id,
                        }
                        result = execute_local_tool(
                            action,
                            tool_input,
                            auth_header,
                            tool_context=tool_context,
                        )

                    # Si una tool de procesamiento de archivos terminó OK, vaciar el carrito.
                    if (
                        tool_name in ("yoko_procesar_archivos", "yoko_procesar_solicitud_caja")
                        and isinstance(result, dict)
                        and result.get("ok") is True
                    ):
                        try:
                            cleared = yoko_cart_store.clear_cart(session_id)
                            print(
                                f"[chat/worker] carrito vaciado tras éxito: "
                                f"{cleared} archivo(s)",
                                file=sys.stderr,
                            )
                        except Exception as e:
                            print(
                                f"[chat/worker] clear_cart falló: {e}",
                                file=sys.stderr,
                            )

                    mac.submit_custom_tool_result(session_id, eid, result)
                continue

            print(
                f"[chat/worker] stop_reason inesperado: {stop_type}",
                file=sys.stderr,
            )
            break

    return "".join(text_parts).strip()
