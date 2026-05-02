"""
Tools de acción (write) — categoría 'accion'.

Importar este módulo registra todas las tools en `tool_registry.TOOLS`
gracias al side-effect del decorador `@register`.

Cada tool de escritura ejecuta sus validators ANTES de tocar Airtable.
Si la validación falla, la ValidationError sube hasta `execute_tool` y
se devuelve al LLM como `{"error": "validacion", "detail": "..."}` —
sin haber escrito nada.

Tablas Airtable que asume este módulo:

  • Solicitudes      → empresa_id, dni, monto, tipo, origen, justificacion,
                       destino, numero_cuenta, centro_costo?, estado, fecha
  • Rendiciones      → empresa_id, dni, id_solicitud, periodo,
                       estado, fecha_inicio
  • ItemsRendicion   → empresa_id, id_rendicion, tipo_comprobante,
                       ruc_emisor, razon_social_emisor, numero_comprobante,
                       fecha_emision, monto, igv, concepto, centro_costo?
"""

import os
import sys
from datetime import datetime

from .. import airtable_client
from ..tool_registry import register
from ..validators import (
    ValidationError,
    validar_monto_contra_tope,
    validar_plazo_rendicion,
)


_TABLA_SOLICITUDES   = "solicitudes_caja"
_TABLA_RENDICIONES   = "Rendiciones"
_TABLA_ITEMS_RENDIC  = "ItemsRendicion"


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _tenant_id(context: dict) -> str:
    config = context.get("config") or {}
    tid = (config.get("empresa") or {}).get("id")
    return tid or os.environ.get("TENANT_ID", "cmejia")


def _user_dni(context: dict) -> str:
    user = context.get("user") or {}
    dni = user.get("dni")
    if not dni:
        raise ValidationError(
            "No se pudo identificar al usuario (DNI ausente en la sesión)."
        )
    return str(dni)





def _hoy_iso() -> str:
    return datetime.now().date().isoformat()


# ─────────────────────────────────────────────────────────────────────────
# 1. crear_solicitud
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="crear_solicitud",
    description=(
        "Crea una nueva solicitud de caja chica. "
        "Valida el tope de monto antes de escribir. Si falla la validación, "
        "NO se crea el registro y se le explica al usuario."
    ),
    parameters={
        "type": "object",
        "properties": {
            "plazo":         {"type": "string", "description": "Plazo para la caja chica (ej. cantidad de días, o fecha desde/hasta)."},
            "motivo":        {"type": "string", "description": "Motivo general de la solicitud (ej. Compra de utiles)."},
            "moneda":        {
                "type": "string", 
                "enum": ["PEN", "USD", "EUR", "CNY"], 
                "description": "Moneda de la solicitud."
            },
            "obra":          {"type": "string", "description": "Nombre de la obra o area que pertenece el gasto."},
            "total_general": {"type": "number", "description": "Monto total a solicitar (numérico)."},
            "tipo_gasto":    {
                "type": "string", 
                "enum": ["CAJA CHICA", "PASAJES AEREOS", "CAJA EXTRAORDINARIA"], 
                "description": "Clasificación del tipo de gasto."
            },
            "detalle_gasto": {"type": "string", "description": "Descripción detallada del gasto a realizar."},
            "aprobador_id":  {"type": "string", "description": "Record ID del aprobador (APROBADOR_2) elegido por el usuario. SIEMPRE obligatorio."},
            "residente_id":  {"type": "string", "description": "Record ID del residente (APROBADOR_1) elegido por el usuario. Omitir si el usuario indica que no aplica."},
        },
        "required": ["plazo", "motivo", "moneda", "obra", "total_general", "tipo_gasto", "detalle_gasto", "aprobador_id"],
    },
    category="accion",
)
def crear_solicitud(args: dict, context: dict) -> dict:
    plazo = args["plazo"]
    motivo = args["motivo"]
    moneda = args["moneda"]
    obra = args["obra"]
    total_general = args["total_general"]
    tipo_gasto = args["tipo_gasto"]
    detalle_gasto = args["detalle_gasto"]
    aprobador_id = args["aprobador_id"]
    residente_id = args.get("residente_id")  # opcional

    config = context.get("config") or {}
    dni = _user_dni(context)
    user = context.get("user") or {}
    nombre = user.get("nombre") or ""
    record_id = user.get("record_id")

    # ── Validaciones ANTES de tocar Airtable ──
    # Usamos total_general como monto. Ya no existe origen (sede/obra).
    validar_monto_contra_tope(total_general, config)

    # ── Estado inicial según presencia de Residente ──
    estado = "PENDIENTE_APROBACION_RESIDENTE" if residente_id else "PENDIENTE_APROBACION_JEFATURA_SEDE"

    # ── Escritura ──
    fields = {
        "NOMBRE":        nombre,
        "PLAZO":         plazo,
        "MOTIVO":        motivo,
        "MONEDA":        moneda,
        "OBRA":          obra,
        "TOTAL_GENERAL": float(total_general),
        "TIPO_GASTO":    tipo_gasto,
        "DETALLE_GASTO": detalle_gasto,
        "APROBADOR":     [aprobador_id],
        "ESTADO":        estado,
    }

    if record_id:
        fields["SOLICITANTE"] = [record_id]

    if residente_id:
        fields["RESIDENTE"] = [residente_id]

    record = airtable_client.create_record(_TABLA_SOLICITUDES, fields)
    return {"id": record["id"], "fields": record["fields"]}


