"""
api/_lib/managed_agents_client.py

Wrapper urllib para la API beta de Anthropic Managed Agents.
Beta header: `managed-agents-2026-04-01`.

Sigue el mismo patrón que airtable_client.py: urllib puro, errores con clase
dedicada, logs a stderr con prefijo [managed_agents]. La dependencia
`anthropic` declarada en pyproject.toml NO se usa acá — la beta API se llama
directo por HTTP para no quedar atado a la shape del SDK mientras está beta.

Endpoints reales (verificados contra platform.claude.com/docs/en/managed-agents):

  POST   /v1/agents                              crear agent
  GET    /v1/agents/{id}                         leer agent
  POST   /v1/agents/{id}                         actualizar agent
  POST   /v1/sessions                            crear session
  POST   /v1/sessions/{id}/events                enviar evento(s): user.message,
                                                 user.custom_tool_result, etc.
  GET    /v1/sessions/{id}/events/stream         stream SSE de eventos del agent
  GET    /v1/sessions/{id}                       leer session (status, usage)
  DELETE /v1/sessions/{id}                       eliminar session

Protocolo:
  - El POST a /events SOLO encola el evento, devuelve un ack vacío.
  - La respuesta del assistant llega por GET /events/stream como SSE.
  - Para custom tools: el agent emite `agent.custom_tool_use`, la session
    pausa con `session.status_idle` y `stop_reason.type == "requires_action"`,
    y se responde con un evento `user.custom_tool_result` cuyo
    `custom_tool_use_id` es el id del evento bloqueante.

Auth:
  x-api-key: ANTHROPIC_API_KEY
  anthropic-version: 2023-06-01
  anthropic-beta: managed-agents-2026-04-01
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator

from ._http_utils import read_http_error_body, require_env


_BASE_URL = "https://api.anthropic.com"
_BETA_HEADER = "managed-agents-2026-04-01"
_API_VERSION = "2023-06-01"


class ManagedAgentsError(Exception):
    """Error genérico de la API de Managed Agents (HTTP no-2xx, red, parseo)."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _get_api_key() -> str:
    return require_env("ANTHROPIC_API_KEY", ManagedAgentsError)


def _headers(extra: dict | None = None) -> dict:
    h = {
        "x-api-key": _get_api_key(),
        "anthropic-version": _API_VERSION,
        "anthropic-beta": _BETA_HEADER,
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 30,
) -> dict:
    """
    Ejecuta request HTTP a la API de Anthropic y devuelve el JSON parseado.
    Para llamadas streaming usar `_request_stream` en su lugar.
    """
    url = f"{_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = read_http_error_body(e)
        msg = f"Anthropic HTTP {e.code} en {method} {path}"
        print(f"[managed_agents] {msg} body={body_text[:300]}", file=sys.stderr)
        raise ManagedAgentsError(msg, status=e.code, body=body_text) from e
    except urllib.error.URLError as e:
        msg = f"Error de red hacia Anthropic: {e}"
        print(f"[managed_agents] {msg}", file=sys.stderr)
        raise ManagedAgentsError(msg) from e
    except json.JSONDecodeError as e:
        msg = f"Respuesta no-JSON desde Anthropic: {e}"
        print(f"[managed_agents] {msg}", file=sys.stderr)
        raise ManagedAgentsError(msg) from e


def _open_sse(method: str, path: str, body: dict | None = None, timeout: int = 300):
    """
    Abre una conexión SSE eagerly. Devuelve el HTTPResponse listo para
    iterar. CRITICAL: hay que llamarla antes de hacer POSTs que disparan
    eventos para no perder ninguno (los servidores SSE solo entregan eventos
    posteriores a la apertura del stream).
    """
    url = f"{_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, headers=_headers({"Accept": "text/event-stream"}), method=method,
    )
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body_text = read_http_error_body(e)
        msg = f"Anthropic HTTP {e.code} (stream) en {method} {path}"
        print(f"[managed_agents] {msg} body={body_text[:300]}", file=sys.stderr)
        raise ManagedAgentsError(msg, status=e.code, body=body_text) from e
    except urllib.error.URLError as e:
        msg = f"Error de red (stream) hacia Anthropic: {e}"
        print(f"[managed_agents] {msg}", file=sys.stderr)
        raise ManagedAgentsError(msg) from e


def _iter_sse_events(res) -> Iterator[dict]:
    """
    Itera eventos SSE desde un HTTPResponse abierto. Cierra el socket al terminar.

    Formato esperado de cada evento:
        event: <tipo>
        data: {"...": ...}
        \n
    """
    try:
        event_type = None
        data_buf: list[str] = []
        for raw_line in res:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")

            if line == "":
                if data_buf:
                    payload = "\n".join(data_buf)
                    try:
                        evt = json.loads(payload)
                    except json.JSONDecodeError:
                        evt = {"type": event_type or "raw", "data": payload}
                    if event_type and "type" not in evt:
                        evt["type"] = event_type
                    yield evt
                event_type = None
                data_buf = []
                continue

            if line.startswith(":"):
                continue  # comentario SSE
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_buf.append(line[len("data:"):].lstrip())
    finally:
        res.close()


