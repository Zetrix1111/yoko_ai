"""
Script de prueba del tool_registry + consulta tools.

Uso (desde la raíz del repo):
    python scripts/test_tool.py
"""

import json
import os
import sys

# Forzamos UTF-8 en stdout para que corra sin crash en cmd/PowerShell de Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def _load_env_local() -> None:
    """Carga `.env.local` sin pisar variables ya seteadas en el entorno."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    env_path = os.path.join(repo_root, ".env.local")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _setup_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def main() -> int:
    _load_env_local()
    _setup_path()

    from api._lib.config_loader import load_full_config
    from api._lib.tool_registry import execute_tool, get_openai_tools_array

    # Importa los 3 módulos de tools — el side-effect del decorador las registra.
    import api._lib.tools.consulta    # noqa: F401
    import api._lib.tools.accion      # noqa: F401
    import api._lib.tools.navegacion  # noqa: F401

    config = load_full_config()
    user = {"dni": "12345678", "nombre": "John", "cargo": "Programador"}
    ctx = {"config": config, "user": user}

    # ── 1) Lista de schemas para OpenAI ──
    print("=" * 72)
    print("TOOLS REGISTRADAS (formato OpenAI)")
    print("=" * 72)
    tools_array = get_openai_tools_array(config.get("empresa", {}).get("modules", []))
    print(f"Total: {len(tools_array)}\n")
    for t in tools_array:
        f = t["function"]
        params = f["parameters"]
        required = params.get("required", [])
        props = list((params.get("properties") or {}).keys())
        print(f"  • {f['name']}  ({', '.join(props) or 'sin args'})  [required: {required}]")

    # ── 2) Ejecutar una consulta que va a Airtable ──
    print()
    print("=" * 72)
    print("execute_tool('consultar_solicitudes_por_dni', {'dni': '12345678'})")
    print("=" * 72)
    result = execute_tool("consultar_solicitudes_por_dni", {"dni": "12345678"}, ctx)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    # ── 3) Ejecutar una consulta que lee del config (no toca Airtable) ──
    print()
    print("=" * 72)
    print("execute_tool('consultar_centros_costo', {})")
    print("=" * 72)
    result = execute_tool("consultar_centros_costo", {}, ctx)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    # ── 4) Ejecutar tope_disponible ──
    print()
    print("=" * 72)
    print("execute_tool('consultar_tope_disponible', {dni, origen='sede'})")
    print("=" * 72)
    result = execute_tool(
        "consultar_tope_disponible",
        {"dni": "12345678", "origen": "sede"},
        ctx,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    # ── 5) Probar manejo de errores: tool inexistente ──
    print()
    print("=" * 72)
    print("execute_tool('tool_inexistente', {})  → debe devolver 'interno'")
    print("=" * 72)
    result = execute_tool("tool_inexistente", {}, ctx)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
