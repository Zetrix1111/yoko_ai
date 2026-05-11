"""
api/_lib/whatsapp_meta_client.py

Cliente HTTP mínimo para WhatsApp Cloud API de Meta (graph.facebook.com).
Sigue el mismo patrón que `airtable_client.py` y `managed_agents_client.py`:
urllib puro, sin SDK externo, errores con clase dedicada, logs a stderr
con prefijo [whatsapp_meta].

Cada call recibe `phone_number_id` (qué WABA emite) y `access_token`
(de la fila correspondiente en `meta_connections`). Multi-tenant
explícito: no hay state global, todo viene por parámetro.

API pública:
  - `send_text(phone_number_id, to, text, access_token) -> dict`
  - `send_image(phone_number_id, to, image_url, caption, access_token) -> dict`
  - `send_document(phone_number_id, to, doc_url, filename, access_token) -> dict`
  - `verify_webhook_signature(payload_bytes, sig_header, app_secret) -> bool`
  - `class MetaError(Exception)`

Endpoint base: https://graph.facebook.com/v18.0/{phone_number_id}/messages
"""

import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.request

from ._http_utils import read_http_error_body


_BASE_URL = "https://graph.facebook.com/v18.0"


class MetaError(Exception):
    """Error de la WhatsApp Cloud API (HTTP no-2xx, red, parseo)."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _post(phone_number_id: str, access_token: str, payload: dict, timeout: int = 15) -> dict:
    """POST a /{phone_number_id}/messages. Devuelve JSON parseado."""
    url = f"{_BASE_URL}/{phone_number_id}/messages"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = read_http_error_body(e)
        msg = f"Meta HTTP {e.code} en POST /messages (type={payload.get('type')})"
        print(f"[whatsapp_meta] {msg} body={body_text[:300]}", file=sys.stderr)
        raise MetaError(msg, status=e.code, body=body_text) from e
    except urllib.error.URLError as e:
        msg = f"Error de red hacia Meta: {e}"
        print(f"[whatsapp_meta] {msg}", file=sys.stderr)
        raise MetaError(msg) from e
    except json.JSONDecodeError as e:
        msg = f"Respuesta no-JSON desde Meta: {e}"
        print(f"[whatsapp_meta] {msg}", file=sys.stderr)
        raise MetaError(msg) from e


def send_text(phone_number_id: str, to: str, text: str, access_token: str) -> dict:
    """
    Envía un mensaje de texto. `to` es el número del cliente en formato
    internacional sin '+' (ej: '51999888777'). Meta normaliza.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "text",
        "text":              {"body": text},
    }
    return _post(phone_number_id, access_token, payload)


def send_image(
    phone_number_id: str,
    to: str,
    image_url: str,
    caption: str | None,
    access_token: str,
) -> dict:
    """
    Envía una imagen desde URL pública. WhatsApp la descarga y la
    reenvía al cliente como mensaje nativo (no como link).
    """
    image_payload: dict = {"link": image_url}
    if caption:
        image_payload["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "image",
        "image":             image_payload,
    }
    return _post(phone_number_id, access_token, payload)


def send_document(
    phone_number_id: str,
    to: str,
    doc_url: str,
    filename: str | None,
    access_token: str,
) -> dict:
    """Envía un documento (PDF, etc) desde URL pública."""
    doc_payload: dict = {"link": doc_url}
    if filename:
        doc_payload["filename"] = filename
    payload = {
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "document",
        "document":          doc_payload,
    }
    return _post(phone_number_id, access_token, payload)


def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    """
    Valida la firma HMAC SHA256 del header `X-Hub-Signature-256` que
    Meta envía con cada POST al webhook. Sin secret válido, cualquiera
    podría POSTear al endpoint público y disparar el bot.

    El header viene como `sha256=<hex_digest>`. Comparamos en tiempo
    constante para evitar timing attacks.

    Devuelve False ante header vacío/malformado o si NO matchea.
    """
    if not signature_header or not app_secret:
        return False

    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header[len("sha256="):]

    mac = hmac.new(
        app_secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    )
    actual = mac.hexdigest()

    return hmac.compare_digest(expected, actual)
