"""
scripts/generate_jwt_token.py

Genera un JWT firmado por `JWT_SECRET` pensado para guardarse en el Vault
de Anthropic Managed Agents (`yoko-{empresa}`). El agent lo usaría cuando
ejecuta llamadas HTTP directas a la API Yoko desde su sandbox.

En el MVP actual el token NO está en el hot path: el orquestador
(`api/_yoko/handler_managed.py`) intercepta los tool_use del agent y reenvía
el JWT del usuario. El Vault token queda provisionado igual para forward-
compat (cuando el agent ejecute código en el sandbox que llame a la API).

Uso:
    # 1. Cargar JWT_SECRET (mismo que el de la app — Vercel)
    vercel env pull .env.local
    set -a; source .env.local; set +a

    # 2. Generar y copiar al portapapeles (Linux/Mac):
    python scripts/generate_jwt_token.py --empresa cmejia --quiet | pbcopy

    # 3. Pegar el token en el Vault yoko-cmejia como YOKO_API_TOKEN.
    #    También agregar YOKO_API_BASE=https://yokochat.vercel.app

Estructura del payload:
  sub:        identificador (no es un user real; default "agent-service")
  email:      "" (vacío — el agent no es persona)
  empresa_id: el tenant (cmejia, demo, ...)
  modulos:    lista (opcional; el agent no la consulta hoy)
  scope:      "agent" (claim nuevo — sirve a futuro para diferenciar de
              tokens de usuario; `auth.require_auth` actual lo ignora)
  iat / exp:  unix timestamps. Default: ahora + 365 días.
"""

import argparse
import os
import sys
import time
from pathlib import Path


def _setup_path() -> None:
    """Permite importar `_lib` para reutilizar la constante JWT_ALGORITHM."""
    here = Path(__file__).resolve().parent
    api_dir = here.parent / "api"
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="Genera un JWT scoped para el Vault del agent.",
    )
    parser.add_argument(
        "--empresa",
        default="cmejia",
        help="empresa_id del tenant (default: cmejia)",
    )
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=365,
        help="TTL del token en días (default: 365)",
    )
    parser.add_argument(
        "--modulos",
        default="",
        help="Módulos habilitados separados por coma (opcional)",
    )
    parser.add_argument(
        "--scope",
        default="agent",
        help="Scope claim del token (default: agent)",
    )
    parser.add_argument(
        "--sub",
        default="agent-service",
        help="Sub claim — identificador del 'usuario' (default: agent-service)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Imprime solo el token (sin metadata humana — útil con pipes)",
    )
    args = parser.parse_args()

    _setup_path()

    secret = os.environ.get("JWT_SECRET")
    if not secret:
        print("X Falta JWT_SECRET en el entorno.", file=sys.stderr)
        print(
            "  Tip: `vercel env pull .env.local` y cargá esa env var antes.",
            file=sys.stderr,
        )
        return 1
    if len(secret) < 32:
        print(
            f"X JWT_SECRET es demasiado corto (len={len(secret)}, mín 32).",
            file=sys.stderr,
        )
        return 1

    try:
        import jwt as pyjwt
    except ImportError:
        print("X PyJWT no está instalado. Corré `pip install -e .` primero.", file=sys.stderr)
        return 1

    # Importar la constante para no hardcodear el algoritmo en dos lugares.
    try:
        from _lib.auth import JWT_ALGORITHM
    except ImportError:
        JWT_ALGORITHM = "HS256"

    modulos = [m.strip() for m in (args.modulos or "").split(",") if m.strip()]

    now = int(time.time())
    payload = {
        "sub":        args.sub,
        "email":      "",
        "empresa_id": args.empresa,
        "modulos":    modulos,
        "scope":      args.scope,
        "iat":        now,
        "exp":        now + args.ttl_days * 24 * 3600,
    }

    token = pyjwt.encode(payload, secret, algorithm=JWT_ALGORITHM)

    if args.quiet:
        print(token)
        return 0

    print("=" * 64)
    print("JWT generado para el Vault del agent")
    print("=" * 64)
    print(f"empresa_id: {args.empresa}")
    print(f"scope:      {args.scope}")
    print(f"sub:        {args.sub}")
    print(f"modulos:    {modulos or '(ninguno)'}")
    print(f"iat:        {now}")
    print(f"exp:        {payload['exp']}  (~{args.ttl_days} días)")
    print()
    print("Token:")
    print(token)
    print()
    print(f"Pegalo en el Vault yoko-{args.empresa} como `YOKO_API_TOKEN`.")
    print("También agregá `YOKO_API_BASE=https://yokochat.vercel.app` al Vault.")
    print()
    print(
        "Nota: en el MVP actual el orquestador reenvía el JWT del usuario, "
        "así que este token queda dormido en el Vault para forward-compat. "
        "Si en una iteración futura el agent ejecuta código en el sandbox "
        "y llama directo a /api/facturas, este token entra en uso.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
