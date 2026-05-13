"""
scripts/smoke_meta_jw.py — smoke E2E offline para `jw_seguridad`.

Valida en orden: env vars → meta_connections → ping Graph API /me →
cerebro de ventas devuelve texto. NO manda mensajes a WhatsApp; sirve
para confirmar que toda la cadena de credenciales/config está OK antes
de exponer el número real al público.

Uso (desde la raíz del repo):

  set -a; source .env.local; set +a        # cargar env de Vercel
  python scripts/smoke_meta_jw.py

Sale 0 si los 4 pasos pasan, 1 si algo falla.
"""

import json
import os
import sys
import urllib.error
import urllib.request


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "api"))


EMPRESA_ID = "jw_seguridad"
_GRAPH_BASE = "https://graph.facebook.com/v23.0"


def _step(n: int, msg: str) -> None:
    print(f"\n[{n}] {msg}")


def _ok(msg: str) -> None:
    print(f"  OK   {msg}")


def _fail(msg: str) -> None:
    print(f"  FAIL {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    # 1. Variables de entorno requeridas
    _step(1, "Verificando env vars")
    for v in ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID"):
        if not os.environ.get(v):
            _fail(f"falta env var: {v}")
    _ok("env vars presentes")

    # 2. Lookup en meta_connections
    _step(2, f"Leyendo meta_connections para {EMPRESA_ID}")
    from _lib import meta_connections  # noqa: E402

    conn = meta_connections.get_by_empresa_id(EMPRESA_ID)
    if not conn:
        _fail(
            "no hay fila activa en meta_connections "
            "(activo=TRUE, access_token y phone_number_id no vacíos)"
        )
    pid = conn.get("phone_number_id") or ""
    waba = conn.get("waba_id") or ""
    if not pid:
        _fail("phone_number_id vacío en meta_connections")
    _ok(f"phone_number_id={pid} waba_id={waba}")

    # 3. Token Meta vivo (ping a /me)
    _step(3, "Ping a Graph API /me con access_token")
    token = conn.get("access_token") or ""
    if not token:
        _fail("access_token vacío")
    url = f"{_GRAPH_BASE}/me?access_token={token}"
    try:
        with urllib.request.urlopen(url, timeout=10) as res:
            data = json.loads(res.read())
        _ok(f"Graph OK, id={data.get('id')}")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read()[:200].decode("utf-8", "ignore")
        except Exception:
            pass
        _fail(f"Graph HTTP {e.code}: {body}")
    except Exception as e:
        _fail(f"Graph error: {type(e).__name__}: {e}")

    # 4. Cerebro responde con texto
    _step(4, "Invocando process_message del cerebro de ventas (channel=meta)")
    from _ventas import chat as ventas_chat  # noqa: E402

    try:
        result = ventas_chat.process_message(
            empresa_id=EMPRESA_ID,
            phone="51999000111",  # número de prueba ficticio
            nombre="Smoke Test",
            history=[{"role": "user", "content": "Hola, qué venden?"}],
            channel="meta",
        )
    except Exception as e:
        _fail(f"process_message excepción: {type(e).__name__}: {e}")

    reply = (result.get("reply") or "").strip()
    if not reply:
        _fail("reply vacío")
    media_n = len(result.get("media_urls") or [])
    _ok(f"reply ({len(reply)} chars) + {media_n} media_urls")
    print(f"       preview: {reply[:120]!r}…")

    print("\nSMOKE OK — todo conectado y listo para mensaje real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
