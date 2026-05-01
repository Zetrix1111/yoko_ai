"""
Script de prueba del prompt_builder. Carga la config completa y dumpea
el system prompt + la (todavía vacía) lista de tools.

Uso (desde la raíz del repo):
    python scripts/test_prompt.py
"""

import os
import sys


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


def main() -> int:
    _load_env_local()

    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from api._lib.config_loader import load_full_config
    from api._lib.prompt_builder import build_system_prompt, build_tools_list

    config = load_full_config()
    user = {"dni": "12345678", "nombre": "John", "cargo": "Programador"}

    print("=" * 72)
    print("SYSTEM PROMPT")
    print("=" * 72)
    print(build_system_prompt(config, user))
    print()
    print("=" * 72)
    print("TOOLS LIST (stub)")
    print("=" * 72)
    print(build_tools_list(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
