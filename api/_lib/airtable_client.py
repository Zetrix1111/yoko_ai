"""
Cliente HTTP mínimo para Airtable usando solo urllib.

No depende de paquetes externos (mismo patrón que api/login.py).
Lee credenciales de las env vars AIRTABLE_TOKEN y AIRTABLE_BASE_ID.

Toda la app vive en una sola base (`app9s5KuEvlAlZJgl`); las funciones
no aceptan `base_id` — siempre se resuelve desde el env.

Forma de los registros devueltos: {"id": <recId>, "fields": {...}}.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from ._http_utils import read_http_error_body, require_env


_BASE_URL = "https://api.airtable.com/v0"


class AirtableError(Exception):
    """Error genérico de la API de Airtable (HTTP no-2xx, red, parseo)."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _get_token() -> str:
    return require_env("AIRTABLE_TOKEN", AirtableError)


def _get_base_id() -> str:
    return require_env("AIRTABLE_BASE_ID", AirtableError)


def _table_url(table: str) -> str:
    """Construye la URL base para una tabla en la base default."""
    return f"{_BASE_URL}/{_get_base_id()}/{urllib.parse.quote(table)}"


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
        body_text = read_http_error_body(e)
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
) -> list[dict]:
    """
    Lista registros de una tabla, opcionalmente filtrados por una fórmula
    Airtable. No pagina: devuelve hasta `max_records` registros (Airtable
    devuelve hasta 100 por página, así que valores >100 quedan capeados).
    """
    params: list[tuple[str, str]] = [("maxRecords", str(max_records))]
    if filter_formula:
        params.append(("filterByFormula", filter_formula))
    qs = urllib.parse.urlencode(params)
    url = f"{_table_url(table)}?{qs}"

    data = _request("GET", url)
    return [_normalize(r) for r in data.get("records", [])]


def get_record(table: str, record_id: str) -> dict:
    """Obtiene un registro específico por su recId."""
    url = f"{_table_url(table)}/{urllib.parse.quote(record_id)}"
    data = _request("GET", url)
    return _normalize(data)


def create_record(table: str, fields: dict) -> dict:
    """Crea un registro en la tabla y devuelve la versión normalizada."""
    url = _table_url(table)
    data = _request("POST", url, body={"fields": fields})
    return _normalize(data)


def update_record(table: str, record_id: str, fields: dict) -> dict:
    """Actualiza campos de un registro (PATCH no destruye los no enviados)."""
    url = f"{_table_url(table)}/{urllib.parse.quote(record_id)}"
    data = _request("PATCH", url, body={"fields": fields})
    return _normalize(data)


def delete_record(table: str, record_id: str) -> dict:
    """Elimina un registro. Devuelve {'deleted': True, 'id': ...}."""
    url = f"{_table_url(table)}/{urllib.parse.quote(record_id)}"
    return _request("DELETE", url)


def upsert_by_field(
    table: str,
    match_field: str,
    match_value: str,
    fields: dict,
) -> dict:
    """
    Si existe una fila donde `match_field == match_value`, la actualiza (PATCH).
    Si no existe, la crea con `fields` + el match_field seteado.

    Las comillas simples en la fórmula están bien para `empresa_id` slugs
    (cmejia, demo, etc). NO usar con valores que puedan tener apóstrofes.
    """
    formula = f"{{{match_field}}} = '{match_value}'"
    existing = list_records(table, filter_formula=formula, max_records=1)
    if existing:
        return update_record(table, existing[0]["id"], fields)
    return create_record(table, {**fields, match_field: match_value})
