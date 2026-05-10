"""
Cliente HTTP mínimo para Vercel KV (Upstash REST), siguiendo el mismo patrón
que airtable_client.py: solo urllib, credenciales del env, errores con clase
dedicada y logs a stderr con prefijo [kv_client].

Env vars consumidas (las inyecta Vercel al activar la integración Upstash):
  - KV_REST_API_URL
  - KV_REST_API_TOKEN

Uso típico:

    from _lib.kv_client import kv_get, kv_set, kv_delete, kv_exists

    kv_set("yoko:session:cmejia:user_42", "sess_abc123", ttl_seconds=14400)
    sid = kv_get("yoko:session:cmejia:user_42")

Los comandos se invocan via pipeline POST {base}/ con body ["CMD", arg1, ...].
Es la API estándar de Upstash REST y maneja bien valores con caracteres
especiales (no hay que URL-encodear).
"""

import json
import os
import sys
import urllib.error
import urllib.request


class KVError(Exception):
    """Error genérico del cliente KV (HTTP no-2xx, red, parseo)."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _get_base_url() -> str:
    url = os.environ.get("KV_REST_API_URL")
    if not url:
        raise KVError("Falta KV_REST_API_URL en las variables de entorno.")
    return url.rstrip("/")


def _get_token() -> str:
    token = os.environ.get("KV_REST_API_TOKEN")
    if not token:
        raise KVError("Falta KV_REST_API_TOKEN en las variables de entorno.")
    return token


def _command(args: list, timeout: int = 10) -> object:
    """
    Ejecuta un comando Redis via Upstash REST.
    args = ["GET", "key"] o ["SET", "key", "value", "EX", "60"], etc.
    Devuelve el campo `result` de la respuesta JSON (string | int | None | "OK").
    """
    url = f"{_get_base_url()}/"
    data = json.dumps(args).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            payload = json.loads(raw) if raw else {}
            if isinstance(payload, dict) and "error" in payload:
                msg = f"KV error: {payload['error']}"
                print(f"[kv_client] {msg}", file=sys.stderr)
                raise KVError(msg)
            return payload.get("result") if isinstance(payload, dict) else None
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        msg = f"KV HTTP {e.code} en cmd {args[0]}"
        print(f"[kv_client] {msg} body={body_text[:200]}", file=sys.stderr)
        raise KVError(msg, status=e.code, body=body_text) from e
    except urllib.error.URLError as e:
        msg = f"Error de red hacia KV: {e}"
        print(f"[kv_client] {msg}", file=sys.stderr)
        raise KVError(msg) from e
    except json.JSONDecodeError as e:
        msg = f"Respuesta no-JSON desde KV: {e}"
        print(f"[kv_client] {msg}", file=sys.stderr)
        raise KVError(msg) from e


def kv_get(key: str) -> str | None:
    """Lee el valor de una clave. Devuelve None si no existe."""
    result = _command(["GET", key])
    if result is None:
        return None
    return str(result)


def kv_set(key: str, value: str, ttl_seconds: int | None = None) -> bool:
    """
    Setea una clave con valor string. Si `ttl_seconds` está dado, expira
    en ese tiempo (sino persiste indefinidamente).
    Devuelve True si Redis respondió "OK".
    """
    args: list = ["SET", key, value]
    if ttl_seconds is not None and ttl_seconds > 0:
        args.extend(["EX", str(int(ttl_seconds))])
    result = _command(args)
    return result == "OK"


def kv_delete(key: str) -> bool:
    """Borra una clave. Devuelve True si existía y se borró."""
    result = _command(["DEL", key])
    try:
        return int(result) > 0
    except (TypeError, ValueError):
        return False


def kv_exists(key: str) -> bool:
    """Devuelve True si la clave existe."""
    result = _command(["EXISTS", key])
    try:
        return int(result) > 0
    except (TypeError, ValueError):
        return False


def kv_expire(key: str, ttl_seconds: int) -> bool:
    """
    Renueva el TTL de una clave existente (sliding expiration manual).
    Devuelve True si la clave existía y se aplicó el nuevo TTL.
    """
    result = _command(["EXPIRE", key, str(int(ttl_seconds))])
    try:
        return int(result) > 0
    except (TypeError, ValueError):
        return False


def kv_mget(keys: list) -> list:
    """
    Lee N claves en una sola llamada Redis (pipelining nativo).
    Devuelve una lista del mismo largo que `keys`, con `str` para claves
    existentes y `None` para las que no existen.

    Útil cuando hay que leer muchas claves relacionadas (ej. el carrito
    de archivos): pasa de N round trips a 1.
    """
    if not keys:
        return []
    result = _command(["MGET", *keys])
    if not isinstance(result, list):
        # Upstash REST devuelve lista; si por algún motivo viene otra cosa,
        # caemos a None para todas las claves.
        return [None] * len(keys)
    return [None if v is None else str(v) for v in result]
