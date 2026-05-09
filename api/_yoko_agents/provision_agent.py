"""
Script idempotente que crea o actualiza el agent "yoko-empresarial" en
Anthropic Managed Agents.

Uso:
    python -m api._yoko_agents.provision_agent

Comportamiento:
  - Si NO existe `YOKO_AGENT_ID` en env: crea agent nuevo, imprime el id e
    instruye al owner a guardarlo en Vercel.
  - Si SÍ existe `YOKO_AGENT_ID`: hace GET para verificar que el agent
    todavía existe, después PATCH/POST con la configuración nueva.
  - Idempotente: correrlo dos veces seguidas funciona — la segunda corrida
    es no-op si nada cambió en el repo.

Imprime un resumen legible de qué cambió (sysprompt size, tools, skills).
"""

import os
import sys
from pathlib import Path


def _setup_path() -> None:
    """Permite ejecutar el script con `python api/_yoko_agents/provision_agent.py`
    además de `python -m api._yoko_agents.provision_agent`."""
    here = Path(__file__).resolve().parent
    api_dir = here.parent
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))


def _summary(config: dict) -> str:
    sys_len = len(config.get("system") or "")
    n_tools = len(config.get("tools") or [])
    n_skills = len(config.get("skills") or [])
    skill_names = ", ".join(s["name"] for s in (config.get("skills") or []))
    return (
        f"  name:       {config.get('name')}\n"
        f"  model:      {config.get('model')}\n"
        f"  system:     {sys_len} chars\n"
        f"  tools ({n_tools}): "
        + ", ".join(t["name"] for t in (config.get("tools") or []))
        + "\n"
        f"  skills ({n_skills}): {skill_names or '(ninguna)'}\n"
        f"  environment_id: {config.get('environment_id') or '(no seteado)'}"
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    _setup_path()

    from _lib import managed_agents_client as mac
    from _yoko_agents.agent_definition import get_agent_config

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("X Falta ANTHROPIC_API_KEY en el entorno.", file=sys.stderr)
        print("  Tip: vercel env pull .env.local && source .env.local", file=sys.stderr)
        return 1

    try:
        config = get_agent_config()
    except (FileNotFoundError, ValueError) as e:
        print(f"X No se pudo construir la config del agent: {e}", file=sys.stderr)
        return 1

    print("→ Configuración a aplicar:")
    print(_summary(config))
    print()

    agent_id = os.environ.get("YOKO_AGENT_ID")

    try:
        if agent_id:
            print(f"→ Modo UPDATE (YOKO_AGENT_ID={agent_id})")
            existing = mac.get_agent(agent_id)
            if existing is None:
                print(
                    f"X El agent {agent_id} no existe en Anthropic. "
                    "Quitá YOKO_AGENT_ID del env y volvé a correr para crear uno nuevo.",
                    file=sys.stderr,
                )
                return 1
            updated = mac.update_agent(agent_id, config)
            print(f"OK Agent {agent_id} actualizado.")
            if "updated_at" in updated:
                print(f"   updated_at: {updated['updated_at']}")
        else:
            print("→ Modo CREATE (no hay YOKO_AGENT_ID en env)")
            created = mac.create_agent(config)
            new_id = created.get("id") or created.get("agent_id")
            if not new_id:
                print(f"X Anthropic no devolvió agent_id: {created}", file=sys.stderr)
                return 1
            print(f"OK Agent creado: {new_id}")
            print()
            print(f"   ACCIÓN REQUERIDA: agregá esta variable a Vercel:")
            print(f"   YOKO_AGENT_ID={new_id}")
            print(f"   (Production + Preview)")
    except mac.ManagedAgentsError as e:
        print(f"X Error en Anthropic: {e}", file=sys.stderr)
        if e.body:
            print(f"   body: {e.body[:500]}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
