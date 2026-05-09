"""
api/_lib/managed_agents_client.py

Wrapper urllib para la API beta de Anthropic Managed Agents.
Beta header: `managed-agents-2026-04-01`.

Sigue el mismo patrón que airtable_client.py: urllib puro, errores con clase
dedicada, logs a stderr con prefijo [managed_agents]. La dependencia
`anthropic` declarada en pyproject.toml NO se usa acá — la beta API se llama
directo por HTTP para no quedar atado a la shape del SDK mientras está beta.

Endpoints asumidos (verificar contra https://docs.anthropic.com cuando se
ejecute por primera vez; ajustar las constantes _PATH_* si difieren):

  POST   /v1/agents                          crear agent
  GET    /v1/agents/{id}                     leer agent
  POST   /v1/agents/{id}                     actualizar agent (algunos SDKs usan PATCH)
  POST   /v1/agents/{id}/sessions            crear session
  POST   /v1/sessions/{id}/messages          enviar mensaje del usuario
  POST   /v1/sessions/{id}/messages          stream de respuesta del assistant (SSE)
  POST   /v1/sessions/{id}/tool_results      submit tool_result desde el orquestador
  DELETE /v1/sessions/{id}                   cerrar session

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
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ManagedAgentsError("Falta ANTHROPIC_API_KEY en las variables de entorno.")
    return key


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
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
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


def _request_stream(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 120,
) -> Iterator[dict]:
    """
    Ejecuta request HTTP con respuesta SSE (Server-Sent Events) y yield-ea
    cada evento parseado como dict. Cierra el socket al terminar.

    Formato esperado de cada evento:
        event: <tipo>
        data: {"...": ...}
        \n
    """
    url = f"{_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, headers=_headers({"Accept": "text/event-stream"}), method=method,
    )

    try:
        res = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        msg = f"Anthropic HTTP {e.code} (stream) en {method} {path}"
        print(f"[managed_agents] {msg} body={body_text[:300]}", file=sys.stderr)
        raise ManagedAgentsError(msg, status=e.code, body=body_text) from e
    except urllib.error.URLError as e:
        msg = f"Error de red (stream) hacia Anthropic: {e}"
        print(f"[managed_agents] {msg}", file=sys.stderr)
        raise ManagedAgentsError(msg) from e

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
    vault_id: str,
    memory_store_id: str,
    metadata: dict | None = None,
) -> str:
    """
    Crea una session asociada al agent. Devuelve `session_id`.
    `metadata` se persiste en la session (útil para empresa_id, user_id, etc.).
    """
    body = {
        "vault_id": vault_id,
        "memory_store_id": memory_store_id,
        "metadata": metadata or {},
    }
    res = _request("POST", f"/v1/agents/{urllib.parse.quote(agent_id)}/sessions", body=body)
    sid = res.get("id") or res.get("session_id")
    if not sid:
        raise ManagedAgentsError(f"create_session no devolvió session_id: {res}")
    return sid


def send_user_message(
    session_id: str,
    content: str,
    attachments: list[dict] | None = None,
) -> dict:
    """
    Envía un mensaje del usuario a la session. `attachments` opcional con
    archivos en base64 (formato a confirmar con docs).

    Devuelve respuesta sincrónica (no-stream). Para stream usar
    `stream_assistant_response`.
    """
    body: dict = {
        "role": "user",
        "content": content,
    }
    if attachments:
        body["attachments"] = attachments
    return _request(
        "POST",
        f"/v1/sessions/{urllib.parse.quote(session_id)}/messages",
        body=body,
    )


def stream_assistant_response(
    session_id: str,
    content: str,
    attachments: list[dict] | None = None,
) -> Iterator[dict]:
    """
    Manda el mensaje del usuario y stream-ea los eventos SSE de la respuesta
    del assistant.

    Cada evento es un dict con al menos `type` (e.g. "content_block_delta",
    "tool_use", "message_stop", etc.). El consumidor decide qué hacer con
    cada uno.
    """
    body: dict = {
        "role": "user",
        "content": content,
        "stream": True,
    }
    if attachments:
        body["attachments"] = attachments
    yield from _request_stream(
        "POST",
        f"/v1/sessions/{urllib.parse.quote(session_id)}/messages",
        body=body,
    )


def submit_tool_result(session_id: str, tool_use_id: str, content: object) -> dict:
    """
    Cuando el orquestador ejecutó un tool_use solicitado por el agent, devuelve
    el resultado vía este endpoint. `content` puede ser string u objeto JSON.
    """
    body = {"tool_use_id": tool_use_id, "content": content}
    return _request(
        "POST",
        f"/v1/sessions/{urllib.parse.quote(session_id)}/tool_results",
        body=body,
    )


def close_session(session_id: str) -> bool:
    """Cierra la session. Devuelve True si OK, False si ya estaba cerrada."""
    try:
        _request("DELETE", f"/v1/sessions/{urllib.parse.quote(session_id)}")
        return True
    except ManagedAgentsError as e:
        if e.status in (404, 410):
            return False
        raise
