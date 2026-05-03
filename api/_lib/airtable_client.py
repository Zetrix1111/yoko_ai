"""
Cliente HTTP mínimo para Airtable usando solo urllib.

No depende de paquetes externos (mismo patrón que api/login.py).
Lee credenciales de las env vars AIRTABLE_TOKEN y AIRTABLE_BASE_ID.

Todas las funciones públicas aceptan un parámetro opcional `base_id`.
Si no se pasa, se usa AIRTABLE_BASE_ID del env (comportamiento normal).
El parámetro queda disponible como foundation por si en el futuro se
necesita acceder a otra base; hoy todas las tablas viven en una sola.

Forma de los registros devueltos: {"id": <recId>, "fields": {...}}.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request


_BASE_URL = "https://api.airtable.com/v0"


class AirtableError(Exception):
    """Error genérico de la API de Airtable (HTTP no-2xx, red, parseo)."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _get_token() -> str:
    """Lee y valida AIRTABLE_TOKEN."""
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        raise AirtableError("Falta AIRTABLE_TOKEN en las variables de entorno.")
    return token


def _resolve_base_id(base_id: str | None) -> str:
    """Si `base_id` viene None, usa AIRTABLE_BASE_ID del env (legacy)."""
    if base_id:
        return base_id
    env_base = os.environ.get("AIRTABLE_BASE_ID")
    if not env_base:
        raise AirtableError(
            "Falta AIRTABLE_BASE_ID en env y no se pasó base_id explícito."
        )
    return env_base


def _get_credentials() -> tuple[str, str]:
    """Compat legacy: token + base_id default. Algunos endpoints viejos lo importan."""
    return _get_token(), _resolve_base_id(None)


def _table_url(table: str, base_id: str | None = None) -> str:
    """Construye la URL base para una tabla en una base específica."""
    base = _resolve_base_id(base_id)
    return f"{_BASE_URL}/{base}/{urllib.parse.quote(table)}"


def _request(method: str, url: str, body: dict | None = None, timeout: int = 15) -> dict:
    """Ejecuta una request HTTP a Airtable y devuelve el JSON parseado."""
    token = _get_token()

    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

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
        raise AirtableError(
            f"Airtable HTTP {e.code} en {method} {url}", status=e.code, body=body_text
        ) from e
    except urllib.error.URLError as e:
        raise AirtableError(f"Error de red hacia Airtable: {e}") from e
    except json.JSONDecodeError as e:
        raise AirtableError(f"Respuesta no-JSON desde Airtable: {e}") from e


def _normalize(record: dict) -> dict:
    """Reduce un registro Airtable a {'id', 'fields'} (descarta createdTime)."""
    return {"id": record.get("id"), "fields": record.get("fields", {})}


def list_records(
    table: str,
    filter_formula: str | None = None,
    max_records: int = 100,
    base_id: str | None = None,
) -> list[dict]:
    """
    Lista registros de una tabla, opcionalmente filtrados por una fórmula
    Airtable. No pagina: devuelve hasta `max_records` registros (Airtable
    devuelve hasta 100 por página, así que valores >100 quedan capeados).

    Si `base_id` viene None, se usa AIRTABLE_BASE_ID del env.
    """
    params: list[tuple[str, str]] = [("maxRecords", str(max_records))]
    if filter_formula:
        params.append(("filterByFormula", filter_formula))
    qs = urllib.parse.urlencode(params)
    url = f"{_table_url(table, base_id=base_id)}?{qs}"

    data = _request("GET", url)
    return [_normalize(r) for r in data.get("records", [])]


def get_record(table: str, record_id: str, base_id: str | None = None) -> dict:
    """Obtiene un registro específico por su recId."""
    url = f"{_table_url(table, base_id=base_id)}/{urllib.parse.quote(record_id)}"
    data = _request("GET", url)
    return _normalize(data)


def create_record(table: str, fields: dict, base_id: str | None = None) -> dict:
    """Crea un registro en la tabla y devuelve la versión normalizada."""
    url = _table_url(table, base_id=base_id)
    data = _request("POST", url, body={"fields": fields})
    return _normalize(data)


def update_record(table: str, record_id: str, fields: dict, base_id: str | None = None) -> dict:
    """Actualiza campos de un registro (PATCH no destruye los no enviados)."""
    url = f"{_table_url(table, base_id=base_id)}/{urllib.parse.quote(record_id)}"
    data = _request("PATCH", url, body={"fields": fields})
    return _normalize(data)


def delete_record(table: str, record_id: str, base_id: str | None = None) -> dict:
    """Elimina un registro. Devuelve {'deleted': True, 'id': ...}."""
    url = f"{_table_url(table, base_id=base_id)}/{urllib.parse.quote(record_id)}"
    return _request("DELETE", url)


def upsert_by_field(
    table: str,
    match_field: str,
    match_value: str,
    fields: dict,
    base_id: str | None = None,
) -> dict:
    """
    Si existe una fila donde `match_field == match_value`, la actualiza (PATCH).
    Si no existe, la crea con `fields` + el match_field seteado.

    Las comillas simples en la fórmula están bien para `empresa_id` slugs
    (cmejia, demo, etc). NO usar con valores que puedan tener apóstrofes.
    """
    formula = f"{{{match_field}}} = '{match_value}'"
    existing = list_records(table, filter_formula=formula, max_records=1, base_id=base_id)
    if existing:
        return update_record(table, existing[0]["id"], fields, base_id=base_id)
    return create_record(table, {**fields, match_field: match_value}, base_id=base_id)
