"""
Smoke E2E del cerebro Claude Managed Agents.

Cubre el "happy path" estructural sin gastar créditos de Anthropic ni
requerir base de datos: imports, constantes centralizadas, contratos
del orquestador (handler_managed/handler_worker), `tool_executor`,
y un round-trip real contra Vercel KV si las credenciales están en el
entorno.

Diseñado para correr en local (post-refactor) y en CI:

    set -a; source .env.local; set +a   # para los tests con KV
    python scripts/test_managed_e2e.py

Estructura de bloques:
  1. **Estructural** (siempre corre): imports, constantes, simetría
     de extracciones (handler_managed limpio + tool_executor poblado).
  2. **task_store con KV** (skip si no hay creds): ciclo real
     create → get → mark_running → append → mark_done → delete.

Sale 0 si todo lo aplicable pasa. 1 si algo falla. Las secciones
saltadas se reportan como SKIP, no rompen.
"""

import os
import sys
import time
import uuid


def _setup_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.abspath(os.path.join(here, "..", "api"))
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)


def _ok(msg: str) -> None:
    print(f"OK   {msg}")


def _skip(msg: str) -> None:
    print(f"SKIP {msg}")


def _fail(msg: str, exc: Exception | None = None) -> None:
    print(f"FAIL {msg}", file=sys.stderr)
    if exc is not None:
        print(f"     {type(exc).__name__}: {exc}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────
# 1. Estructural — imports + constantes + simetría de extracciones
# ─────────────────────────────────────────────────────────────────────────

def test_imports() -> bool:
    """Todos los módulos del cerebro cargan sin error."""
    try:
        from _lib import _config, _http_utils, tool_executor  # noqa: F401
        from _lib import kv_client, airtable_client, managed_agents_client  # noqa: F401
        from _lib import yoko_session_store, yoko_task_store, yoko_cart_store  # noqa: F401
        from _yoko import handler_managed, handler_worker  # noqa: F401
        _ok("imports del cerebro completo")
        return True
    except Exception as e:
        _fail("imports del cerebro fallan", e)
        return False


def test_config_constants() -> bool:
    """_config.py expone los valores esperados."""
    from _lib import _config

    expected = {
        "SESSION_TTL_SECONDS":      4 * 60 * 60,   # 4 hrs
        "TASK_TTL_ACTIVE_SECONDS":  5 * 60,        # 5 min
        "TASK_TTL_FINAL_SECONDS":   60,            # 1 min
        "TOOL_HTTP_TIMEOUT_SECONDS": 120,          # 2 min
        "MAX_TURNS_PER_RUN":        8,
    }
    for name, want in expected.items():
        got = getattr(_config, name, None)
        if got != want:
            _fail(f"_config.{name} = {got!r}, esperado {want!r}")
            return False
    _ok(f"_config tiene las {len(expected)} constantes esperadas")
    return True


def test_stores_use_central_config() -> bool:
    """Los stores leen las constantes desde _config (no las redeclaran)."""
    from _lib import yoko_cart_store, yoko_session_store, yoko_task_store, _config

    cases = [
        ("yoko_cart_store.SESSION_TTL_SECONDS",
         yoko_cart_store.SESSION_TTL_SECONDS, _config.SESSION_TTL_SECONDS),
        ("yoko_session_store.SESSION_TTL_SECONDS",
         yoko_session_store.SESSION_TTL_SECONDS, _config.SESSION_TTL_SECONDS),
        ("yoko_task_store._TTL_ACTIVE",
         yoko_task_store._TTL_ACTIVE, _config.TASK_TTL_ACTIVE_SECONDS),
        ("yoko_task_store._TTL_FINAL",
         yoko_task_store._TTL_FINAL, _config.TASK_TTL_FINAL_SECONDS),
    ]
    for name, got, want in cases:
        if got != want:
            _fail(f"{name} = {got!r}, esperado {want!r} (drift respecto a _config)")
            return False
    _ok("stores leen TTLs desde _config (sin drift)")
    return True


def test_handler_managed_clean() -> bool:
    """handler_managed NO debe seguir exponiendo lo que se extrajo a tool_executor."""
    from _yoko import handler_managed

    leaked = [
        s for s in (
            "_exec_local_tool",
            "_TOOL_TO_ACTION",
            "_TOOL_HTTP_TIMEOUT",
            "_MAX_TURNS",
            "_filename_from_disposition",
        )
        if hasattr(handler_managed, s)
    ]
    if leaked:
        _fail(f"handler_managed todavía tiene símbolos extraídos: {leaked}")
        return False
    _ok("handler_managed limpio (símbolos extraídos a tool_executor)")
    return True


def test_tool_executor_contract() -> bool:
    """tool_executor expone la API que el worker espera, con los tools del agent."""
    from _lib import tool_executor

    if not callable(getattr(tool_executor, "execute_local_tool", None)):
        _fail("tool_executor.execute_local_tool no es callable")
        return False

    mapping = getattr(tool_executor, "TOOL_TO_ACTION", None)
    if not isinstance(mapping, dict):
        _fail(f"tool_executor.TOOL_TO_ACTION no es dict: {type(mapping).__name__}")
        return False

    expected_pairs = {
        "yoko_procesar_archivos":         "procesar-chat",
        "yoko_generar_registro_contable": "registro-contable-chat",
    }
    for tool_name, action in expected_pairs.items():
        if mapping.get(tool_name) != action:
            _fail(f"TOOL_TO_ACTION[{tool_name!r}] = {mapping.get(tool_name)!r}, "
                  f"esperado {action!r}")
            return False

    _ok(f"tool_executor expone API contractual ({len(expected_pairs)} tools mapeados)")
    return True


def test_filename_parser() -> bool:
    """_filename_from_disposition parsea Content-Disposition correctamente."""
    from _lib.tool_executor import _filename_from_disposition

    cases = [
        ('attachment; filename="registro.xlsx"', 'registro.xlsx'),
        ("attachment; filename=registro.xlsx",   "registro.xlsx"),
        ("",                                     "archivo"),  # fallback
        ("inline",                               "archivo"),  # sin filename=
    ]
    for header, want in cases:
        got = _filename_from_disposition(header)
        if got != want:
            _fail(f"_filename_from_disposition({header!r}) = {got!r}, esperado {want!r}")
            return False
    _ok(f"_filename_from_disposition parsea correctamente ({len(cases)} casos)")
    return True


# ─────────────────────────────────────────────────────────────────────────
# 2. task_store contra KV real — happy path completo
# ─────────────────────────────────────────────────────────────────────────

def test_task_store_lifecycle() -> bool:
    """
    Ciclo completo de un task: create → get → mark_running →
    append_accumulated → mark_done → delete.

    Skip si no hay credenciales de KV.
    """
    if not (os.environ.get("KV_REST_API_URL") and os.environ.get("KV_REST_API_TOKEN")):
        _skip("task_store lifecycle (sin KV_REST_API_URL/TOKEN)")
        return True

    from _lib import yoko_task_store

    # task_id único para no chocar con otros runs en paralelo.
    task_id = f"e2e-test-{uuid.uuid4().hex[:8]}"

    try:
        # create
        ok = yoko_task_store.create(
            task_id,
            session_id="sesn_e2e_dummy",
            user_id="e2e",
            empresa_id="e2e",
            user_content="hola e2e",
            auth_header="Bearer fake",
        )
        if not ok:
            _fail("task_store.create devolvió False")
            return False

        # get → status pending
        task = yoko_task_store.get(task_id)
        if not task or task.get("status") != "pending":
            _fail(f"tras create, status esperado 'pending'; got {task!r}")
            return False

        # mark_running
        yoko_task_store.mark_running(task_id)
        task = yoko_task_store.get(task_id)
        if task.get("status") != "running":
            _fail(f"tras mark_running, status = {task.get('status')!r}")
            return False

        # append_accumulated x2 (simula streaming)
        yoko_task_store.append_accumulated(task_id, "Hola ")
        yoko_task_store.append_accumulated(task_id, "mundo")
        task = yoko_task_store.get(task_id)
        if task.get("accumulated") != "Hola mundo":
            _fail(f"accumulated = {task.get('accumulated')!r}, esperado 'Hola mundo'")
            return False

        # mark_done con texto final
        yoko_task_store.mark_done(task_id, "Hola mundo final.")
        task = yoko_task_store.get(task_id)
        if task.get("status") != "done":
            _fail(f"tras mark_done, status = {task.get('status')!r}")
            return False
        if task.get("accumulated") != "Hola mundo final.":
            _fail(f"final accumulated = {task.get('accumulated')!r}")
            return False
        if not task.get("finished_at"):
            _fail("mark_done no setea finished_at")
            return False

        _ok(f"task_store lifecycle ({task_id}): pending→running→streaming→done")
        return True
    finally:
        # Cleanup (también ejerce el path delete)
        try:
            yoko_task_store.delete(task_id)
        except Exception as e:
            print(f"     warning: cleanup falló: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    _setup_path()

    print("=" * 64)
    print(" Smoke E2E — cerebro Managed Agents (refactor sanity)")
    print("=" * 64)

    started = time.time()
    tests = [
        test_imports,
        test_config_constants,
        test_stores_use_central_config,
        test_handler_managed_clean,
        test_tool_executor_contract,
        test_filename_parser,
        test_task_store_lifecycle,
    ]

    results = []
    for fn in tests:
        try:
            results.append(fn())
        except Exception as e:
            _fail(f"{fn.__name__} crashed", e)
            results.append(False)

    elapsed = time.time() - started
    passed = sum(1 for r in results if r)
    total = len(results)

    print("=" * 64)
    print(f" {passed}/{total} OK en {elapsed:.2f}s")
    print("=" * 64)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
