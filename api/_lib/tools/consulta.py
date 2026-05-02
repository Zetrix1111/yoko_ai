"""
Tools de consulta (read-only) — categoría 'consulta'.

Importar este módulo registra todas las tools en `tool_registry.TOOLS`
gracias al side-effect del decorador `@register`.

Tablas de Airtable que asume este módulo (deben existir en la base
del tenant; los nombres son convenciones — si tu schema difiere,
edita las constantes _TABLA_* abajo):

  • Solicitudes  → empresa_id, dni, estado, fecha, monto, origen, tipo, motivo
  • Rendiciones  → empresa_id, dni, estado, fecha, monto, ...
  • Pagos        → empresa_id, dni, fecha, monto, ...
"""

from .. import airtable_client
from ..tool_registry import register


# ─────────────────────────────────────────────────────────────────────────
# Constantes (edita si tu Airtable usa otros nombres de tabla)
# ─────────────────────────────────────────────────────────────────────────
_TABLA_SOLICITUDES = "solicitudes_caja"
_TABLA_RENDICIONES = "Rendiciones"   # TODO: confirmar el nombre real cuando se cree
_TABLA_PAGOS       = "Pagos"         # TODO: confirmar el nombre real cuando se cree

# Campos lookup en solicitudes_caja: SOLICITANTE es Linked Record a Empleados,
# así que usamos los lookup fields para filtrar por DNI/Email/Nombre.
_CAMPO_DNI_SOLICITUDES   = "DNI (from SOLICITANTE)"
_CAMPO_EMAIL_SOLICITUDES = "EMAIL (from SOLICITANTE)"
_CAMPO_ESTADO            = "ESTADO"


# ─────────────────────────────────────────────────────────────────────────
# Helpers compartidos
# ─────────────────────────────────────────────────────────────────────────

def _formula_y(*partes: str) -> str:
    """Une condiciones con AND(...)."""
    partes = [p for p in partes if p]
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return "AND(" + ", ".join(partes) + ")"


def _filtro_periodo(periodo: str | None, campo_fecha: str = "fecha") -> str | None:
    """
    Devuelve una sub-fórmula Airtable que filtra por mes (YYYY-MM).
    Soporta tanto campos Date (DATETIME_FORMAT) como text (LEFT).
    """
    if not periodo:
        return None
    return (
        f"OR("
        f"DATETIME_FORMAT({{{campo_fecha}}}, 'YYYY-MM')='{periodo}',"
        f"LEFT({{{campo_fecha}}},7)='{periodo}'"
        f")"
    )


def _listar_por_dni(
    tabla: str,
    dni: str,
    estado: str | None = None,
    periodo: str | None = None,
    campo_dni: str = "DNI (from SOLICITANTE)",
    campo_estado: str = "ESTADO",
    campo_fecha: str = "fecha",
) -> list[dict]:
    """
    Helper para listar registros por DNI desde una tabla con SOLICITANTE
    como Linked Record a Empleados. Filtra por el lookup DNI.

    No filtra por empresa_id porque cada tenant usa su propia Airtable base
    (separación física, no lógica). Si ese supuesto cambia, agregar filtro
    `{empresa_id}` aquí.

    Estado: usa coincidencia parcial uppercase para acomodar valores como
    `PENDIENTE_APROBACION_JEFATURA_SEDE` cuando el LLM pasa `pendiente`.
    """
    partes = [f"{{{campo_dni}}}='{dni}'"]
    if estado:
        partes.append(
            f"FIND('{estado.upper()}', UPPER({{{campo_estado}}} & ''))>0"
        )
    p = _filtro_periodo(periodo, campo_fecha=campo_fecha)
    if p:
        partes.append(p)

    formula = _formula_y(*partes)
    records = airtable_client.list_records(tabla, filter_formula=formula)
    return [r["fields"] for r in records]


