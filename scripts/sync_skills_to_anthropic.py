"""
scripts/sync_skills_to_anthropic.py

Sincroniza el system prompt y los skills locales (carpeta `skills/`) con el
agent de Anthropic identificado por `YOKO_AGENT_ID`.

Uso:
    python scripts/sync_skills_to_anthropic.py [--dry-run]

Comportamiento:
  1. Construye la config del agent leyendo desde `skills/` y los tools
     declarados en `api/_yoko_agents/tools/`.
  2. Lee el agent remoto (GET /v1/agents/{id}).
  3. Compara system prompt + nombres de skills + nombres de tools.
  4. Si hay diferencias, llama `update_agent` con la config nueva.
  5. Si no hay diferencias, es no-op.

Imprime un diff legible (qué skills se agregaron / quitaron, si el system
prompt cambió de tamaño, etc.). NO hace deploy parcial — siempre manda la
config completa.

Pre-requisitos:
  - ANTHROPIC_API_KEY en env
  - YOKO_AGENT_ID en env (si falta, este script falla; usá provision_agent
    para crear el agent inicial)
"""

import argparse
import os
import sys
from pathlib import Path


def _setup_path() -> None:
    here = Path(__file__).resolve().parent
    api_dir = here.parent / "api"
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))


def _tool_names(items: list[dict]) -> set[str]:
    """Para tools custom el campo distintivo es `name`; para built-in es `type`."""
    out: set[str] = set()
    for i in items:
        n = i.get("name") or i.get("type") or ""
        if n:
            out.add(n)
    return out


def _tool_schemas_by_name(items: list[dict]) -> dict[str, dict]:
    """Indexa custom tools por nombre, devolviendo description + input_schema."""
    out: dict[str, dict] = {}
    for i in items:
        name = i.get("name")
        if not name:
            continue
        out[name] = {
            "description": i.get("description") or "",
            "input_schema": i.get("input_schema") or {},
        }
    return out


def _skill_ids(items: list[dict]) -> set[str]:
    """Skills se referencian por skill_id (custom) o skill_id (anthropic)."""
    return {i.get("skill_id", "") for i in items if i.get("skill_id")}


def _diff_summary(local: dict, remote: dict | None) -> tuple[bool, list[str]]:
    """
    Compara local vs remote y devuelve (hay_cambios, lineas_legibles).
    Si remote es None (agent no existe), todo es "nuevo".
    """
    lines: list[str] = []
    if remote is None:
        lines.append("  Agent no existe remotamente — todo es nuevo.")
        return True, lines

    has_changes = False

    # System prompt
    local_sys = local.get("system") or ""
    remote_sys = remote.get("system") or ""
    if local_sys != remote_sys:
        has_changes = True
        lines.append(
            f"  ~ system: {len(remote_sys)} chars -> {len(local_sys)} chars"
        )

    # Tools — diff por nombre + diff por schema (description/input_schema).
    # Sin el diff de schema, cambiar el `required` o el enum de un campo
    # quedaba como "sin cambios" porque el nombre del tool no cambia.
    local_tools_list = local.get("tools") or []
    remote_tools_list = remote.get("tools") or []
    local_tools = _tool_names(local_tools_list)
    remote_tools = _tool_names(remote_tools_list)
    added = sorted(local_tools - remote_tools)
    removed = sorted(remote_tools - local_tools)
    if added:
        has_changes = True
        lines.append(f"  + tools: {', '.join(added)}")
    if removed:
        has_changes = True
        lines.append(f"  - tools: {', '.join(removed)}")

    local_schemas = _tool_schemas_by_name(local_tools_list)
    remote_schemas = _tool_schemas_by_name(remote_tools_list)
    for name in sorted(local_schemas.keys() & remote_schemas.keys()):
        if local_schemas[name] != remote_schemas[name]:
            has_changes = True
            lines.append(f"  ~ tool schema cambió: {name}")

    # Skills (por skill_id remoto)
    local_skills = _skill_ids(local.get("skills") or [])
    remote_skills = _skill_ids(remote.get("skills") or [])
    added_s = sorted(local_skills - remote_skills)
    removed_s = sorted(remote_skills - local_skills)
    if added_s:
        has_changes = True
        lines.append(f"  + skills: {', '.join(added_s)}")
    if removed_s:
        has_changes = True
        lines.append(f"  - skills: {', '.join(removed_s)}")

    if not has_changes:
        lines.append("  (sin cambios)")
    return has_changes, lines


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime el diff pero no llama update_agent.",
    )
    args = parser.parse_args()

    _setup_path()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("X Falta ANTHROPIC_API_KEY en el entorno.", file=sys.stderr)
        return 1
    agent_id = os.environ.get("YOKO_AGENT_ID")
    if not agent_id:
        print(
            "X Falta YOKO_AGENT_ID en el entorno. Para crear el agent por "
            "primera vez, corré:\n"
            "    python -m api._yoko_agents.provision_agent",
            file=sys.stderr,
        )
        return 1

    from _lib import managed_agents_client as mac
    from _yoko_agents.agent_definition import get_agent_config

    try:
        local_config = get_agent_config()
    except (FileNotFoundError, ValueError) as e:
        print(f"X No se pudo construir la config local: {e}", file=sys.stderr)
        return 1

    print(f"→ Comparando con agent {agent_id} en Anthropic...")
    try:
        remote = mac.get_agent(agent_id)
    except mac.ManagedAgentsError as e:
        print(f"X Error al leer agent remoto: {e}", file=sys.stderr)
        return 1

    has_changes, lines = _diff_summary(local_config, remote)
    print("\nDiff:")
    for ln in lines:
        print(ln)
    print()

    if not has_changes:
        print("OK Nada que sincronizar.")
        return 0

    if args.dry_run:
        print("DRY-RUN: no se aplicaron cambios.")
        return 0

    # La API de Managed Agents exige `version` en el body del POST como control
    # de optimistic locking — debe coincidir con la versión actual remota.
    # Después del update incrementa automáticamente.
    local_config["version"] = remote.get("version")

    try:
        updated = mac.update_agent(agent_id, local_config)
        print(f"OK Agent {agent_id} actualizado.")
        if "updated_at" in updated:
            print(f"   updated_at: {updated['updated_at']}")
    except mac.ManagedAgentsError as e:
        print(f"X Error al actualizar el agent: {e}", file=sys.stderr)
        if e.body:
            print(f"   body: {e.body[:500]}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
