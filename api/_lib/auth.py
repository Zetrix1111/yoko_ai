"""
Helpers de autenticación para el backend multi-tenant.

Tres responsabilidades:

  • Verificar passwords contra hashes bcrypt almacenados en Airtable.
  • Emitir JWTs HS256 con TTL de 30 días.
  • Validar el header `Authorization: Bearer <jwt>` que el frontend
    manda en cada request a los endpoints protegidos.

`AuthError` es la única excepción que tira este módulo. Su atributo
`status` indica el código HTTP que el handler debe devolver. Los
endpoints solo necesitan capturar `AuthError` y mapearlo a `_json(e.status, ...)`.

Variables de entorno:
  • JWT_SECRET — string de >=32 chars. Se valida al cargarlo. Si falta
    o es corto, `AuthError(status=500)` con mensaje claro a stderr.
"""

from __future__ import annotations

import os
import sys
import time

import bcrypt
import jwt


JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 30 * 24 * 3600   # 30 días
_MIN_SECRET_LEN = 32


class AuthError(Exception):
    """
    Error de autenticación. El handler lo captura y devuelve `e.status`
    como código HTTP. El mensaje (str(e)) se usa para el campo `error`
    de la respuesta cuando es seguro filtrarlo al cliente.
    """

    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


# ─────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────

def _get_secret() -> str:
    """
    Lee y valida JWT_SECRET. El backend NO arranca sin este secret —
    si falta se lanza AuthError(status=500) que se logguea a stderr.

    Generación recomendada: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
    """
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        print("[auth] JWT_SECRET no está definido en el entorno.", file=sys.stderr)
        raise AuthError("Configuración del servidor incompleta.", status=500)
    if len(secret) < _MIN_SECRET_LEN:
        print(
            f"[auth] JWT_SECRET es demasiado corto "
            f"(len={len(secret)}, mínimo {_MIN_SECRET_LEN}).",
            file=sys.stderr,
        )
        raise AuthError("Configuración del servidor incompleta.", status=500)
    return secret


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    """
    Compara un password en texto plano contra un hash bcrypt almacenado.
    Devuelve False ante cualquier formato inválido (no levanta).

    `hashed` se acepta como str (UTF-8). bcrypt opera en bytes, así que
    convertimos. Un hash bcrypt válido tiene la forma `$2b$XX$...`.
    """
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash malformado en Airtable (string vacío, formato roto, etc.)
        return False


def issue_jwt(
    user_id: str,
    email: str,
    empresa_id: str,
    modulos: list[str],
) -> str:
    """
    Emite un JWT HS256 con TTL de 30 días.

    Payload:
      sub         — record_id del usuario en la tabla Usuarios
      email       — email lowercase del usuario
      empresa_id  — slug del tenant (cmejia, demo, ...)
      modulos     — lista de módulos habilitados para esa empresa
      iat         — issued-at (unix timestamp)
      exp         — expiration (iat + TTL)
    """
    now = int(time.time())
    payload = {
        "sub":        user_id,
        "email":      email,
        "empresa_id": empresa_id,
        "modulos":    list(modulos or []),
        "iat":        now,
        "exp":        now + JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def verify_jwt(authorization_header: str | None) -> dict:
    """
    Valida el header `Authorization: Bearer <jwt>` y devuelve el payload
    decodificado. Lanza `AuthError(status=401)` si:
      • el header falta o no empieza con "Bearer "
      • el token está vencido (exp < now)
      • la firma es inválida
      • cualquier otro error de parseo
    """
    if not authorization_header:
        raise AuthError("Falta el header Authorization.")

    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthError("Header Authorization mal formado. Esperado 'Bearer <jwt>'.")

    token = parts[1].strip()
    try:
        return jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token vencido. Volvé a iniciar sesión.")
    except jwt.InvalidTokenError as e:
        # Cubre InvalidSignatureError, DecodeError, etc.
        raise AuthError(f"Token inválido: {e}")


def require_auth(headers) -> dict:
    """
    Lee el header `Authorization` y valida el JWT. Devuelve el payload
    decodificado: `{sub, email, empresa_id, modulos, iat, exp}`.

    Acepta tanto el `self.headers` de un BaseHTTPRequestHandler (objeto
    `email.message.Message` con método `.get()`) como un dict plano. Si
    falta el header, propagamos `AuthError(status=401)` que el handler
    debe capturar y mapear al status HTTP de la respuesta.

    Patrón de uso en cada handler:

        try:
            auth_payload = auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})
        empresa_id = auth_payload["empresa_id"]
    """
    auth_header = headers.get("Authorization") or headers.get("authorization")
    return verify_jwt(auth_header)
