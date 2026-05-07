"""
api/_lib/contabilidad.py

Variables y generación de asientos contables por sistema (CONCAR, ...).

Cada sistema contable tiene su propio plan de cuentas y formato de líneas.
Centralizamos los defaults de cada sistema acá; el usuario puede overridear
por empresa via Config_Empresa.data.contabilidad.{cuentas|sub_diarios|...}.

Uso típico (futuro endpoint /api/facturas?action=concar):

    from _lib.contabilidad import get_contabilidad_config, factura_a_asientos

    contab = get_contabilidad_config(empresa_config)
    todas_las_lineas = []
    for factura in proceso["facturas"]:
        todas_las_lineas.extend(factura_a_asientos(factura, contab))
    # → todas_las_lineas se serializa a Excel en formato CONCAR
"""

from typing import Dict, List


# ─────────────────────────────────────────────────────────────────────────
# Defaults por sistema contable
# ─────────────────────────────────────────────────────────────────────────

# Plan de cuentas estándar peruano para CONCAR. Replica las constantes del
# escenario Make.com original. La empresa puede overridear cualquiera de
# estos valores en Config_Empresa.data.contabilidad.
CONCAR_DEFAULTS: Dict = {
    "cuentas": {
        "gasto":      "63/65",   # 63 = servicios prestados por terceros, 65 = otros gastos
        "cxp":        "421201",  # cuentas por pagar comerciales — facturas
        "igv":        "401111",  # IGV crédito fiscal
    },
    # Sub-diario CONCAR por tipo de comprobante (codigo de 2 letras del OCR).
    "sub_diarios": {
        "FT": "01",  # Factura
        "BV": "01",  # Boleta
        "NC": "08",  # Nota de crédito
        "ND": "09",  # Nota de débito
        "RH": "06",  # Recibo por honorarios
        "BA": "01",  # Boleto aéreo
        "TK": "01",  # Ticket
    },
    # Código numérico de tipo de comprobante que CONCAR espera en el archivo.
    "tipos_doc_codigo": {
        "FT": "01",
        "BV": "03",
        "NC": "07",
        "ND": "08",
        "RH": "02",
        "BA": "01",
        "TK": "12",
    },
    "tasa_igv": 18.0,
    "moneda_default": "PEN",
}


# Registro de sistemas soportados. Para agregar uno nuevo:
#   1. Definir SISCONT_DEFAULTS = {...} (mismo shape que CONCAR_DEFAULTS).
#   2. Agregarlo acá: "siscont": SISCONT_DEFAULTS.
#   3. La empresa elige el sistema en empresa.basicos.sistema_contable.
DEFAULTS_POR_SISTEMA: Dict[str, Dict] = {
    "concar": CONCAR_DEFAULTS,
}


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def get_contabilidad_config(empresa_config: Dict) -> Dict:
    """
    Resuelve la config contable consolidada para una empresa.

    1. Lee `empresa.basicos.sistema_contable` (default: "concar").
    2. Toma los defaults del sistema (DEFAULTS_POR_SISTEMA).
    3. Hace deep-merge con `empresa.contabilidad` si la empresa overridea
       alguna cuenta / sub-diario / tasa.

    Devuelve siempre un dict con las mismas keys que CONCAR_DEFAULTS para
    que el caller pueda asumir su presencia sin defensive checks.
    """
    sistema = (empresa_config.get("basicos", {}).get("sistema_contable") or "concar").lower()
    base = DEFAULTS_POR_SISTEMA.get(sistema, CONCAR_DEFAULTS)

    # Deep-copy de los defaults para no mutar el módulo global.
    config: Dict = {
        key: (dict(value) if isinstance(value, dict) else value)
        for key, value in base.items()
    }

    overrides = empresa_config.get("contabilidad") or {}
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if isinstance(config.get(key), dict) and isinstance(value, dict):
                config[key].update(value)
            else:
                config[key] = value

    return config


def factura_a_asientos(factura: Dict, contab: Dict) -> List[Dict]:
    """
    Convierte una factura del catálogo procesado en las 2-3 líneas
    contables que CONCAR espera. Replica exactamente la lógica del flujo
    Make.com:

      Línea 1: GASTO            (DEBE)  — cuenta 63/65, monto = base sin IGV
      Línea 2: IGV CRÉDITO      (DEBE)  — cuenta 401111, solo si monto_tributo > 0
      Línea 3: CXP PROVEEDOR    (HABER) — cuenta 421201, monto = total con IGV

    Cada línea es un dict con las 12 columnas del archivo CONCAR.

    Args:
        factura: dict con los campos OCR-extraídos + obra_area.
        contab:  dict resultado de `get_contabilidad_config(empresa)`.
    """
    # Tipo de comprobante (código de 2 letras del OCR; default Factura).
    tipo_doc    = (factura.get("tipo_doc_codigo") or "FT").upper()
    sub_diario  = contab["sub_diarios"].get(tipo_doc, "01")
    tipo_concar = contab["tipos_doc_codigo"].get(tipo_doc, "01")

    # Montos.
    monto_total = float(factura.get("monto_total") or 0)
    monto_igv   = float(factura.get("monto_tributo") or 0)
    base        = round(monto_total - monto_igv, 2)

    # Identificación del proveedor y centro de costo.
    ruc         = (factura.get("ruc") or "").strip()
    cc          = (factura.get("obra_area") or "").strip()

    # Fechas (vencimiento default = emision; el usuario puede ajustar luego).
    fecha_emi   = factura.get("fecha_emision") or ""
    vencimiento = factura.get("vencimiento") or fecha_emi

    # Número de comprobante: SERIE-NUMERO (ej. "F001-00012345").
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
