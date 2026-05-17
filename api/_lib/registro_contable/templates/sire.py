"""
api/_lib/registro_contable/templates/sire.py

Template SIRE - Registro de Compras Electrónico (estructura 8.4 SUNAT).
Genera TXT pipe-delimited compatible con la carga directa en el portal SIRE
de SUNAT, sin pasar por software contable intermedio.

Spec: Resolución de Superintendencia N° 040-2022/SUNAT y modificatorias.
"""

from typing import Dict, List


NAME = "sire"
DESCRIPTION = "Registro de Compras Electrónico SIRE (TXT estructura 8.4)"

OUTPUT_EXTENSION    = "txt"
OUTPUT_CONTENT_TYPE = "text/plain; charset=utf-8"


DEFAULTS: Dict = {
    # Tipo OCR (FT/BV/NC/...) → código SUNAT Tabla 10.
    "tipos_doc_sunat": {
        "FT": "01",  # Factura
        "BV": "03",  # Boleta de venta
        "NC": "07",  # Nota de crédito
        "ND": "08",  # Nota de débito
        "RH": "02",  # Recibo por honorarios
        "BA": "05",  # Boleto aéreo (boleto de transporte aéreo)
        "TK": "12",  # Ticket de máquina registradora
    },
    # Códigos ISO 4217 que SIRE acepta (los demás se mandan tal cual).
    "monedas_sunat": {
        "PEN": "PEN",
        "USD": "USD",
        "EUR": "EUR",
    },
    # Tipo de doc del proveedor (Tabla 2). 6 = RUC, que es el caso 99%.
    "tipo_doc_proveedor_default": "6",
}


# Total de campos según estructura 8.4 SUNAT.
_NUM_CAMPOS = 41


def _fmt_fecha(fecha_raw: str) -> str:
    """
    SIRE pide DD/MM/YYYY. El OCR puede devolver YYYY-MM-DD o DD/MM/YYYY u
    otro formato. Normalizamos a DD/MM/YYYY; si no se puede parsear,
    devolvemos el string tal cual y SUNAT decidirá si lo acepta.
    """
    s = (fecha_raw or "").strip()
    if not s:
        return ""
    # Caso YYYY-MM-DD → DD/MM/YYYY
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def _fmt_monto(valor) -> str:
    """
    SIRE acepta decimales con punto, 2 decimales. Vacío si None/0.
    Negativos (notas de crédito) permitidos con signo `-`.
    """
    if valor is None or valor == "":
        return ""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return ""
    if v == 0:
        return ""
    return f"{v:.2f}"


def _periodo_yyyymm00(factura: Dict) -> str:
    """
    Deriva el periodo SIRE (YYYYMM00) desde el campo `mes` (YYYY-MM) o
    `periodo` (alias) de la factura. SIRE requiere los 2 últimos dígitos
    en 00 (no se especifica día).
    """
    raw = (factura.get("mes") or factura.get("periodo") or "").strip()
    if len(raw) >= 7 and raw[4] == "-":
        return f"{raw[0:4]}{raw[5:7]}00"
    return ""


