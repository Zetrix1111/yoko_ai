"""
api/empresa_config.py — CRUD del bloque empresa.info_extendida.

Métodos:
  GET   → devuelve el shape actual de info_extendida del tenant
            (Airtable si existe, sino el config.json estático, sino defaults).
  POST  → recibe el shape completo y lo persiste en Airtable.

Tabla Airtable: `Config_Empresa_Info`
  • empresa_id (Single line text)  → PK lógica (1 fila por tenant)
  • data       (Long text)         → JSON serializado del bloque info_extendida

Después de un POST exitoso invalidamos el cache del config_loader para que
el agente vea los cambios en la próxima request (sin esperar al TTL de 5min).

Validaciones:
  • Cada campo debe respetar shape {activo: bool, valor: <tipo correcto>}.
  • Campos no definidos en el schema se ignoran silenciosamente.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client                      # noqa: E402
from _lib import config_loader                        # noqa: E402
from _lib.airtable_client import AirtableError        # noqa: E402


_TABLA = "Config_Empresa_Info"
_FALLBACK_TENANT = "cmejia"


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID") or _FALLBACK_TENANT


def _validate_info_extendida(payload: dict) -> dict:
    """
    Acepta un payload del frontend y devuelve un dict listo para serializar.
    Campos no del schema → silenciosamente ignorados.
    Campos malformados → reemplazados por su default.
    """
    valid = config_loader._default_empresa_info_extendida()
    if not isinstance(payload, dict):
        return valid
    schema = config_loader._INFO_EXTENDIDA_SCHEMA
    for key, expected_default in schema.items():
        if key not in payload:
            continue
        incoming = payload[key]
        if not isinstance(incoming, dict):
            continue
        # activo: forzamos a bool
        if "activo" in incoming:
            valid[key]["activo"] = bool(incoming["activo"])
        # valor: validamos tipo según el campo
        if "valor" in incoming:
            v = incoming["valor"]
            if isinstance(expected_default, list):
                # redes_sociales: array de {red, url}
                if isinstance(v, list):
                    cleaned = []
                    for item in v:
                        if not isinstance(item, dict): continue
                        red = (item.get("red") or "").strip()
                        url = (item.get("url") or "").strip()
                        if red and url:
                            cleaned.append({"red": red, "url": url})
                    valid[key]["valor"] = cleaned
            elif isinstance(expected_default, str):
                valid[key]["valor"] = str(v) if v is not None else ""
            else:
                valid[key]["valor"] = v
    return valid


def _find_row(tenant_id: str) -> dict | None:
    """Busca la row del tenant en Config_Empresa_Info. None si no existe."""
    formula = f"{{empresa_id}}='{tenant_id}'"
    try:
        records = airtable_client.list_records(_TABLA, filter_formula=formula, max_records=1)
    except AirtableError as e:
        # Tabla no existe aún (404) → devolvemos None sin propagar error
        print(
            f"[empresa_config] No se pudo leer {_TABLA} (status={e.status}). "
            f"Probablemente la tabla aún no existe. Detalle: {e}",
            file=sys.stderr,
        )
        return None
    return records[0] if records else None


class handler(BaseHTTPRequestHandler):

    # ── GET ──────────────────────────────────────────────────────────────
    def do_GET(self):
        try:
            tenant = _tenant_id()
            # Reusamos load_full_config que ya hace el merge defaults ←
            # static ← dynamic. Garantiza que siempre devolvemos el shape
            # completo aunque la tabla esté vacía.
            try:
                full = config_loader.load_full_config()
            except AirtableError as e:
                print(f"[empresa_config] AirtableError GET: {e}", file=sys.stderr)
                return self._json(502, {"error": "No se pudo cargar la configuración."})
            empresa = (full or {}).get("empresa", {}) or {}
            info = empresa.get("info_extendida") or config_loader._default_empresa_info_extendida()
            return self._json(200, {
                "empresa_id":     tenant,
                "info_extendida": info,
            })
        except Exception as e:
            print(f"[empresa_config] Error GET: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ── POST: persiste el shape completo ────────────────────────────────
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length)) if length else {}
            except json.JSONDecodeError:
                return self._json(400, {"error": "JSON inválido en el cuerpo."})

            # El payload puede venir como `info_extendida: {...}` o ya como el dict directamente
            info_input = payload.get("info_extendida") if "info_extendida" in payload else payload
            if not isinstance(info_input, dict):
                return self._json(400, {"error": "Body debe contener un objeto info_extendida."})

            cleaned = _validate_info_extendida(info_input)
            tenant = _tenant_id()
            data_json = json.dumps(cleaned, ensure_ascii=False)

            existing = _find_row(tenant)
            try:
                if existing:
                    rec = airtable_client.update_record(_TABLA, existing["id"], {"data": data_json})
                else:
                    # Si la tabla no existe el create también va a fallar; mensaje claro al cliente.
                    rec = airtable_client.create_record(_TABLA, {
                        "empresa_id": tenant,
                        "data":       data_json,
                    })
            except AirtableError as e:
                print(f"[empresa_config] AirtableError persist: {e}", file=sys.stderr)
                return self._json(502, {
                    "error": "No se pudo persistir. Verificá que la tabla "
                             f"'{_TABLA}' exista en Airtable con columnas "
                             "'empresa_id' (Single line text) y 'data' (Long text)."
                })

            # Cache invalidation: la próxima request del agente arma el prompt fresh.
            config_loader.invalidate_cache()

            return self._json(200, {
                "ok":             True,
                "empresa_id":     tenant,
                "info_extendida": cleaned,
                "record_id":      rec.get("id"),
            })
        except Exception as e:
            print(f"[empresa_config] Error POST: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ── Helpers ──────────────────────────────────────────────────────────
    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
