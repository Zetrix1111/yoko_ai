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
  - centros de costo activos → opcional, futuro.
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

    # Si el módulo gestion-caja-chica está activo, inyectar el bloque
    # <contexto_modulo> con la config del proceso. El SKILL solicitud-caja
    # lo necesita para decidir si pedir aprobador o saltar directo a pago.
    if any(m in modulos_list for m in ("gestion-caja-chica", "gestion-caja")):
        caja_block = _build_caja_chica_context(full)
        if caja_block:
            lines.append("")
            lines.append(caja_block)

    return "\n".join(lines)


def _build_caja_chica_context(full_config: dict) -> str:
    """
    Construye el bloque `<contexto_modulo nombre="gestion-caja">` con la
    config de caja_chica que el SKILL solicitud-caja espera leer para
    decidir el flujo (pedir aprobador vs. saltar a pago directo).

    Devuelve string vacío si no hay config — en ese caso el agent va a
    asumir defaults conservadores (pedir aprobador).
    """
    proceso = (full_config or {}).get("proceso") or {}
    cc = proceso.get("caja_chica") or {}
    centros = (full_config or {}).get("centros_costo") or {}

    if not isinstance(cc, dict):
        return ""

    requiere = bool(cc.get("requiere_aprobacion", True))
    num_aprob = int(cc.get("num_aprobadores", 2) or 2)
    monto_max_act = bool(cc.get("monto_maximo_activo", False))
    monto_max = cc.get("monto_maximo", 0)
    aprob_rend = bool(cc.get("aprobacion_rendicion", False))
    seg_ia = bool(cc.get("seguimiento_ia", False))
    centro_costo_activo = bool(centros.get("activo", True)) if isinstance(centros, dict) else True

    out = [
        '<contexto_modulo nombre="gestion-caja">',
        f"requiere_aprobacion: {str(requiere).lower()}",
        f"num_aprobadores: {num_aprob}",
        f"monto_maximo_activo: {str(monto_max_act).lower()}",
        f"monto_maximo: {monto_max}",
        f"aprobacion_rendicion: {str(aprob_rend).lower()}",
        f"seguimiento_ia: {str(seg_ia).lower()}",
        f"centro_costo: {str(centro_costo_activo).lower()}",
        "</contexto_modulo>",
    ]
    return "\n".join(out)
