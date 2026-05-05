"""
api/login.py — endpoint de autenticación multi-tenant.

POST con `{"email": "...", "password": "..."}`. Si las credenciales son
correctas y tanto el usuario como la empresa están activos, devuelve un
JWT HS256 (TTL 30 días) + datos básicos del usuario y la empresa para
que el frontend rendere su UI sin hacer un GET adicional.

El JWT es self-contained: incluye `empresa_id` y `modulos` para que los
demás endpoints resuelvan el tenant del usuario sin tocar Airtable
nuevamente. Cuando el JWT vence, el frontend re-loguea.

Errores siempre genéricos al cliente — no filtrar si fue email o password
lo que falló (anti-enumeration). Detalle interno solo a stderr.

Códigos:
  200  → login OK
  400  → JSON inválido o email mal formado
  401  → email o password incorrectos / token issues
  403  → cuenta o empresa desactivada
  500  → JWT_SECRET no configurado, o inconsistencia en Airtable
  502  → falla de Airtable
"""

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler


# Bootstrap: api/ al sys.path para que los `from _lib import ...` resuelvan
# correctamente, igual que el resto de los handlers serverless.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client, auth                  # noqa: E402
from _lib.airtable_client import AirtableError          # noqa: E402
from _lib.auth import AuthError                         # noqa: E402


_TABLA_USUARIOS = "Usuarios"
_TABLA_EMPRESAS = "Empresas"
_TABLA_EMPLEADOS = "Empleados"

