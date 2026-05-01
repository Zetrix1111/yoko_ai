"""
Script de prueba: carga la config completa y la imprime.

Uso (desde la raíz del repo):
    python scripts/test_config.py

Requiere las env vars (de tu .env.local o de tu shell):
    AIRTABLE_TOKEN
    AIRTABLE_BASE_ID
    TENANT_ID            (opcional; cae a 'cmejia' con warning)

Si las tablas Config_* todavía no existen en Airtable, el loader
imprime warnings y sigue, devolviendo listas/dicts vacíos para
las secciones dinámicas. La estática (empresa) siempre se llena.
"""

import json
import os
import sys


def _load_env_local() -> None:
    """
    Carga variables desde `.env.local` en la raíz del repo si existen,
    sin pisar las que ya estén exportadas en el entorno. Evita depender
    de python-dotenv (queremos cero deps fuera de openai).
    """
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
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def main() -> int:
    _load_env_local()

    # Aseguramos que el repo root esté en sys.path para importar `api._lib`
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from api._lib.config_loader import load_full_config

    config = load_full_config()
    print(json.dumps(config, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
