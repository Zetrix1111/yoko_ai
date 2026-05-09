"""
api/_yoko_agents/agent_definition.py

Construye el dict de configuración del agent "yoko-empresarial" listo para
mandar a `POST /v1/agents` (provisioning) o `POST /v1/agents/{id}` (update).

Fuentes:
  - System prompt: skills/_system_prompts/yoko-empresarial.md
                   (el repo es la fuente de verdad — opción A; nunca edites
                   el prompt en el Console UI: lo va a sobreescribir el
                   próximo `provision_agent`).
  - Skills:        env vars `YOKO_SKILL_<NAME>_ID` con el id devuelto por
                   `scripts/upload_skill.py`. La API de Managed Agents
                   referencia skills por id, NO por contenido inline.
  - Tools:         api/_yoko_agents/tools/*.py — solo se incluyen si
                   `YOKO_AGENT_TOOLS_ENABLED=true`. Por defecto se omiten
                   (modo conversacional puro), así Yoko responde texto sin
                   pedir tool calls hasta que cerremos esa fase.

Si falta el system prompt, lanza FileNotFoundError con mensaje claro.
"""

import os
import sys
from pathlib import Path

from .tools import ALL_TOOLS


DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_NAME = "yoko-empresarial"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / "skills"
_SYSTEM_PROMPT_FILE = _SKILLS_DIR / "_system_prompts" / "yoko-empresarial.md"

# Mapeo nombre simbólico → variable de entorno con el skill_id remoto.
# Cada vez que sumamos un skill nuevo (yoko-caja, yoko-fianzas, etc.),
# se agrega acá la entrada y se suma la env var en Vercel.
_SKILL_ENV_VARS: dict[str, str] = {
    "yoko-facturas": "YOKO_SKILL_FACTURAS_ID",
}


def _load_system_prompt() -> str:
    """
    Lee skills/_system_prompts/yoko-empresarial.md. Lanza FileNotFoundError
    con mensaje claro si todavía no existe.
    """
    if not _SYSTEM_PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"No existe {_SYSTEM_PROMPT_FILE.relative_to(_REPO_ROOT)}. "
            "Hay que crear el archivo con el system prompt antes de provisionar."
        )
    text = _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(
            f"{_SYSTEM_PROMPT_FILE.relative_to(_REPO_ROOT)} está vacío."
        )
    return text


def _load_skills() -> list[dict]:
    """
    Devuelve la lista de skills en el formato que espera la API de Managed
    Agents:  [{"type": "custom", "skill_id": "skill_...", "version": "latest"}, ...]

    Para cada entrada de _SKILL_ENV_VARS, lee la env var. Si está, agrega el
    skill al array. Si no, salta (con un warning a stderr) — el agent puede
    operar sin skills, solo conversacional.
    """
    skills: list[dict] = []
    for symbolic_name, env_name in _SKILL_ENV_VARS.items():
        sid = (os.environ.get(env_name) or "").strip()
        if not sid:
            print(
                f"[agent_definition] {env_name} no está seteada — el skill "
                f"'{symbolic_name}' no se va a adjuntar al agent. "
                "Subilo con `python scripts/upload_skill.py skills/"
                f"{symbolic_name}` y guardá el id en Vercel.",
                file=sys.stderr,
            )
            continue
        skills.append({
            "type":     "custom",
            "skill_id": sid,
            "version":  "latest",
        })
    return skills


def _tools_enabled() -> bool:
    """
    Por defecto NO incluimos tools en el agent (modo conversacional puro
    durante la fase actual). Para activarlas, setear
    YOKO_AGENT_TOOLS_ENABLED=true en Vercel.
    """
    raw = (os.environ.get("YOKO_AGENT_TOOLS_ENABLED") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def get_agent_config(
    name: str = DEFAULT_NAME,
    model: str = DEFAULT_MODEL,
    environment_id: str | None = None,
) -> dict:
    """
    Devuelve el dict listo para mandar al endpoint del agent. Carga sysprompt,
    skills (por id) y tools al momento de la llamada.
    """
    config: dict = {
        "name":   name,
        "model":  model,
        "system": _load_system_prompt(),
        "skills": _load_skills(),
        "tools":  ALL_TOOLS if _tools_enabled() else [],
    }
    env_id = environment_id or os.environ.get("YOKO_ENVIRONMENT_ID")
    if env_id:
        config["environment_id"] = env_id
    return config