# ─────────────────────────────────────────────────────────────────────────
# 1. consultar_solicitudes_por_dni
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="consultar_solicitudes_por_dni",
    description=(
        "Consulta las solicitudes de caja chica del usuario. Útil para "
        "preguntas como '¿cómo va mi solicitud?' o '¿qué tengo pendiente?'. "
        "El parámetro DNI debe ser el del usuario autenticado. "
        "El filtro de estado hace match parcial (uppercase): por ejemplo "
        "'pendiente_aprobacion' matchea PENDIENTE_APROBACION_RESIDENTE y "
        "PENDIENTE_APROBACION_JEFATURA_SEDE."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dni":     {"type": "string", "description": "DNI del solicitante (8 dígitos)."},
            "estado":  {
                "type": "string",
                "enum": [
                    "pendiente_aprobacion",
                    "por_pagar",
                    "por_contabilizar",
                    "por_rendir",
                    "finalizado",
                    "rechazado",
                ],
                "description": (
                    "Filtra por etapa del ciclo. "
                    "pendiente_aprobacion=en revisión; "
                    "por_pagar=esperando desembolso del tesorero; "
                    "por_contabilizar=esperando registro contable; "
                    "por_rendir=usuario debe rendir gastos; "
                    "finalizado=ciclo cerrado; "
                    "rechazado=denegado en cualquier etapa. "
                    "Omitir para traer todos."
                ),
            },
            "periodo": {"type": "string", "description": "Mes en formato YYYY-MM."},
        },
        "required": ["dni"],
    },
    category="consulta",
)
def consultar_solicitudes_por_dni(args: dict, context: dict) -> dict:
    items = _listar_por_dni(
        _TABLA_SOLICITUDES,
        dni=args["dni"],
        estado=args.get("estado"),
        periodo=args.get("periodo"),
        campo_dni=_CAMPO_DNI_SOLICITUDES,
        campo_estado=_CAMPO_ESTADO,
    )
    return {"solicitudes": items, "total": len(items)}


# ─────────────────────────────────────────────────────────────────────────
# 2. consultar_rendiciones_por_dni
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="consultar_rendiciones_por_dni",
    description=(
        "Consulta las rendiciones del usuario. Útil para '¿qué tengo "
        "pendiente de rendir?' o '¿cuáles ya rendí este mes?'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dni":     {"type": "string", "description": "DNI del usuario."},
            "estado":  {
                "type": "string",
                "enum": ["pendiente", "parcial", "rendida"],
                "description": "Filtra por estado de rendición.",
            },
            "periodo": {"type": "string", "description": "Mes en formato YYYY-MM."},
        },
        "required": ["dni"],
    },
    category="consulta",
)
def consultar_rendiciones_por_dni(args: dict, context: dict) -> dict:
    # NOTA: la tabla `Rendiciones` aún no se ha definido. El nombre y
    # los campos lookup deberán ajustarse cuando se cree (siguiendo el
    # patrón de `solicitudes_caja`).
    items = _listar_por_dni(
        _TABLA_RENDICIONES,
        dni=args["dni"],
        estado=args.get("estado"),
        periodo=args.get("periodo"),
    )
    return {"rendiciones": items, "total": len(items)}


# ─────────────────────────────────────────────────────────────────────────
# 3. consultar_pagos_por_dni
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="consultar_pagos_por_dni",
    description=(
        "Consulta los pagos efectuados al usuario. Útil para '¿ya me "
        "pagaron mi solicitud?' o '¿qué pagos recibí este mes?'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dni":     {"type": "string", "description": "DNI del usuario."},
            "periodo": {"type": "string", "description": "Mes en formato YYYY-MM."},
        },
        "required": ["dni"],
    },
    category="consulta",
)
def consultar_pagos_por_dni(args: dict, context: dict) -> dict:
    # NOTA: la tabla `Pagos` aún no se ha definido. Ajustar nombre y
    # campos lookup cuando se cree.
    items = _listar_por_dni(
        _TABLA_PAGOS,
        dni=args["dni"],
        estado=None,
        periodo=args.get("periodo"),
    )
    return {"pagos": items, "total": len(items)}


