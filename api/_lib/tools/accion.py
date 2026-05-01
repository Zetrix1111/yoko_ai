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
    validar_centro_costo,
    validar_monto_contra_tope,
    validar_plazo_rendicion,
)


_TABLA_SOLICITUDES   = "Solicitudes"
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


def _aplica_centro_costo(config: dict) -> bool:
    proceso = (config or {}).get("proceso", {}).get("caja_chica", {})
    # Default True si no está configurado: comportamiento conservador
    # (mejor exigir un campo y errar a estricto que olvidar registrar uno).
    return bool(proceso.get("aplica_centro_costo", True))


def _hoy_iso() -> str:
    return datetime.now().date().isoformat()


# ─────────────────────────────────────────────────────────────────────────
# 1. crear_solicitud
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="crear_solicitud",
    description=(
        "Crea una nueva solicitud de fondos (caja chica o entrega a rendir). "
        "Valida tope semanal y centro de costo antes de escribir. Si falla "
        "una validación, NO se crea el registro y se le explica al usuario."
    ),
    parameters={
        "type": "object",
        "properties": {
            "monto":         {"type": "number", "description": "Monto en soles."},
            "tipo":          {
                "type": "string",
                "enum": ["caja-chica", "rendir"],
                "description": "Tipo de fondo solicitado.",
            },
            "origen":        {
                "type": "string",
                "enum": ["sede", "obra"],
                "description": "Origen del fondo.",
            },
            "justificacion": {"type": "string", "description": "Motivo o sustento."},
            "destino":       {
                "type": "string",
                "description": "A quién o a qué se destina el fondo (proveedor, obra, etc.).",
            },
            "centro_costo":  {
                "type": "string",
                "description": "Código del centro de costo. Obligatorio si aplica_centro_costo=True.",
            },
            "numero_cuenta": {
                "type": "string",
                "description": "Cuenta bancaria de depósito.",
            },
        },
        "required": ["monto", "tipo", "origen", "justificacion", "destino", "numero_cuenta"],
    },
    category="accion",
)
def crear_solicitud(args: dict, context: dict) -> dict:
    monto = args["monto"]
    tipo = args["tipo"]
    origen = args["origen"]
    justificacion = args["justificacion"]
    destino = args["destino"]
    centro_costo = args.get("centro_costo")
    numero_cuenta = args["numero_cuenta"]

    config = context.get("config") or {}
    dni = _user_dni(context)

    # ── Validaciones ANTES de tocar Airtable ──
    validar_monto_contra_tope(monto, dni, origen, config)

    if _aplica_centro_costo(config):
        if not centro_costo:
            raise ValidationError(
                "Esta empresa exige asignar un centro de costo a cada solicitud. "
                "Indica el código (consulta los activos con `consultar_centros_costo`)."
            )
        validar_centro_costo(centro_costo, config)

    # ── Escritura ──
    fields = {
        "empresa_id":    _tenant_id(context),
        "dni":           dni,
        "monto":         float(monto),
        "tipo":          tipo,
        "origen":        origen,
        "justificacion": justificacion,
        "destino":       destino,
        "numero_cuenta": numero_cuenta,
        "estado":        "pendiente",
        "fecha":         _hoy_iso(),
    }
    if centro_costo:
        fields["centro_costo"] = centro_costo

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
            "centro_costo":        {
                "type": "string",
                "description": "Código del centro de costo. Obligatorio si aplica_centro_costo=True.",
            },
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
    centro_costo = args.get("centro_costo")
    config = context.get("config") or {}

    # ── Validaciones ──
    if _aplica_centro_costo(config):
        if not centro_costo:
            raise ValidationError(
                "Esta empresa exige asignar un centro de costo a cada item "
                "de rendición. Indica el código."
            )
        validar_centro_costo(centro_costo, config)

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
    if centro_costo:
        fields["centro_costo"] = centro_costo

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
