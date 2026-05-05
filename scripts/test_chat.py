"""
Smoke test del pipeline de chat completo: extract_user → load_full_config
→ build_system_prompt + build_tools_list → run_chat (con tool calling).

NO usa HTTP ni el BaseHTTPRequestHandler — invoca las funciones del backend
directamente para diagnóstico rápido. La lógica HTTP de api/chat.py es un
wrapper delgado sobre estas mismas funciones.

Uso:
    python scripts/test_chat.py
    python scripts/test_chat.py "tu mensaje aquí"

Requiere en .env.local (o exportadas en el shell):
    OPENAI_API_KEY
    AIRTABLE_TOKEN, AIRTABLE_BASE_ID

NOTE: este script quedó desactualizado tras Fase 4 (multi-tenant por JWT) —
`load_full_config` ahora requiere empresa_id explícito y `prompt_builder` se
movió a `api/_yoko/_lib/prompt.py`. Conservado como referencia histórica;
para validar el pipeline real, usar el endpoint `/api/chat` vía curl con un
JWT válido.
"""

import json
import os
import sys

# UTF-8 en stdout para que corra en cmd/PowerShell de Windows.
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

    from api._lib import config_loader, openai_client, prompt_builder, session

    # Mensaje del usuario (CLI arg o default)
    user_text = sys.argv[1] if len(sys.argv) > 1 else "Hola, ¿cómo estás?"

    # Usamos un DNI real de cmejia para que el lookup a Empleados funcione
    # y para que las consultas a solicitudes_caja devuelvan datos reales.
    body = {
        "user": {
            "dni":    "41683585",  # PAUL PEÑALOZA en Empleados
            # nombre/cargo/email/celular se enriquecen vía lookup
        },
        "messages": [
            {"role": "user", "content": user_text},
        ],
    }

    print("=" * 72)
    print("INPUT")
    print("=" * 72)
    print(json.dumps(body, indent=2, ensure_ascii=False))

    # 1) Extraer usuario
    user = session.extract_user(body)
    print(f"\n[OK] extract_user: {user}")

    # 2) Cargar config
    config = config_loader.load_full_config()
    print(f"[OK] load_full_config: empresa={config['empresa']['id']}, "
          f"módulos={config['empresa']['modules']}")

    # 3) Armar prompt + tools
    system = prompt_builder.build_system_prompt(config, user)
    tools = prompt_builder.build_tools_list(config)
    print(f"[OK] build_system_prompt: {len(system)} chars")
    print(f"[OK] build_tools_list: {len(tools)} tools")

    # 4) Run chat
    print(f"\n>> Llamando a OpenAI ({openai_client._MODEL})...\n")
    result = openai_client.run_chat(
        system_prompt=system,
        messages=body["messages"],
        tools=tools,
        context={"user": user, "config": config},
    )

    print("=" * 72)
    print("OUTPUT")
    print("=" * 72)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