def factura_a_filas(
    factura: Dict, contab: Dict, fecha_hoy: str,
    numero_comprobante: str = "",
) -> List[Dict]:
    """
    Convierte 1 factura en 1 dict de 41 campos (keys "1".."41") según la
    estructura 8.4 SIRE para Registro de Compras Electrónico.

    A diferencia de CONCAR (que genera 2-3 filas contables por factura),
    SIRE consolida toda la factura en una sola línea: monto gravado, IGV,
    total, proveedor, etc.

    Args:
        factura: dict OCR-extraído + metadata (id, periodo, etc).
        contab:  resultado de merge_config(DEFAULTS, overrides).
        fecha_hoy: no se usa en SIRE pero forma parte del contrato.
        numero_comprobante: no aplica a SIRE (el CUO es el correlativo del
            lote). Mantenido en la firma por compat con engine.generate.
    """
    tipo_doc = (factura.get("tipo_doc_codigo") or "FT").upper()
    tipo_sunat = contab.get("tipos_doc_sunat", {}).get(tipo_doc, "")

    moneda = (factura.get("moneda") or "PEN").upper()
    monto_total  = float(factura.get("monto_total")  or 0)
    monto_tributo = float(factura.get("monto_tributo") or 0)
    base_imponible = round(monto_total - monto_tributo, 2) if monto_total else 0

    # CUO/correlativo: lo asignamos por orden de aparición en el lote.
    # `engine.generate` no nos pasa el índice, así que lo derivamos de
    # `archivo_nombre` + id; en su defecto, build_xlsx renumerará todo
    # en orden secuencial al ensamblar el TXT.
    periodo = _periodo_yyyymm00(factura)

    fila = {str(i): "" for i in range(1, _NUM_CAMPOS + 1)}

    fila["1"]  = periodo
    # CUO y correlativo se asignan en build_xlsx con el índice global del lote.
    fila["2"]  = ""
    fila["3"]  = ""
    fila["4"]  = _fmt_fecha(factura.get("fecha_emision") or "")
    fila["5"]  = _fmt_fecha(factura.get("vencimiento") or "")
    fila["6"]  = tipo_sunat
    fila["7"]  = (factura.get("serie") or "").strip()
    fila["8"]  = ""  # Año emisión DUA — no aplica a facturas comunes
    fila["9"]  = (factura.get("numero") or "").strip()
    fila["10"] = ""  # Número final — solo para rangos consolidados
    fila["11"] = contab.get("tipo_doc_proveedor_default", "6")
    fila["12"] = (factura.get("ruc") or "").strip()
    fila["13"] = (factura.get("razon_social") or factura.get("proveedor") or "").strip()
    fila["14"] = _fmt_monto(base_imponible)
    fila["15"] = _fmt_monto(monto_tributo)
    # 16-20: bases/IGV operaciones no gravadas, valor adquisiciones no gravadas.
    # El OCR actual no las extrae por separado — quedan vacías. SUNAT acepta
    # vacío salvo que la operación realmente tenga componentes no gravados.
    fila["21"] = ""  # ISC
    fila["22"] = ""  # ICBPER (impuesto bolsas plásticas)
    fila["23"] = ""  # Otros tributos
    fila["24"] = _fmt_monto(monto_total)
    fila["25"] = contab.get("monedas_sunat", {}).get(moneda, moneda)
    fila["26"] = (str(factura.get("tipo_cambio") or "").strip()) if moneda != "PEN" else ""
    # 27-31: documento referenciado (solo NC/ND). El OCR no captura esto
    # hoy → vacío. Si SUNAT rechaza NC/ND por esto, se suma como columna
    # editable en la tabla web (follow-up).
    fila["32"] = ""  # ID proyecto Ley 27037
    fila["33"] = ""  # Detracción tipo de bien
    fila["34"] = "0"  # Marca retención (0 = sin retención)
    fila["35"] = ""  # Clasificación bienes/servicios
    fila["36"] = ""  # ID proyecto contratos colaboración
    fila["37"] = "1"  # Estado del comprobante (1 = registrado vigente)
    fila["38"] = ""
    fila["39"] = ""
    fila["40"] = "0"
    fila["41"] = ""

    return [fila]


def build_xlsx(filas: List[Dict]) -> bytes:
    """
    A pesar del nombre (heredado del contrato del registry), devuelve bytes
    TXT pipe-delimited. El content_type/extension reales los expone el
    template via OUTPUT_CONTENT_TYPE / OUTPUT_EXTENSION.

    Formato:
      - 41 campos por línea separados por `|`.
      - Sin headers (SIRE no los acepta).
      - 1 línea por factura, terminada en CRLF (estándar SUNAT).
      - UTF-8 sin BOM.
      - El CUO y el correlativo (campos 2 y 3) se asignan acá con el índice
        global del lote, no por factura — así el orden de aparición en el
        TXT es el orden de presentación a SUNAT.
    """
    lines: List[str] = []
    for idx, fila in enumerate(filas, start=1):
        # CUO = "M" + correlativo zfill 4 (M = comprobante de operación).
        # Es opaco para SUNAT salvo unicidad por archivo.
        fila["2"] = f"M{idx:04d}"
        fila["3"] = str(idx)

        campos = [str(fila.get(str(i), "")) for i in range(1, _NUM_CAMPOS + 1)]
        lines.append("|".join(campos))

    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def build_filename(proceso_id: str, facturas: List[Dict], contab: Dict) -> str:
    """
    Nombre oficial SUNAT: LE<RUC><YYYYMM00>080400001111

    Composición (33 chars + .txt):
      - LE         (2)  : prefijo libro electrónico
      - RUC        (11) : del contribuyente (contab["_empresa"]["ruc"])
      - YYYYMM00   (8)  : periodo del proceso (último DD siempre 00)
      - 080400     (6)  : código del Registro de Compras Electrónico 8.4
      - 001111     (6)  : oportunidad de presentación (estándar mensual)

    Si falta el RUC o el periodo (datos incompletos), fallback a
    `REGISTRO_<proceso_id>.txt` — el archivo igual se descarga y el usuario
    puede renombrarlo a mano antes de subirlo a SUNAT.
    """
    ruc = (contab.get("_empresa") or {}).get("ruc") or ""
    ruc = "".join(ch for ch in ruc if ch.isdigit())  # solo dígitos

    periodo = _periodo_yyyymm00(facturas[0]) if facturas else ""

    if len(ruc) == 11 and len(periodo) == 8:
        return f"LE{ruc}{periodo}080400001111.txt"

    return f"REGISTRO_{proceso_id}.txt"
