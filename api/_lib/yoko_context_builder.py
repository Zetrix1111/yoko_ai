"""
api/_lib/yoko_context_builder.py

Construye el bloque `<contexto_empresa>...</contexto_empresa>` que se inyecta
como primer mensaje en cada session NUEVA del agent (Managed Agents).

El system prompt del agent (skills/_system_prompts/yoko-empresarial.md)
espera ese bloque exacto al inicio de la conversación. Si no llega, el
agent responde "No recibí el contexto de empresa" y se planta.

El bloque se arma con:
  - razón social, RUC, sistema contable → de Config_Empresa.basicos via
    config_loader.load_full_config(empresa_id).
  - usuario (nombre + cargo) → del dict que devuelve session.extract_user.
  - módulos activos → del JWT (se pasan como argumento, NO se leen de Airtable
    porque el JWT es la fuente autoritativa post-Fase-4).
  - obras activas → opcional, futuro.
"""

from . import config_loader
from .airtable_client import AirtableError


def construir_contexto_empresa(
    empresa_id: str,
    user: dict,
    modulos: list[str] | None = None,
) -> str:
    """
    Devuelve el string `<contexto_empresa>...</contexto_empresa>` listo para
    mandar como primer evento de la session.

    `user`: dict {dni, nombre, cargo, email, celular} de session.extract_user.
    `modulos`: lista de slugs de módulos habilitados (los del JWT).
    """
    try:
        full = config_loader.load_full_config(empresa_id)
    except AirtableError:
        full = {"empresa": {}}

    empresa = full.get("empresa") or {}
    razon = empresa.get("razon_social") or empresa.get("name") or empresa_id
    ruc = (empresa.get("ruc") or "").strip()
    sistema_contable = (empresa.get("sistema_contable") or "concar").upper()

    nombre = (user.get("nombre") or "").strip()
    cargo = (user.get("cargo") or "").strip()
    if nombre and cargo:
        usuario_str = f"{nombre} ({cargo})"
    elif nombre:
        usuario_str = nombre
    else:
        usuario_str = "(sin identificar)"

    modulos_list = [m for m in (modulos or []) if m]
    modulos_str = ", ".join(modulos_list) or "(ninguno)"

    lines = [
        "<contexto_empresa>",
        f"Empresa: {razon} (empresa_id: {empresa_id})",
    ]
    if ruc:
        lines.append(f"RUC: {ruc}")
    lines.append(f"Usuario: {usuario_str}")
    lines.append(f"Módulos activos: {modulos_str}")
    lines.append(f"Sistema contable: {sistema_contable}")
    lines.append("</contexto_empresa>")

    return "\n".join(lines)