# ─────────────────────────────────────────────────────────────────────────
# 4. consultar_tope_disponible
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="consultar_tope_disponible",
    description=(
        "Consulta cuánto le queda al usuario del tope semanal de caja chica "
        "según su origen (sede u obra). Devuelve {tope, usado, disponible}."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dni":    {"type": "string", "description": "DNI del usuario."},
            "origen": {
                "type": "string",
                "enum": ["sede", "obra"],
                "description": "Origen del fondo: 'sede' u 'obra'.",
            },
        },
        "required": ["dni", "origen"],
    },
    category="consulta",
)
def consultar_tope_disponible(args: dict, context: dict) -> dict:
    """
    Devuelve el tope semanal según `origen` desde la configuración.

    El valor es netamente informativo: NO se calcula consumo real desde
    la tabla `solicitudes_caja`. La tabla no lleva campos para esto y
    el negocio prefiere usar el tope solo como referencia conversacional.
    """
    _ = args.get("dni")  # disponible para auditoría futura
    origen = args["origen"]

    config = context.get("config") or {}
    proceso = (config.get("proceso") or {}).get("caja_chica", {})
    tope = proceso.get(f"tope_semanal_{origen}", 0) or 0
    try:
        tope_f = float(tope)
    except (ValueError, TypeError):
        tope_f = 0.0

    return {
        "tope":       tope_f,
        "usado":      0.0,
        "disponible": tope_f,
        "origen":     origen,
        "nota": (
            "Valor informativo desde la configuración del proceso. "
            "No refleja consumo real (no se contabiliza desde la tabla)."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# 5. consultar_aprobador
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="consultar_aprobador",
    description=(
        "Devuelve el/los aprobador(es) que deben autorizar una solicitud "
        "según su monto, tipo, origen y opcionalmente el área."
    ),
    parameters={
        "type": "object",
        "properties": {
            "monto":  {"type": "number", "description": "Monto solicitado en soles."},
            "tipo":   {
                "type": "string",
                "description": "Tipo de fondo: 'caja-chica' o 'rendir'.",
            },
            "origen": {
                "type": "string",
                "enum": ["sede", "obra"],
            },
            "area":   {"type": "string", "description": "Área del solicitante (opcional)."},
        },
        "required": ["monto", "tipo", "origen"],
    },
    category="consulta",
)
def consultar_aprobador(args: dict, context: dict) -> dict:
    monto = float(args["monto"])
    tipo = args["tipo"]
    origen = args["origen"]
    area = args.get("area")

    config = context.get("config") or {}
    aprobadores = (config.get("proceso") or {}).get("caja_chica", {}).get("aprobadores", []) or []

    matches = []
    for a in aprobadores:
        if a.get("tipo") and a["tipo"] != tipo:
            continue
        if a.get("origen") and a["origen"] != origen:
            continue
        if area and a.get("area") and a["area"] != area:
            continue
        try:
            mmin = float(a["monto_min"]) if a.get("monto_min") is not None else None
            mmax = float(a["monto_max"]) if a.get("monto_max") is not None else None
        except (ValueError, TypeError):
            mmin = mmax = None
        if mmin is not None and monto < mmin:
            continue
        if mmax is not None and monto > mmax:
            continue
        matches.append(a)

    matches.sort(key=lambda a: int(a.get("nivel") or 99))

    aprobs = [
        {
            "dni":   a.get("aprobador_dni"),
            "nivel": a.get("nivel"),
            "tipo":  a.get("tipo"),
        }
        for a in matches
    ]

    return {
        "aprobadores": aprobs,
        "total":       len(aprobs),
    }


# ─────────────────────────────────────────────────────────────────────────
# 6. consultar_centros_costo
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="consultar_centros_costo",
    description=(
        "Devuelve la lista de centros de costo activos de la empresa. "
        "Útil cuando el usuario pregunta 'a qué centro de costo lo cargo'."
    ),
    parameters={
        "type":       "object",
        "properties": {},
    },
    category="consulta",
)
def consultar_centros_costo(args: dict, context: dict) -> dict:
    config = context.get("config") or {}
    centros = (config.get("proceso") or {}).get("caja_chica", {}).get("centros_costo", []) or []
    activos = [
        {"codigo": c.get("codigo"), "nombre": c.get("nombre")}
        for c in centros if c.get("activo")
    ]
    return {"centros_costo": activos, "total": len(activos)}


