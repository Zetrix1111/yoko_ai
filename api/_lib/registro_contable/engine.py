"""
api/_lib/registro_contable/engine.py

Motor de generación del registro contable. Es la fachada que orquesta:
  1) lee el proceso de SQLite (db_manager.get_proceso),
  2) lee la config de la empresa (config_loader.load_full_config),
  3) resuelve el template segun `sistema_contable` (registry.get_template),
  4) merge de DEFAULTS del template con overrides de la empresa,
  5) llama `template.factura_a_filas` + `template.build_xlsx`.

Dos entry points:
  - `validate(proceso_id, empresa_id)` → liviano, NO genera bytes. Usado
    por el endpoint del chat tool.
  - `generate(proceso_id, empresa_id)` → genera el .xlsx completo. Usado
    por el endpoint de descarga de la web UI.
"""

from datetime import datetime
from typing import Any, Dict, List

from . import registry


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def validate(proceso_id: str, empresa_id: str) -> Dict[str, Any]:
    """
    Validación liviana. NO genera el .xlsx, solo verifica que el proceso
    existe, tiene facturas, el sistema_contable resuelve a un template
    conocido, y cuenta cuántas filas saldrían.

    Returns:
        {
          "ok":                 True,
          "sistema":            "concar",
          "num_facturas":       5,
          "num_filas_estimado": 13,
        }

    Raises:
        ValueError con mensaje legible si: proceso no existe / sin facturas /
        sistema_contable no soportado.
    """
    facturas, contab, sistema = _prepare(proceso_id, empresa_id)
    template = registry.get_template(sistema)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    num_filas = 0
    for f in facturas:
        num_filas += len(template.factura_a_filas(f, contab, fecha_hoy))

    return {
        "ok":                 True,
        "sistema":            sistema,
        "num_facturas":       len(facturas),
        "num_filas_estimado": num_filas,
    }


def generate(proceso_id: str, empresa_id: str) -> Dict[str, Any]:
    """
    Genera el archivo Excel del registro contable completo en memoria.

    Returns:
        {
          "filename":     "REGISTRO_proc-xxx.xlsx",
          "content_type": "application/vnd.openxml...",
          "content":      <bytes>,
          "sistema":      "concar",
          "num_facturas": 5,
          "num_filas":    13,
        }

    Raises:
        ValueError con mensaje legible si: proceso no existe / sin facturas /
        sistema_contable no soportado.
    """
    facturas, contab, sistema = _prepare(proceso_id, empresa_id)
    template = registry.get_template(sistema)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    todas_las_filas: List[Dict] = []
    for f in facturas:
        todas_las_filas.extend(template.factura_a_filas(f, contab, fecha_hoy))

    content: bytes = template.build_xlsx(todas_las_filas)

    return {
        "filename":     f"REGISTRO_{proceso_id}.xlsx",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "content":      content,
        "sistema":      sistema,
        "num_facturas": len(facturas),
        "num_filas":    len(todas_las_filas),
    }


# ─────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────

def _prepare(proceso_id: str, empresa_id: str) -> tuple[List[Dict], Dict, str]:
    """
    Parte común a validate() y generate(): carga proceso + facturas + config
    contable. Devuelve (facturas, contab, sistema).

    Raises ValueError si algo falta para que la generación pueda ocurrir.
    """
    # Imports diferidos para evitar ciclos al cargar el paquete.
    from .. import config_loader, db_manager
    from ..airtable_client import AirtableError

    proceso = db_manager.get_proceso(proceso_id, empresa_id)
    if not proceso:
        raise ValueError(f"Proceso '{proceso_id}' no encontrado o expirado.")
    facturas = proceso.get("facturas") or []
    if not facturas:
        raise ValueError(f"El proceso '{proceso_id}' no tiene facturas.")

    try:
        full_config = config_loader.load_full_config(empresa_id)
    except AirtableError:
        # Si Airtable falla, seguimos con defaults; el caller decide si
        # eso es aceptable (validate sí, generate sí — el template usa
        # DEFAULTS sin overrides).
        full_config = {"empresa": {}}

    empresa_data = full_config.get("empresa") or {}
    sistema = (
        empresa_data.get("basicos", {}).get("sistema_contable")
        or empresa_data.get("sistema_contable")
        or "concar"
    ).lower()

    # Resolvemos template ya acá para que el ValueError ("sistema no
    # soportado") surja temprano en validate() también.
    template = registry.get_template(sistema)

    contab = merge_config(
        getattr(template, "DEFAULTS", {}),
        empresa_data.get("contabilidad") or {},
    )
    return facturas, contab, sistema


def merge_config(defaults: Dict, overrides: Dict) -> Dict:
    """
    Merge poco profundo (1 nivel) de overrides sobre defaults. Misma
    semántica que `contabilidad.get_contabilidad_config` original:
      - Para values dict en defaults, hace `.update()` con el override
        si éste también es dict.
      - Para values escalares, reemplaza.

    Devuelve un dict NUEVO (no muta defaults).
    """
    out: Dict = {
        key: (dict(value) if isinstance(value, dict) else value)
        for key, value in (defaults or {}).items()
    }
    if not isinstance(overrides, dict):
        return out
    for key, value in overrides.items():
        if isinstance(out.get(key), dict) and isinstance(value, dict):
            out[key].update(value)
        else:
            out[key] = value
    return out
