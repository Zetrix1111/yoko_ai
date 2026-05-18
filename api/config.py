"""
api/config.py — endpoint genérico para Config_Empresa, Config_Ventas y
master-data lookups (centros de costo).

Consolida persistencia + lecturas read-only de tablas relacionadas con la
configuración de empresa, en un solo handler. Un solo dispatcher por
`?tipo=` evita duplicar funciones serverless en Vercel.

URLs:
  GET  /api/config?tipo=empresa        → {data: <objeto JSON o null>}
  GET  /api/config?tipo=ventas         → {data: <objeto JSON o null>}
  POST /api/config?tipo=empresa        → {ok: true}
  POST /api/config?tipo=ventas         → {ok: true}
  GET  /api/config?tipo=centros_costo  → {centros: [{id, centro_costo, nombre, constituyen}]}

Body del POST: `{"data": {...objeto JSON...}}`. Validación blanda — que sea
serializable y no exceda 100KB. No hay JSON Schema; las pantallas del
frontend son responsables de mandar la forma correcta.

`centros_costo` es read-only (lee el maestro de centros de costo, no es config blob). POST
sobre ese tipo devuelve 405. El nombre `tipo=` se conserva por simetría
con el dispatcher genérico, aunque semánticamente es un master-data lookup.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client, auth, config_loader        # noqa: E402
from _lib.airtable_client import AirtableError               # noqa: E402
from _lib.auth import AuthError                              # noqa: E402


_MAX_DATA_BYTES = 100_000

ALLOWED_TIPOS = {"empresa", "ventas", "centros_costo"}

# Solo los tipos "data blob" (fila por empresa con JSON en `data`).
# `centros_costo` no entra acá: es un master-data lookup.
# y se maneja en una rama aparte.
TABLE_BY_TIPO = {
    "empresa": "Config_Empresa",
    "ventas":  "Config_Ventas",
}


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            try:
                auth_payload = auth.require_auth(self.headers)
            except AuthError as e:
                return self._json(e.status, {"error": str(e)})
            empresa_id = auth_payload["empresa_id"]

            tipo = self._get_tipo()
            if tipo is None:
                return  # _get_tipo ya respondió 400

            # Master-data lookup: lista de centros de costo del tenant.
            # de "fila por empresa con JSON en data" — devuelve N records.
            if tipo == "centros_costo":
                return self._get_centros_costo(empresa_id)

            try:
                rows = airtable_client.list_records(
                    TABLE_BY_TIPO[tipo],
                    filter_formula=f"{{empresa_id}} = '{empresa_id}'",
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
            try:
                auth_payload = auth.require_auth(self.headers)
            except AuthError as e:
                return self._json(e.status, {"error": str(e)})
            empresa_id = auth_payload["empresa_id"]

            tipo = self._get_tipo()
            if tipo is None:
                return

            # Master-data lookups son read-only.
            if tipo == "centros_costo":
                return self._json(405, {"error": "centros_costo es read-only."})

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

            try:
                airtable_client.upsert_by_field(
                    TABLE_BY_TIPO[tipo],
                    match_field="empresa_id",
                    match_value=empresa_id,
                    fields={"data": serialized},
                )
            except AirtableError as e:
                print(f"[config] AirtableError POST {tipo}: {e}", file=sys.stderr)
                return self._json(502, {
                    "error": f"No se pudo guardar. Verificá que la tabla "
                             f"'{TABLE_BY_TIPO[tipo]}' exista en Airtable."
                })

            # Cache invalidation: la próxima request del agente lee fresh,
            # solo para esta empresa (no afecta a otros tenants).
            config_loader.invalidate_cache(empresa_id)

            return self._json(200, {"ok": True})

        except Exception as e:
            print(f"[config] Error POST: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ── Master-data lookups ──────────────────────────────────────────────

    def _get_centros_costo(self, empresa_id: str):
        """
        Devuelve la lista de centros de costo del tenant.
        No es un blob de config — es un master-data lookup. Se sirve por este
        dispatcher para evitar gastar una función serverless aparte.
        """
        try:
            records = airtable_client.list_records(
                "centros_costo",
                filter_formula=f"{{empresa_id}}='{empresa_id}'",
                max_records=100,
            )
        except AirtableError as e:
            print(f"[config/centros_costo] AirtableError: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo consultar Airtable."})

        centros = []
        for r in records:
            f = r.get("fields", {})
            centro_costo = f.get("CENTRO_COSTO")
            if not centro_costo:
                continue
            centros.append({
                "id":          f.get("ID") or r.get("id"),
                "centro_costo": centro_costo,
                "nombre":      f.get("NOMBRE CENTRO COSTO", ""),
                "constituyen": f.get("CONSTITUYEN", ""),
            })
        return self._json(200, {"centros": centros})

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