# ─────────────────────────────────────────────────────────────────────────
# 7. consultar_tipos_gasto
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="consultar_tipos_gasto",
    description=(
        "Devuelve la lista de tipos de gasto válidos de la empresa "
        "(ej. movilidad, materiales, refrigerios)."
    ),
    parameters={
        "type":       "object",
        "properties": {},
    },
    category="consulta",
)
def consultar_tipos_gasto(args: dict, context: dict) -> dict:
    config = context.get("config") or {}
    tipos = (config.get("proceso") or {}).get("caja_chica", {}).get("tipos_gasto", []) or []
    activos = [
        {
            "codigo":                t.get("codigo"),
            "nombre":                t.get("nombre"),
            "centro_costo_default":  t.get("centro_costo_default"),
        }
        for t in tipos if t.get("activo")
    ]
    return {"tipos_gasto": activos, "total": len(activos)}


# ─────────────────────────────────────────────────────────────────────────
# 8. consultar_resumen_caja_chica
# ─────────────────────────────────────────────────────────────────────────
# Etapas del ciclo de caja chica (en orden) según el negocio:
#   PENDIENTE_APROBACION_*  → en revisión, todavía no se puede pagar
#   POR_PAGAR              → aprobada, esperando desembolso del tesorero
#   POR_CONTABILIZAR       → pagada, esperando registro contable
#   POR_RENDIR             → desembolsada, usuario debe rendir gastos
#   FINALIZADO             → ciclo cerrado
#   RECHAZADO              → puede ocurrir en cualquier etapa
_BUCKETS_ESTADO = (
    "pendiente_aprobacion",
    "por_pagar",
    "por_contabilizar",
    "por_rendir",
    "finalizado",
    "rechazado",
    "sin_estado",
)


def _clasificar_estado(estado_raw) -> str:
    """Mapea el ESTADO crudo de Airtable a uno de los buckets del ciclo."""
    if not estado_raw:
        return "sin_estado"
    e = str(estado_raw).strip().upper()
    if not e:
        return "sin_estado"
    if e.startswith("PENDIENTE_APROBACION"):
        return "pendiente_aprobacion"
    if e == "POR_PAGAR":
        return "por_pagar"
    if e == "POR_CONTABILIZAR":
        return "por_contabilizar"
    if e == "POR_RENDIR":
        return "por_rendir"
    if e == "FINALIZADO":
        return "finalizado"
    if e == "RECHAZADO":
        return "rechazado"
    # Estado desconocido: lo agrupamos como sin_estado para no perderlo
    return "sin_estado"


@register(
    name="consultar_resumen_caja_chica",
    description=(
        "Devuelve un resumen agregado de las solicitudes de caja chica del "
        "usuario: conteo y monto total agrupados por etapa del ciclo "
        "(pendiente_aprobacion, por_pagar, por_contabilizar, por_rendir, "
        "finalizado, rechazado). Úsalo para responder preguntas como "
        "'¿cuánto tengo pendiente?', '¿cuánto me falta rendir?', '¿cómo voy "
        "este mes?', '¿cuánto me deben pagar?'. Si se especifica `periodo` "
        "filtra por mes de creación del registro."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dni":     {"type": "string", "description": "DNI del usuario (8 dígitos)."},
            "periodo": {
                "type": "string",
                "description": "Mes en formato YYYY-MM (filtra por createdTime).",
            },
        },
        "required": ["dni"],
    },
    category="consulta",
)
def consultar_resumen_caja_chica(args: dict, context: dict) -> dict:
    dni = args["dni"]
    periodo = args.get("periodo")

    partes = [f"{{{_CAMPO_DNI_SOLICITUDES}}}='{dni}'"]
    if periodo:
        # Filtramos por createdTime() ya que la tabla no tiene un campo
        # 'fecha' explícito visible.
        partes.append(f"DATETIME_FORMAT(CREATED_TIME(), 'YYYY-MM')='{periodo}'")
    formula = _formula_y(*partes)

    records = airtable_client.list_records(
        _TABLA_SOLICITUDES, filter_formula=formula
    )

    # Inicializar buckets con counts y montos en 0
    por_estado = {
        b: {"count": 0, "monto": 0.0} for b in _BUCKETS_ESTADO
    }

    monto_total = 0.0
    for r in records:
        f = r.get("fields", {})
        bucket = _clasificar_estado(f.get(_CAMPO_ESTADO))
        try:
            monto = float(f.get("TOTAL_GENERAL") or 0)
        except (ValueError, TypeError):
            monto = 0.0
        por_estado[bucket]["count"] += 1
        por_estado[bucket]["monto"] += monto
        monto_total += monto

    # Redondear todos los montos a 2 decimales
    for b in por_estado:
        por_estado[b]["monto"] = round(por_estado[b]["monto"], 2)

    return {
        "dni": dni,
        "periodo": periodo,
        "total_solicitudes": len(records),
        "monto_total": round(monto_total, 2),
        "por_estado": por_estado,
        # Resúmenes interpretables que el LLM suele necesitar de un solo tiro
        "monto_en_revision":      por_estado["pendiente_aprobacion"]["monto"],
        "monto_por_cobrar":       por_estado["por_pagar"]["monto"],
        "monto_pendiente_rendir": por_estado["por_rendir"]["monto"],
        "monto_finalizado":       por_estado["finalizado"]["monto"],
        "monto_rechazado":        por_estado["rechazado"]["monto"],
    }