# Email validation conservadora — si el email tiene comillas o caracteres
# raros lo rechazamos antes de construir el filterByFormula de Airtable
# (Airtable no soporta escape de comillas dentro de la fórmula).
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_GENERIC_INVALID_CREDS = "Email o contraseña incorrectos."


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            body = self._read_json_body()
            if body is None:
                return self._json(400, {"error": "JSON inválido en el cuerpo de la solicitud."})

            email = str(body.get("email", "")).strip().lower()
            password = str(body.get("password", ""))

            if not _EMAIL_RE.match(email):
                return self._json(400, {"error": "Email inválido."})
            if not password:
                return self._json(401, {"error": _GENERIC_INVALID_CREDS})

            # ── 1. Buscar usuario por email ──────────────────────────────
            try:
                user_rec = self._find_usuario(email)
            except AirtableError as e:
                print(f"[login] AirtableError buscando Usuarios: {e}", file=sys.stderr)
                return self._json(502, {"error": "Error al consultar la base de datos."})

            if user_rec is None:
                return self._json(401, {"error": _GENERIC_INVALID_CREDS})

            user_fields = user_rec.get("fields", {}) or {}
            password_hash = user_fields.get("password_hash") or ""

            # ── 2. Verificar password ────────────────────────────────────
            if not auth.verify_password(password, password_hash):
                return self._json(401, {"error": _GENERIC_INVALID_CREDS})

            # ── 3. Usuario activo? ───────────────────────────────────────
            if not _coerce_bool(user_fields.get("activo"), default=True):
                return self._json(403, {"error": "Tu cuenta está desactivada."})

            empresa_id = (user_fields.get("empresa_id") or "").strip()
            if not empresa_id:
                print(
                    f"[login] Usuario {user_rec.get('id')} sin empresa_id asignado.",
                    file=sys.stderr,
                )
                return self._json(500, {"error": "Configuración de cuenta incompleta."})

            # ── 4. Buscar empresa ────────────────────────────────────────
            try:
                empresa_rec = self._find_empresa(empresa_id)
            except AirtableError as e:
                print(f"[login] AirtableError buscando Empresas: {e}", file=sys.stderr)
                return self._json(502, {"error": "Error al consultar la base de datos."})

            if empresa_rec is None:
                print(
                    f"[login] Inconsistencia: usuario {user_rec.get('id')} apunta a "
                    f"empresa_id='{empresa_id}' que no existe en la tabla Empresas.",
                    file=sys.stderr,
                )
                return self._json(500, {"error": "Configuración de cuenta incompleta."})

            empresa_fields = empresa_rec.get("fields", {}) or {}

            # ── 5. Empresa activa? ───────────────────────────────────────
            if not _coerce_bool(empresa_fields.get("activo"), default=True):
                return self._json(403, {"error": "Tu empresa está desactivada."})

            modulos = _normalize_modulos(empresa_fields.get("modulos_habilitados"))

            # ── 6. Enriquecimiento OPCIONAL: lookup en Empleados ────────
            # Si el email tiene un Empleado asociado, copiamos dni / cargo /
            # celular al user de la respuesta. Esto mantiene compat con el
            # backend del chat (api/chat.py + session.extract_user) que
            # todavía espera user.dni en el body. Si Empleados falla o no
            # existe la fila, NO rompemos el login — es enriquecimiento.
            empleado_extra = self._fetch_empleado_extra(email)

            # ── 7. Emitir JWT ────────────────────────────────────────────
            try:
                token = auth.issue_jwt(
                    user_id=user_rec.get("id", ""),
                    email=email,
                    empresa_id=empresa_id,
                    modulos=modulos,
                )
            except AuthError as e:
                # Casi siempre: JWT_SECRET mal configurado.
                return self._json(e.status, {"error": str(e)})

            # ── 8. Respuesta ─────────────────────────────────────────────
            user_payload: dict = {
                "id":     user_rec.get("id", ""),
                "email":  email,
                "nombre": user_fields.get("nombre", ""),
            }
            # Merge enriquecimiento — solo agrega claves que existan y no estén vacías.
            for k in ("dni", "cargo", "celular"):
                v = empleado_extra.get(k, "")
                if v:
                    user_payload[k] = v

            return self._json(200, {
                "token":   token,
                "user":    user_payload,
                "empresa": {
                    "id":           empresa_id,
                    "razon_social": empresa_fields.get("razon_social", ""),
                    "modulos":      modulos,
                },
            })

        except AuthError as e:
            return self._json(e.status, {"error": str(e)})
        except Exception as e:
            print(f"[login] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ── Airtable lookups ────────────────────────────────────────────────

    def _find_usuario(self, email: str) -> dict | None:
        """email ya viene lowercase y validado contra `_EMAIL_RE`."""
        formula = f"LOWER({{email}})='{email}'"
        records = airtable_client.list_records(
            _TABLA_USUARIOS, filter_formula=formula, max_records=1,
        )
        return records[0] if records else None

    def _find_empresa(self, empresa_id: str) -> dict | None:
        # empresa_id es slug controlado (cmejia, demo, ...) — sin caracteres
        # que necesiten escape en filterByFormula.
        formula = f"{{empresa_id}}='{empresa_id}'"
        records = airtable_client.list_records(
            _TABLA_EMPRESAS, filter_formula=formula, max_records=1,
        )
        return records[0] if records else None

    def _fetch_empleado_extra(self, email: str) -> dict[str, str]:
        """
        Lookup opcional de la fila en Empleados que matchea el email del
        usuario. Devuelve {dni, cargo, celular} con strings limpios.

        Si Airtable falla o no hay fila, devuelve {} silenciosamente —
        este enriquecimiento NO debe romper el login. Detalle a stderr.
        """
        try:
            formula = f"LOWER({{EMAIL}})='{email}'"
            records = airtable_client.list_records(
                _TABLA_EMPLEADOS, filter_formula=formula, max_records=1,
            )
        except AirtableError as e:
            print(
                f"[login] No se pudo enriquecer desde Empleados ({email}): {e}",
                file=sys.stderr,
            )
            return {}

        if not records:
            return {}

        f = records[0].get("fields", {}) or {}
        return {
            "dni":     str(f.get("DNI", "") or "").strip(),
            "cargo":   str(f.get("PUESTO", "") or "").strip(),
            "celular": str(f.get("CELULAR", "") or "").strip(),
        }

    # ── HTTP helpers ────────────────────────────────────────────────────

    def _read_json_body(self) -> dict | None:
        """Devuelve el body parseado, o None si el JSON es inválido."""
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silenciar logs de acceso HTTP


# ─────────────────────────────────────────────────────────────────────────
# Helpers locales
# ─────────────────────────────────────────────────────────────────────────

def _coerce_bool(value, *, default: bool) -> bool:
    """
    Airtable devuelve checkboxes como bool, pero por si el campo está
    vacío o llega como string ('true' / 'false' / '1' / '0'), normalizamos.
    `default` se usa cuando el campo está ausente del registro.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "sí", "si", "on")
    return default


def _normalize_modulos(raw) -> list[str]:
    """
    `modulos_habilitados` es multipleSelects en Airtable → llega como
    lista de strings. Pero protegemos del caso legacy donde quedó como
    string `"[a, b, c]"` o `"a, b, c"`.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(m).strip() for m in raw if str(m).strip()]
    if isinstance(raw, str):
        s = raw.strip().lstrip("[").rstrip("]")
        return [
            m.strip().strip("\"'")
            for m in s.split(",")
            if m.strip()
        ]
    return []
