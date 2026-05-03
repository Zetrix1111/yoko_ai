"""
api/config.py — endpoint genérico para Config_Empresa y Config_Ventas.

Consolida la persistencia del config editable en un solo handler. Las dos
tablas tienen el mismo shape (`empresa_id` + `data` long-text JSON), así
que un solo dispatcher por `?tipo=` evita duplicar código y nos mantiene
debajo del cap de 12 funciones de Vercel.

URLs:
  GET  /api/config?tipo=empresa  → {data: <objeto JSON o null>}
  GET  /api/config?tipo=ventas   → {data: <objeto JSON o null>}
  POST /api/config?tipo=empresa  → {ok: true}
  POST /api/config?tipo=ventas   → {ok: true}

Body del POST: `{"data": {...objeto JSON...}}`. Validación blanda — que sea
serializable y no exceda 100KB. No hay JSON Schema; las pantallas del
frontend son responsables de mandar la forma correcta.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client, config_loader              # noqa: E402
from _lib.airtable_client import AirtableError               # noqa: E402


_FALLBACK_TENANT = "cmejia"
_MAX_DATA_BYTES = 100_000

ALLOWED_TIPOS = {"empresa", "ventas"}
TABLE_BY_TIPO = {
    "empresa": "Config_Empresa",
    "ventas":  "Config_Ventas",
}


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID") or _FALLBACK_TENANT


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            tipo = self._get_tipo()
            if tipo is None:
                return  # _get_tipo ya respondió 400

            tenant_id = _tenant_id()
            try:
                rows = airtable_client.list_records(
                    TABLE_BY_TIPO[tipo],
                    filter_formula=f"{{empresa_id}} = '{tenant_id}'",
                    max_records=1,
                )
            except AirtableError as e:
                print(f"[config] AirtableError GET {tipo}: {e}", file=sys.stderr)
                return self._json(502, {"error": "No se pudo leer la configuración."})

            if not rows:
                return self._json(200, {"data": None})

            raw = rows[0].get("fields", {}).get("data") or "{}"
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, ValueError):
                data = None

            return self._json(200, {"data": data})

        except Exception as e:
            print(f"[config] Error GET: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    def do_POST(self):
        try:
            tipo = self._get_tipo()
            if tipo is None:
                return

            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "JSON inválido en el cuerpo."})

            data = body.get("data")
            if not isinstance(data, dict):
                return self._json(400, {"error": "Falta el campo 'data' (object)."})

            try:
                serialized = json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                return self._json(400, {"error": f"data no serializable: {e}"})
            if len(serialized.encode("utf-8")) > _MAX_DATA_BYTES:
                return self._json(400, {"error": "data excede 100KB."})

            tenant_id = _tenant_id()
            try:
                airtable_client.upsert_by_field(
                    TABLE_BY_TIPO[tipo],
                    match_field="empresa_id",
                    match_value=tenant_id,
                    fields={"data": serialized},
                )
            except AirtableError as e:
                print(f"[config] AirtableError POST {tipo}: {e}", file=sys.stderr)
                return self._json(502, {
                    "error": f"No se pudo guardar. Verificá que la tabla "
                             f"'{TABLE_BY_TIPO[tipo]}' exista en Airtable."
                })

            # Cache invalidation: la próxima request del agente lee fresh.
            config_loader.invalidate_cache()

            return self._json(200, {"ok": True})

        except Exception as e:
            print(f"[config] Error POST: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_tipo(self) -> str | None:
        qs = parse_qs(urlparse(self.path).query)
        tipo = (qs.get("tipo") or [""])[0]
        if tipo not in ALLOWED_TIPOS:
            self._json(400, {"error": f"tipo inválido. Use: {sorted(ALLOWED_TIPOS)}."})
            return None
        return tipo

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
