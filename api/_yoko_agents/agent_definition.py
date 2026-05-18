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
    "facturas-inteligentes": "YOKO_SKILL_FACTURAS_ID",
    "solicitud-caja": "YOKO_SKILL_SOLICITUD_CAJA_ID",
    "rendicion-caja": "YOKO_SKILL_RENDICION_CAJA_ID",
}


_MANAGED_SOLICITUD_CAJA_GUIDANCE = """

# Runtime Managed Agents: solicitud-caja

Cuando el skill `solicitud-caja` esté activo, usa el contexto detallado de
`gestion-caja` para decidir si necesitas consultar aprobadores.

Reglas para aprobadores:
- Si `requiere_aprobacion = false`, no llames `consultar_aprobador`.
- Si `requiere_aprobacion = true` y `num_aprobadores = 1`, llama una sola vez:
  `consultar_aprobador({"rol": "APROBADOR_2"})`.
- Si `requiere_aprobacion = true` y `num_aprobadores >= 2`, llama una sola vez:
  `consultar_aprobador({"rol": "todos"})`.
- `APROBADOR_1` corresponde al residente opcional y se usa como
  `residente_id` solo si el usuario elige uno.
- `APROBADOR_2` corresponde al aprobador obligatorio y se usa como
  `aprobador_id`.
- Muestra al usuario nombres, no record ids. Usa internamente el `id` devuelto
  por la tool al llamar `yoko_crear_solicitud`.

Reglas para centros de costo:
- No esperes recibir centros de costo en el contexto.
- Si necesitas completar o validar `centro_costo`, llama
  `consultar_centros_costo`.
- Muestra al usuario nombres de centros de costo y usa internamente el valor
  elegido al llamar `yoko_crear_solicitud`.
""".strip()


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
    return f"{text}\n\n{_MANAGED_SOLICITUD_CAJA_GUIDANCE}"


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


def _custom_tools_enabled() -> bool:
    """
    Controla si los CUSTOM tools (`yoko_procesar_archivos`,
    `yoko_generar_registro_contable`, `yoko_recuperar_proceso`) se adjuntan al agent. Default true
    porque ya pasamos la fase conversacional pura.
    """
    raw = (os.environ.get("YOKO_AGENT_TOOLS_ENABLED") or "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


# Configuración del toolset built-in `agent_toolset_20260401` requerido por
# Managed Agents para que los skills funcionen — los skills son archivos en
# el filesystem de la VM y el agent los lee con `read`. Sin este toolset, la
# API rechaza la creación de sesiones que tengan skills adjuntos:
#     "Missing required tool: skills require the read tool to be usable"
#
# Estrategia: habilitamos el toolset completo (default), pero deshabilitamos
# explícitamente las tools que NO queremos que el agent use en ningún caso:
#   - `bash` y `web_fetch` y `web_search`: para evitar que el agent intente
#     "buscar" archivos del usuario en el filesystem o salir a la web. Los
#     archivos llegan via custom tool injection del orquestador.
#   - `write` y `edit`: el agent no debe modificar archivos.
# Quedan habilitados `read`, `glob`, `grep` — necesarios para que el skill
# facturas-inteligentes se cargue y se navegue.
_BUILTIN_TOOLSET: dict = {
    "type": "agent_toolset_20260401",
    "configs": [
        {"name": "bash",       "enabled": False},
        {"name": "web_fetch",  "enabled": False},
        {"name": "web_search", "enabled": False},
        {"name": "write",      "enabled": False},
        {"name": "edit",       "enabled": False},
    ],
}


def get_agent_config(
    name: str = DEFAULT_NAME,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Devuelve el dict listo para mandar al endpoint del agent. Carga sysprompt,
    skills (por id) y tools al momento de la llamada.

    NOTA: `environment_id` NO va en la config del agent — es un campo de
    session (/v1/sessions). El agent es independiente del environment;
    cualquier session puede combinar este agent con cualquier environment.
    """
    tools: list[dict] = [_BUILTIN_TOOLSET]
    if _custom_tools_enabled():
        tools.extend(ALL_TOOLS)

    return {
        "name":   name,
        "model":  model,
        "system": _load_system_prompt(),
        "skills": _load_skills(),
        "tools":  tools,
    }
