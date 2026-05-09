"""
api/_lib/contabilidad.py

Lógica genérica de asientos contables y resolución de la config consolidada
de cada empresa. El plan de cuentas y la generación del .xlsx son
responsabilidad de los templates de `_lib/registro_contable/templates/`
(uno por sistema contable).

Este módulo expone:
  - `get_contabilidad_config(empresa)` → resuelve `sistema_contable` +
     hace deep-merge de los DEFAULTS del template con los overrides de la
     empresa.
  - `factura_a_asientos(factura, contab)` → formato semántico (no Excel).
     Histórico, mantenido para tests y debug.
  - `upper_strings(d)` → helper de post-proceso CONCAR.

Re-exports backwards-compat al final del archivo:
  - `CONCAR_DEFAULTS`     → `registro_contable.templates.concar.DEFAULTS`
  - `factura_a_filas_excel` → `registro_contable.templates.concar.factura_a_filas`

NO usar esos re-exports en código nuevo. Llamar directo al engine:

    from _lib.registro_contable import engine
    out = engine.generate(proceso_id, empresa_id)
"""

from typing import Dict, List

from . import registro_contable
from .registro_contable import engine as _rc_engine
from .registro_contable.templates import concar as _concar_template


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def get_contabilidad_config(empresa_config: Dict) -> Dict:
    """
    Resuelve la config contable consolidada para una empresa.

    1. Lee `empresa.basicos.sistema_contable` (default: "concar").
    2. Toma los DEFAULTS del template registrado para ese sistema.
    3. Hace deep-merge (1 nivel) con `empresa.contabilidad` si la empresa
       overridea alguna cuenta / sub-diario / tasa.

    Si `sistema_contable` no está registrado, cae al template "concar"
    para no romper consumers legacy. (El engine.validate/generate sí
    levanta ValueError en ese caso, que es el comportamiento correcto
    cuando alguien quiere generar el archivo.)
    """
    sistema = (
        empresa_config.get("basicos", {}).get("sistema_contable")
        or "concar"
    ).lower()
    try:
        template = registro_contable.registry.get_template(sistema)
    except ValueError:
        template = _concar_template

    return _rc_engine.merge_config(
        getattr(template, "DEFAULTS", {}),
        empresa_config.get("contabilidad") or {},
    )


def factura_a_asientos(factura: Dict, contab: Dict) -> List[Dict]:
    """
    Convierte una factura del catálogo procesado en las 2-3 líneas
    contables que CONCAR espera. Replica exactamente la lógica del flujo
    Make.com:

      Línea 1: GASTO            (DEBE)  — cuenta 63/65, monto = base sin IGV
      Línea 2: IGV CRÉDITO      (DEBE)  — cuenta 401111, solo si monto_tributo > 0
      Línea 3: CXP PROVEEDOR    (HABER) — cuenta 421201, monto = total con IGV

    Cada línea es un dict con las 12 columnas del archivo CONCAR (formato
    semántico, NO el A-AO del Excel). Se usa para tests / debug.

    Args:
        factura: dict con los campos OCR-extraídos + obra_area.
        contab:  dict resultado de `get_contabilidad_config(empresa)`.
    """
    tipo_doc    = (factura.get("tipo_doc_codigo") or "FT").upper()
    sub_diario  = contab["sub_diarios"].get(tipo_doc, "01")
    tipo_concar = contab["tipos_doc_codigo"].get(tipo_doc, "01")

    monto_total = float(factura.get("monto_total") or 0)
    monto_igv   = float(factura.get("monto_tributo") or 0)
    base        = round(monto_total - monto_igv, 2)

    ruc         = (factura.get("ruc") or "").strip()
    cc          = (factura.get("obra_area") or "").strip()

    fecha_emi   = factura.get("fecha_emision") or ""
    vencimiento = factura.get("vencimiento") or fecha_emi

    serie       = (factura.get("serie") or "").strip()
    numero      = (factura.get("numero") or "").strip()
    if serie and numero:
        num_comp = f"{serie}-{numero}"
    else:
        num_comp = serie or numero

    concepto       = (factura.get("concepto") or "").strip()
    concepto_corto = concepto[:30]
    tasa           = contab.get("tasa_igv", 18.0)

    asientos: List[Dict] = []

    # ── LÍNEA 1: GASTO (DEBE) ──────────────────────────────────────────
    asientos.append({
        "sub_diario":      sub_diario,
        "cuenta_contable": contab["cuentas"]["gasto"],
        "ruc_dni":         "",
        "cc":              cc,
        "debe_haber":      "D",
        "monto":           _format_money(base),
        "tipo":            tipo_concar,
        "numero":          num_comp,
        "fecha_emision":   fecha_emi,
        "vencimiento":     vencimiento,
        "concepto_gasto":  concepto_corto,
        "tasa":            tasa,
    })

    # ── LÍNEA 2: IGV CRÉDITO FISCAL (DEBE) — solo si hay IGV ───────────
    if monto_igv > 0:
        asientos.append({
            "sub_diario":      sub_diario,
            "cuenta_contable": contab["cuentas"]["igv"],
            "ruc_dni":         "",
            "cc":              "",
            "debe_haber":      "D",
            "monto":           _format_money(monto_igv),
            "tipo":            tipo_concar,
            "numero":          num_comp,
            "fecha_emision":   fecha_emi,
            "vencimiento":     vencimiento,
            "concepto_gasto":  f"IGV - {concepto}"[:30],
            "tasa":            tasa,
        })

    # ── LÍNEA 3: CXP PROVEEDOR (HABER) ─────────────────────────────────
    asientos.append({
        "sub_diario":      sub_diario,
        "cuenta_contable": contab["cuentas"]["cxp"],
        "ruc_dni":         ruc,
        "cc":              "",
        "debe_haber":      "H",
        "monto":           _format_money(monto_total),
        "tipo":            tipo_concar,
        "numero":          num_comp,
        "fecha_emision":   fecha_emi,
        "vencimiento":     vencimiento,
        "concepto_gasto":  concepto_corto,
        "tasa":            tasa,
    })

    return asientos


def upper_strings(d: Dict) -> Dict:
    """
    Convierte a MAYÚSCULAS todos los valores string del dict. Replica el
    post-proceso final del flujo Make.com (CONCAR es case-sensitive en
    algunas validaciones).
    """
    return {k: (str(v).upper() if isinstance(v, str) else v) for k, v in d.items()}


# ─────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────

def _format_money(amount: float) -> str:
    """Formatea un monto como string con 2 decimales para CONCAR."""
    return f"{amount:.2f}"


# ─────────────────────────────────────────────────────────────────────────
# Re-exports backwards-compat — NO usar en código nuevo.
# ─────────────────────────────────────────────────────────────────────────
# Estos símbolos vivían acá antes del refactor a `_lib/registro_contable/`.
# Se mantienen como aliases para que cualquier consumer existente que los
# importe siga funcionando sin cambios. Código nuevo debe llamar al engine.

CONCAR_DEFAULTS: Dict = _concar_template.DEFAULTS
CONCAR_EXCEL_HEADERS: Dict = _concar_template.EXCEL_HEADERS
factura_a_filas_excel = _concar_template.factura_a_filas

# DEFAULTS_POR_SISTEMA queda como dict 1-key para no romper a quien lo
# importe. La verdad ahora vive en el registry.
DEFAULTS_POR_SISTEMA: Dict[str, Dict] = {"concar": CONCAR_DEFAULTS}
