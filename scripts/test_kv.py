"""
Smoke test del cliente Vercel KV (Upstash REST) y del session store de Yoko.

Requiere las env vars `KV_REST_API_URL` y `KV_REST_API_TOKEN` en el entorno
local. Para tomarlas de Vercel:

    vercel env pull .env.local
    # luego cargá .env.local antes de correr (set -a; source .env.local; set +a)
    python scripts/test_kv.py

Verifica:
  - kv_set / kv_get / kv_delete / kv_exists (operaciones básicas)
  - kv_delete idempotente sobre clave inexistente
  - yoko_session_store: store -> get -> force_new -> get None
  - get_session_metadata recupera los campos esperados

Sale 0 si todo pasa, 1 si algo falla.
"""

import os
import sys


def _setup_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.abspath(os.path.join(here, "..", "api"))
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    _setup_path()

    if not os.environ.get("KV_REST_API_URL") or not os.environ.get("KV_REST_API_TOKEN"):
        print("X Faltan KV_REST_API_URL / KV_REST_API_TOKEN en el entorno.")
        print("  Tip: corré `vercel env pull .env.local` y cargá esas vars antes.")
        return 1

    from _lib.kv_client import KVError, kv_delete, kv_exists, kv_get, kv_set
    from _lib import yoko_session_store as ss

    failures: list[str] = []
    total = 0

    def check(cond: bool, msg: str) -> None:
        nonlocal total
        total += 1
        if not cond:
            failures.append(msg)

    test_key = "yoko:smoketest:hello"

    try:
        # ── T1: estado inicial limpio ──────────────────────────────────
        kv_delete(test_key)
        check(not kv_exists(test_key), "T1: clave no debe existir tras delete")
        check(kv_get(test_key) is None, "T1: kv_get devuelve None en clave ausente")

        # ── T2: SET / GET / EXISTS ─────────────────────────────────────
        ok = kv_set(test_key, "world", ttl_seconds=60)
        check(ok, "T2: kv_set devuelve True")
        check(kv_get(test_key) == "world", "T2: kv_get devuelve el valor seteado")
        check(kv_exists(test_key), "T2: kv_exists True tras set")

        # ── T3: DEL ────────────────────────────────────────────────────
        deleted = kv_delete(test_key)
        check(deleted, "T3: kv_delete devuelve True para clave existente")
        check(kv_get(test_key) is None, "T3: kv_get None tras delete")
        check(not kv_exists(test_key), "T3: kv_exists False tras delete")

        # ── T4: DEL idempotente ────────────────────────────────────────
        deleted2 = kv_delete(test_key)
        check(not deleted2, "T4: kv_delete sobre inexistente devuelve False")

        # ── T5: yoko_session_store ─────────────────────────────────────
        ss.force_new_session("smoketest", "user_x")
        check(
            ss.get_session_id("smoketest", "user_x") is None,
            "T5: get_session_id pre-store devuelve None",
        )

        ss.store_session(
            "smoketest", "user_x", "sess_abc123",
            extra_metadata={"agent_id": "agent_test"},
        )
        check(
            ss.get_session_id("smoketest", "user_x") == "sess_abc123",
            "T5: get_session_id devuelve el session_id guardado",
        )

        meta = ss.get_session_metadata("sess_abc123")
        check(meta is not None, "T5: metadata existe tras store")
        check(
            meta and meta.get("empresa_id") == "smoketest",
            "T5: metadata.empresa_id correcto",
        )
        check(
            meta and meta.get("user_id") == "user_x",
            "T5: metadata.user_id correcto",
        )
        check(
            meta and meta.get("agent_id") == "agent_test",
            "T5: extra_metadata se incluye",
        )
        check(
            meta and "created_at" in meta,
            "T5: metadata.created_at presente",
        )

        # ── T6: force_new_session limpia ambas claves ──────────────────
        ss.force_new_session("smoketest", "user_x")
        check(
            ss.get_session_id("smoketest", "user_x") is None,
            "T6: force_new_session limpia el cache",
        )
        check(
            ss.get_session_metadata("sess_abc123") is None,
            "T6: force_new_session también borra metadata",
        )

    except KVError as e:
        print(f"\nX Error de KV: {e}", file=sys.stderr)
        return 1

    passed = total - len(failures)
    print(f"\n{passed}/{total} aserciones pasaron.")
    if failures:
        print("\nFallaron:")
        for m in failures:
            print(f"  X {m}")
        return 1
    print("OK Todos los tests pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