# ─────────────────────────────────────────────────────────────────────────
# 9. consultar_solicitud_por_id
# ─────────────────────────────────────────────────────────────────────────

def _es_record_id_airtable(s: str) -> bool:
    """Heurística: los IDs internos de Airtable empiezan con 'rec' y tienen 17 chars."""
    return bool(s) and s.startswith("rec") and len(s) >= 14


@register(
    name="consultar_solicitud_por_id",
    description=(
        "Busca una solicitud de caja chica específica por su folio (campo "
        "NUMERO en Airtable, formato típico '000003 - 2026') o por su ID "
        "interno de Airtable. Acepta variantes: '000003 - 2026', '000003', "
        "'3' o el recId. Devuelve los datos completos si la encuentra, o "
        "{encontrado: false} si no."
    ),
    parameters={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": (
                    "Folio (NUMERO) o ID interno de Airtable. Ejemplos: "
                    "'000003 - 2026', '000003', '3', 'rec3eziJJhRpd3Wzs'."
                ),
            },
        },
        "required": ["id"],
    },
    category="consulta",
)
def consultar_solicitud_por_id(args: dict, context: dict) -> dict:
    raw = (args.get("id") or "").strip()
    if not raw:
        return {"encontrado": False, "motivo": "ID vacío."}

    # Caso 1: ID interno de Airtable
    if _es_record_id_airtable(raw):
        try:
            rec = airtable_client.get_record(_TABLA_SOLICITUDES, raw)
            return {"encontrado": True, "solicitud": rec.get("fields", {}), "id": rec.get("id")}
        except Exception as e:
            # 404 u otro error: lo tratamos como no encontrado para que el LLM
            # pueda explicarlo sin propagar el stacktrace.
            return {"encontrado": False, "motivo": f"No se pudo obtener el registro: {e}"}

    # Caso 2: folio (NUMERO). Aceptamos:
    #   "000003 - 2026"  → match exacto
    #   "000003"         → FIND parcial
    #   "3"              → padding a 6 dígitos
    candidatos = [raw]
    if raw.isdigit():
        candidatos.append(raw.zfill(6))

    # Escapamos comillas simples por si el folio las trae (defensivo).
    def _esc(s: str) -> str:
        return s.replace("'", "\\'")

    or_terms = [
        f"FIND('{_esc(c)}', {{NUMERO}} & '')>0" for c in candidatos
    ]
    formula = "OR(" + ", ".join(or_terms) + ")" if len(or_terms) > 1 else or_terms[0]

    records = airtable_client.list_records(
        _TABLA_SOLICITUDES, filter_formula=formula, max_records=5
    )
    if not records:
        return {"encontrado": False, "motivo": f"No existe solicitud con folio '{raw}'."}

    if len(records) == 1:
        r = records[0]
        return {"encontrado": True, "solicitud": r.get("fields", {}), "id": r.get("id")}

    # Múltiples coincidencias: devolvemos un listado mínimo para que el LLM
    # le pida al usuario que aclare cuál.
    return {
        "encontrado": True,
        "ambiguo": True,
        "candidatos": [
            {
                "id":     r.get("id"),
                "numero": r.get("fields", {}).get("NUMERO"),
                "estado": r.get("fields", {}).get(_CAMPO_ESTADO),
                "monto":  r.get("fields", {}).get("TOTAL_GENERAL"),
                "motivo": r.get("fields", {}).get("MOTIVO"),
            }
            for r in records
        ],
    }
