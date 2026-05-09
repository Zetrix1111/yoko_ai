"""
api/_yoko_agents/agent_definition.py

Construye el dict de configuración del agent "yoko-empresarial" leyendo:
  - System prompt:  skills/_system_prompts/yoko-empresarial.md
  - Skills:         skills/yoko-*/SKILL.md       (uno por subcarpeta)
  - Tools:          api/_yoko_agents/tools/*.py  (constantes TOOL_DEFINITION)

`get_agent_config()` devuelve el dict listo para mandar al endpoint
POST /v1/agents (provision_agent.py lo usa).

Si falta el system prompt o la carpeta skills/, lanza FileNotFoundError con
mensaje claro indicando que la Etapa D no se completó.
"""

import os
from pathlib import Path

from .tools import ALL_TOOLS


# Default model: Claude Sonnet 4.6 (decisión cerrada en PLAN_YOKO_MANAGED_AGENTS).
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_NAME = "yoko-empresarial"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / "skills"
_SYSTEM_PROMPT_FILE = _SKILLS_DIR / "_system_prompts" / "yoko-empresarial.md"


def _load_system_prompt() -> str:
    """
    Lee skills/_system_prompts/yoko-empresarial.md. Lanza FileNotFoundError
    con mensaje claro si todavía no existe (Etapa D pendiente).
    """
    if not _SYSTEM_PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"No existe {_SYSTEM_PROMPT_FILE.relative_to(_REPO_ROOT)}. "
            "Etapa D no completada: hay que crear el archivo con el system "
            "prompt de Claude Console antes de provisionar el agent."
        )
    text = _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(
            f"{_SYSTEM_PROMPT_FILE.relative_to(_REPO_ROOT)} está vacío. "
            "Pegá el system prompt antes de provisionar."
        )
    return text


def _load_skills() -> list[dict]:
    """
    Recorre skills/yoko-*/SKILL.md y devuelve una lista de
    {"name": ..., "content": ...} para incluir en el agent.

    Si la carpeta skills/ no existe todavía, devuelve lista vacía (no falla):
    permite provisionar el agent antes de poblar skills, pero aparecerá sin
    capacidades especializadas hasta que la Etapa D corra.
    """
    if not _SKILLS_DIR.exists():
        return []

    skills: list[dict] = []
    for entry in sorted(_SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue  # convención: _system_prompts, _template, etc.
        skill_file = entry / "SKILL.md"
        if not skill_file.exists():
            continue
        skills.append({
            "name": entry.name,
            "content": skill_file.read_text(encoding="utf-8"),
        })
    return skills


def get_agent_config(
    name: str = DEFAULT_NAME,
    model: str = DEFAULT_MODEL,
    environment_id: str | None = None,
) -> dict:
    """
    Devuelve el dict de configuración listo para POST /v1/agents (o PATCH al
    update). Carga sysprompt + skills + tools al momento de la llamada.
    """
    config: dict = {
        "name": name,
        "model": model,
        "system": _load_system_prompt(),
        "tools": ALL_TOOLS,
        "skills": _load_skills(),
    }
    env_id = environment_id or os.environ.get("YOKO_ENVIRONMENT_ID")
    if env_id:
        config["environment_id"] = env_id
    return config
