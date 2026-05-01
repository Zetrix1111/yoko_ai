"""
Cliente HTTP mínimo para Airtable usando solo urllib.

No depende de paquetes externos (mismo patrón que api/login.py).
Lee credenciales de las env vars AIRTABLE_TOKEN y AIRTABLE_BASE_ID.

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


def _get_credentials() -> tuple[str, str]:
    """Lee y valida AIRTABLE_TOKEN y AIRTABLE_BASE_ID."""
    token = os.environ.get("AIRTABLE_TOKEN")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    if not token or not base_id:
        raise AirtableError(
            "Faltan AIRTABLE_TOKEN o AIRTABLE_BASE_ID en las variables de entorno."
        )
    return token, base_id


def _table_url(table: str) -> str:
    """Construye la URL base para una tabla."""
    _, base_id = _get_credentials()
    return f"{_BASE_URL}/{base_id}/{urllib.parse.quote(table)}"


def _request(method: str, url: str, body: dict | None = None, timeout: int = 15) -> dict:
    """Ejecuta una request HTTP a Airtable y devuelve el JSON parseado."""
    token, _ = _get_credentials()

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
) -> list[dict]:
    """
    Lista registros de una tabla, opcionalmente filtrados por una fórmula
    Airtable. No pagina: devuelve hasta `max_records` registros (Airtable
    devuelve hasta 100 por página, así que valores >100 quedan capeados).
    """
    params: list[tuple[str, str]] = [("maxRecords", str(max_records))]
    if filter_formula:
        # urlencode hace el quote internamente; explícito por si el formula
        # tiene caracteres especiales como llaves o comillas.
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
