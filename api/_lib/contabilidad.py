"""
api/_lib/contabilidad.py

Variables y generación de asientos contables por sistema (CONCAR, ...).

Cada sistema contable tiene su propio plan de cuentas y formato de líneas.
Centralizamos los defaults de cada sistema acá; el usuario puede overridear
por empresa via Config_Empresa.data.contabilidad.{cuentas|sub_diarios|...}.

Uso típico (endpoint /api/facturas?action=concar):

    from _lib.contabilidad import (
        get_contabilidad_config,
        factura_a_filas_excel,
        CONCAR_EXCEL_HEADERS,
    )

    contab = get_contabilidad_config(empresa_config)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    todas_las_filas = []
    for factura in proceso["facturas"]:
        todas_las_filas.extend(factura_a_filas_excel(factura, contab, fecha_hoy))
    # → todas_las_filas se escribe al .xlsx con openpyxl, headers en filas 1-3.

`factura_a_asientos` (formato semántico) se mantiene para tests/debug;
`factura_a_filas_excel` (formato A-AO del Excel CONCAR) es lo que usa
el endpoint real.
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
    # Confirmado con el usuario: RH=15, BV=13, todos los demás = 11.
    "sub_diarios": {
        "FT": "11",  # Factura
        "BV": "13",  # Boleta de venta
        "NC": "11",  # Nota de crédito
        "ND": "11",  # Nota de débito
        "RH": "15",  # Recibo por honorarios
        "BA": "11",  # Boleto aéreo
        "TK": "11",  # Ticket
    },
    # Tipo de documento (col R del Excel CONCAR). Usamos el código del OCR
    # directamente — CONCAR los acepta como FT, BV, NC, etc.
    "tipos_doc_codigo": {
        "FT": "FT",
        "BV": "BV",
        "NC": "NC",
        "ND": "ND",
        "RH": "RH",
        "BA": "BA",
        "TK": "TK",
    },
    # Mapeo de moneda OCR → código CONCAR (col E del Excel).
    "monedas_codigo": {
        "PEN": "MN",  # Moneda Nacional (soles)
        "USD": "ME",  # Moneda Extranjera (dólares)
        "EUR": "ER",  # Euros
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


# ─────────────────────────────────────────────────────────────────────────
# Excel CONCAR — headers y generador de filas
# ─────────────────────────────────────────────────────────────────────────

# Headers que se escriben en las filas 1-3 del Excel CONCAR. Replican la
# plantilla del usuario: fila 1 = nombres de columna (cabecera azul +
# blanco bold), fila 2 = descripciones de validación, fila 3 = tamaño/
# formato. Las columnas no especificadas (A, V, X-AN) quedan vacías.
CONCAR_EXCEL_HEADERS = {
    # Fila 1: nombres de columna
    "row1": {
        "A":  "WE",
        "B":  "Sub Diario",
        "C":  "Número de Comprobante",
        "D":  "Fecha de Comprobante",
        "E":  "Código de Moneda",
        "F":  "Glosa Principal",
        "G":  "Tipo de Cambio",
        "H":  "Tipo de Conversión",
        "I":  "Flag de Conversión de Moneda",
        "J":  "Fecha Tipo de Cambio",
        "K":  "Cuenta Contable",
        "L":  "Código de Anexo",
        "M":  "Código de Centro de Costo",
        "N":  "Debe / Haber",
        "O":  "Importe Original",
        "P":  "Importe USD",
        "Q":  "Importe PEN",
        "R":  "Tipo de Documento",
        "S":  "Serie-Número",
        "T":  "Fecha de Emisión",
        "U":  "Fecha de Vencimiento",
        "W":  "Glosa Corta",
        "AO": "Tasa Tributo",
    },
    # Fila 2: descripciones de validación / referencia (replicadas del
    # screenshot original del usuario para A-O; P-AO sin descripción).
    "row2": {
        "B":  "Ver T.G. 02",
        "C":  "Los dos primeros dígitos son el mes y los otros 4 siguientes un correlativo",
        "E":  "Ver T.G. 03",
        "G":  "Llenar solo si Tipo de Conversión es 'C'. Debe estar entre >=0 y <=9999.999999",
        "H":  "Solo: 'C'= Especial, 'M'=Compra, 'V'=Venta, 'F' De acuerdo a fecha",
        "I":  "Solo: 'S' = Si se convierte, 'N'= No se convierte",
        "J":  "Si Tipo de Conversión 'F'",
        "K":  "Debe existir en el Plan de Cuentas",
        "L":  "Si Cuenta Contable tiene seleccionado Tipo de Anexo, debe existir en la tabla de Anexos",
        "M":  "Si Cuenta Contable tiene habilitado C. Costo, Ver T.G. 05",
        "N":  "'D' ó 'H'",
        "O":  "Importe original de la cuenta contable. Obligatorio, debe estar entre >=0 y <=99999999999.99",
    },
    # Fila 3: Tamaño/Formato de cada columna.
    "row3": {
        "A":  "Tamaño/Formato",
        "B":  "4 Caracteres",
        "C":  "6 Caracteres",
        "D":  "dd/mm/aaaa",
        "E":  "2 Caracteres",
        "F":  "40 Caracteres",
        "G":  "Numérico 11,6",
        "H":  "1 Caracteres",
        "I":  "1 Caracteres",
        "J":  "dd/mm/aaaa",
        "K":  "12 Caracteres",
        "L":  "18 Caracteres",
        "M":  "6 Caracteres",
        "N":  "1 Carácter",
        "O":  "Numérico 14,2",
        "P":  "Numérico 14,2",
        "Q":  "Numérico 14,2",
        "R":  "2 Caracteres",
        "S":  "—",
        "T":  "dd/mm/aaaa",
        "U":  "dd/mm/aaaa",
        "W":  "30 Caracteres",
        "AO": "Numérico",
    },
}


# Constantes para el formato del Excel.
_CONCAR_DEFAULT_TIPO_CONVERSION = "V"
_CONCAR_DEFAULT_FLAG_CONVERSION = "S"


def factura_a_filas_excel(factura: Dict, contab: Dict, fecha_hoy: str) -> List[Dict]:
    """
    Convierte una factura en 2-3 dicts cuyas KEYS son letras de columna
    (A, B, ..., AO) listas para escribir directo al Excel CONCAR.

    Cada dict representa una línea contable:
      - Línea 1: GASTO (DEBE) — cuenta de gasto, monto = base sin IGV, cc = obra_area.
      - Línea 2: IGV CRÉDITO (DEBE) — cuenta IGV, monto = monto_tributo. Solo si > 0.
      - Línea 3: CXP PROVEEDOR (HABER) — cuenta cxp, monto = total con IGV, anexo = ruc.

    Args:
        factura:    dict con campos OCR-extraídos + obra_area.
        contab:     dict de get_contabilidad_config(empresa).
        fecha_hoy:  string DD/MM/YYYY para columna J ("Fecha Tipo de Cambio").
    """
    # Tipo de comprobante (código de 2 letras; default Factura).
    tipo_doc    = (factura.get("tipo_doc_codigo") or "FT").upper()
    sub_diario  = contab["sub_diarios"].get(tipo_doc, "11")
    tipo_concar = contab["tipos_doc_codigo"].get(tipo_doc, "FT")

    # Moneda → código CONCAR.
    moneda      = (factura.get("moneda") or "PEN").upper()
    moneda_code = contab["monedas_codigo"].get(moneda, "MN")

    # Montos.
    monto_total = float(factura.get("monto_total") or 0)
    monto_igv   = float(factura.get("monto_tributo") or 0)
    base        = round(monto_total - monto_igv, 2)

    # Identificación.
    ruc = (factura.get("ruc") or "").strip()
    cc  = (factura.get("obra_area") or "").strip()

    # Fechas.
    fecha_emi   = factura.get("fecha_emision") or ""
    vencimiento = factura.get("vencimiento") or fecha_emi

    # Serie-Número del comprobante.
    serie  = (factura.get("serie") or "").strip()
    numero = (factura.get("numero") or "").strip()
    if serie and numero:
        serie_numero = f"{serie}-{numero}"
    else:
        serie_numero = serie or numero

    # Conceptos / glosas (40 chars en col F, 30 en col W).
    concepto       = (factura.get("concepto") or "").strip()
    glosa_principal = concepto[:40]
    glosa_corta     = concepto[:30]

    tasa = contab.get("tasa_igv", 18.0)

    # Helper para construir filas con los defaults compartidos.
    def _fila_base(monto: float) -> Dict:
        is_usd = (moneda == "USD")
        is_pen = (moneda == "PEN")
        return {
            "A":  "",                                 # WE — vacío
            "B":  sub_diario,
            "C":  "",                                 # Número de Comprobante — lo asigna contador
            "D":  fecha_emi,
            "E":  moneda_code,
            "F":  glosa_principal,
            "G":  "",                                 # Tipo de Cambio — vacío
            "H":  _CONCAR_DEFAULT_TIPO_CONVERSION,    # "V"
            "I":  _CONCAR_DEFAULT_FLAG_CONVERSION,    # "S"
            "J":  fecha_hoy,
            "K":  "",                                 # cuenta_contable — la pone el caller por línea
            "L":  "",                                 # ruc — solo en HABER
            "M":  "",                                 # cc — solo en gasto
            "N":  "",                                 # debe/haber — la pone el caller
            "O":  monto,                              # importe original (numérico)
            "P":  monto if is_usd else "",            # USD
            "Q":  monto if is_pen else "",            # PEN
            "R":  tipo_concar,
            "S":  serie_numero,
            "T":  fecha_emi,
            "U":  vencimiento,
            "W":  glosa_corta,
            "AO": tasa,
        }

    filas: List[Dict] = []

    # ── LÍNEA 1: GASTO (DEBE) ─────────────────────────────────────
    fila_gasto = _fila_base(base)
    fila_gasto["K"] = contab["cuentas"]["gasto"]
    fila_gasto["M"] = cc
    fila_gasto["N"] = "D"
    filas.append(fila_gasto)

    # ── LÍNEA 2: IGV CRÉDITO FISCAL (DEBE) — solo si hay IGV ──────
    if monto_igv > 0:
        fila_igv = _fila_base(monto_igv)
        fila_igv["K"] = contab["cuentas"]["igv"]
        fila_igv["F"] = f"IGV - {concepto}"[:40]
        fila_igv["W"] = f"IGV - {concepto}"[:30]
        fila_igv["N"] = "D"
        filas.append(fila_igv)

    # ── LÍNEA 3: CXP PROVEEDOR (HABER) ────────────────────────────
    fila_cxp = _fila_base(monto_total)
    fila_cxp["K"] = contab["cuentas"]["cxp"]
    fila_cxp["L"] = ruc
    fila_cxp["N"] = "H"
    filas.append(fila_cxp)

    return filas