# ─────────────────────────────────────────────────────────────────────────
# 2. iniciar_rendicion
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="iniciar_rendicion",
    description=(
        "Inicia una rendición ligada a una solicitud previamente pagada. "
        "Valida que la solicitud esté dentro del plazo de rendición."
    ),
    parameters={
        "type": "object",
        "properties": {
            "id_solicitud": {
                "type": "string",
                "description": "recId de la solicitud (ej. 'rec123abc').",
            },
            "periodo": {
                "type": "string",
                "description": "Mes contable de la rendición (YYYY-MM).",
            },
        },
        "required": ["id_solicitud", "periodo"],
    },
    category="accion",
)
def iniciar_rendicion(args: dict, context: dict) -> dict:
    id_solicitud = args["id_solicitud"]
    periodo = args["periodo"]

    config = context.get("config") or {}
    dni = _user_dni(context)

    # ── Validaciones ──
    validar_plazo_rendicion(id_solicitud, config)

    # ── Escritura ──
    fields = {
        "empresa_id":    _tenant_id(context),
        "dni":           dni,
        "id_solicitud":  id_solicitud,   # como string. Si tu campo es Linked Record, cambia a [id_solicitud].
        "periodo":       periodo,
        "estado":        "pendiente",
        "fecha_inicio":  _hoy_iso(),
    }
    record = airtable_client.create_record(_TABLA_RENDICIONES, fields)
    return {"id": record["id"], "fields": record["fields"]}


# ─────────────────────────────────────────────────────────────────────────
# 3. agregar_item_rendicion
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="agregar_item_rendicion",
    description=(
        "Agrega un comprobante (factura, boleta, recibo) a una rendición "
        "existente. Valida el centro de costo si la empresa lo exige."
    ),
    parameters={
        "type": "object",
        "properties": {
            "id_rendicion":        {"type": "string", "description": "recId de la rendición."},
            "tipo_comprobante":    {
                "type": "string",
                "description": "Tipo de comprobante (Factura, Boleta, Recibo, Ticket, etc.).",
            },
            "ruc_emisor":          {"type": "string", "description": "RUC del proveedor (11 dígitos)."},
            "razon_social_emisor": {"type": "string", "description": "Razón social del proveedor."},
            "numero_comprobante":  {
                "type": "string",
                "description": "Número del comprobante (ej. F001-12345).",
            },
            "fecha_emision":       {"type": "string", "description": "Fecha de emisión (YYYY-MM-DD)."},
            "monto":               {"type": "number", "description": "Total del comprobante incluyendo IGV."},
            "igv":                 {"type": "number", "description": "Monto del IGV (puede ser 0)."},
            "concepto":            {"type": "string", "description": "Descripción del gasto."},

        },
        "required": [
            "id_rendicion", "tipo_comprobante", "ruc_emisor",
            "razon_social_emisor", "numero_comprobante", "fecha_emision",
            "monto", "igv", "concepto",
        ],
    },
    category="accion",
)
def agregar_item_rendicion(args: dict, context: dict) -> dict:
    id_rendicion = args["id_rendicion"]
    config = context.get("config") or {}

    # ── Escritura ──
    fields = {
        "empresa_id":          _tenant_id(context),
        "id_rendicion":        id_rendicion,
        "tipo_comprobante":    args["tipo_comprobante"],
        "ruc_emisor":          args["ruc_emisor"],
        "razon_social_emisor": args["razon_social_emisor"],
        "numero_comprobante":  args["numero_comprobante"],
        "fecha_emision":       args["fecha_emision"],
        "monto":               float(args["monto"]),
        "igv":                 float(args["igv"]),
        "concepto":            args["concepto"],
    }


    record = airtable_client.create_record(_TABLA_ITEMS_RENDIC, fields)
    return {"id": record["id"], "fields": record["fields"]}


# ─────────────────────────────────────────────────────────────────────────
# 4. enviar_para_aprobacion
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="enviar_para_aprobacion",
    description=(
        "Cambia el estado de una solicitud o rendición a 'pendiente_aprobacion' "
        "para que el flujo de aprobaciones la procese. Úsalo cuando el usuario "
        "confirme que quiere enviar el documento ya armado."
    ),
    parameters={
        "type": "object",
        "properties": {
            "id":   {"type": "string", "description": "recId del registro a enviar."},
            "tipo": {
                "type": "string",
                "enum": ["solicitud", "rendicion"],
                "description": "Tipo de documento.",
            },
        },
        "required": ["id", "tipo"],
    },
    category="accion",
)
def enviar_para_aprobacion(args: dict, context: dict) -> dict:
    id_record = args["id"]
    tipo = args["tipo"]

    if tipo == "solicitud":
        tabla = _TABLA_SOLICITUDES
    elif tipo == "rendicion":
        tabla = _TABLA_RENDICIONES
    else:
        raise ValidationError(
            f"Tipo inválido: {tipo!r}. Debe ser 'solicitud' o 'rendicion'."
        )

    record = airtable_client.update_record(
        tabla,
        id_record,
        {"estado": "pendiente_aprobacion"},
    )

    # TODO: disparar webhook a Make para notificar al primer aprobador
    # según `consultar_aprobador`. Env var sugerida:
    #   MAKE_WEBHOOK_APROBACION_PENDIENTE
    webhook = os.environ.get("MAKE_WEBHOOK_APROBACION_PENDIENTE")
    if not webhook:
        print(
            "[accion/enviar_para_aprobacion] MAKE_WEBHOOK_APROBACION_PENDIENTE "
            "no configurado — el aprobador no será notificado automáticamente.",
            file=sys.stderr,
        )

    return {
        "id":             record["id"],
        "tipo":           tipo,
        "estado":         "pendiente_aprobacion",
        "notificado":     False,  # cambiará a True cuando se implemente el webhook
    }