# ─────────────────────────────────────────────────────────────────────────
# Agents (provisioning)
# ─────────────────────────────────────────────────────────────────────────

def create_agent(config: dict) -> dict:
    """
    Crea un agent nuevo. `config` debe incluir name, model, system, tools, skills.
    Devuelve el dict del agent creado (incluye `id`).
    """
    return _request("POST", "/v1/agents", body=config)


def get_agent(agent_id: str) -> dict | None:
    """Lee un agent existente. Devuelve None si 404."""
    try:
        return _request("GET", f"/v1/agents/{urllib.parse.quote(agent_id)}")
    except ManagedAgentsError as e:
        if e.status == 404:
            return None
        raise


def update_agent(agent_id: str, config: dict) -> dict:
    """
    Actualiza un agent existente con la configuración nueva (sysprompt, tools,
    skills, etc.). Idempotente: si la config no cambió, debería ser no-op
    server-side.
    """
    return _request("POST", f"/v1/agents/{urllib.parse.quote(agent_id)}", body=config)


# ─────────────────────────────────────────────────────────────────────────
# Sessions (runtime)
# ─────────────────────────────────────────────────────────────────────────

def create_session(
    agent_id: str,
    vault_id: str | None = None,
    title: str | None = None,
) -> str:
    """
    Crea una session asociada al agent. Devuelve `session_id`.
    `title` aparece en la columna "Nombre" del Console.
    `environment_id` se toma del env YOKO_ENVIRONMENT_ID (requerido por la beta).
    """
    body: dict = {"agent": agent_id}

    env_id = os.environ.get("YOKO_ENVIRONMENT_ID")
    if env_id:
        body["environment_id"] = env_id

    if vault_id:
        body["vault_ids"] = [vault_id]
    if title:
        body["title"] = title

    res = _request("POST", "/v1/sessions", body=body)
    sid = res.get("id") or res.get("session_id")
    if not sid:
        raise ManagedAgentsError(f"create_session no devolvió session_id: {res}")
    return sid


def send_user_message(session_id: str, content: str) -> dict:
    """
    Encola un evento `user.message` con texto plano. La respuesta del agent
    NO viene en este endpoint — hay que leerla con `stream_session_events`.
    Devuelve el ack del POST (puede ser dict vacío).
    """
    body = {
        "events": [
            {
                "type": "user.message",
                "content": [{"type": "text", "text": content}],
            }
        ]
    }
    return _request(
        "POST",
        f"/v1/sessions/{urllib.parse.quote(session_id)}/events",
        body=body,
    )


def submit_custom_tool_result(
    session_id: str,
    custom_tool_use_id: str,
    content: object,
) -> dict:
    """
    Devuelve el resultado de un custom tool al agent. `custom_tool_use_id` es
    el id del evento `agent.custom_tool_use` que disparó la pausa
    `requires_action`. `content` puede ser string o dict; si es dict se serializa.
    """
    if isinstance(content, str):
        text = content
    else:
        try:
            text = json.dumps(content, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(content)

    body = {
        "events": [
            {
                "type": "user.custom_tool_result",
                "custom_tool_use_id": custom_tool_use_id,
                "content": [{"type": "text", "text": text}],
            }
        ]
    }
    return _request(
        "POST",
        f"/v1/sessions/{urllib.parse.quote(session_id)}/events",
        body=body,
    )


def stream_session_events(session_id: str, timeout: int = 300) -> Iterator[dict]:
    """
    Abre el stream SSE de eventos de la session EAGERLY (la conexión HTTP se
    abre antes de devolver) y devuelve un iterador de eventos.

    NO es una generator function — la apertura del socket ocurre en esta
    llamada, no en la primera iteración. Esto es indispensable para que el
    POST de user.message que viene después no pierda eventos:

        stream = mac.stream_session_events(session_id)  # ya abrió el socket
        mac.send_user_message(session_id, ...)          # dispara eventos
        for evt in stream: ...                          # los consume
    """
    res = _open_sse(
        "GET",
        f"/v1/sessions/{urllib.parse.quote(session_id)}/events/stream",
        body=None,
        timeout=timeout,
    )
    return _iter_sse_events(res)


def get_session(session_id: str) -> dict | None:
    """Lee el estado actual de una session (status, usage, etc.). None si 404."""
    try:
        return _request("GET", f"/v1/sessions/{urllib.parse.quote(session_id)}")
    except ManagedAgentsError as e:
        if e.status == 404:
            return None
        raise


def close_session(session_id: str) -> bool:
    """Cierra la session. Devuelve True si OK, False si ya estaba cerrada."""
    try:
        _request("DELETE", f"/v1/sessions/{urllib.parse.quote(session_id)}")
        return True
    except ManagedAgentsError as e:
        if e.status in (404, 410):
            return False
        raise
