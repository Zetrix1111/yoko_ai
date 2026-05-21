"""
Tools de acción (write) — categoría 'accion'.

Importar este módulo registra todas las tools en `tool_registry.TOOLS`
gracias al side-effect del decorador `@register`.

Cada tool de escritura ejecuta sus validators ANTES de tocar Airtable.
Si la validación falla, la ValidationError sube hasta `execute_tool` y
se devuelve al LLM como `{"error": "validacion", "detail": "..."}` —
sin haber escrito nada.

Tabla principal que asume este módulo:

  • solicitudes_caja → SOLICITANTE, RESIDENTE, APROBADOR, CENTRO_COSTO, PLAZO,
                       MOTIVO, MONEDA, TOTAL_GENERAL, DETALLE_GASTO, ESTADO
"""

import os
import sys
from datetime import datetime

from _lib import airtable_client, solicitud_caja_processor
from _yoko._lib.tool_registry import register
from _lib.validators import (
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
    """
    Devuelve el `empresa_id` del contexto. Multi-tenant (Fase 3): lo
    inyecta el handler tras validar el JWT. Sin fallback al env porque
    eso permitiría cross-tenant leak si por alguna razón el contexto
    llega vacío.

    Si vino bajo `context["empresa_id"]` (camino preferido) lo usamos.
    Si no, intentamos `context["config"]["empresa"]["id"]` (compat con
    rutas que solo construyeron el config). Si tampoco hay → error.
    """
    eid = context.get("empresa_id")
    if not eid:
        config = context.get("config") or {}
        eid = (config.get("empresa") or {}).get("id")
    if not eid:
        raise ValidationError("empresa_id ausente en el contexto.")
    return eid


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
# 1. yoko_procesar_solicitud_caja
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="yoko_procesar_solicitud_caja",
    description=(
        "Procesa documentos adjuntos de solicitud de caja chica usando el "
        "template `caja_chica`. Devuelve campos extraídos para que el agente "
        "los resuma y pida solo lo faltante antes de crear la solicitud."
    ),
    parameters={
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "description": (
                    "Lista opcional de archivos con filename/content_b64. "
                    "Normalmente se omite porque el backend inyecta el carrito "
                    "de archivos de la sesión."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content_b64": {"type": "string"},
                    },
                },
            },
        },
    },
    category="accion",
)
def procesar_solicitud_caja(args: dict, context: dict) -> dict:
    tool_args = dict(args or {})
    if not tool_args.get("files") and context.get("session_id_for_cart"):
        tool_args["session_id_for_cart"] = context["session_id_for_cart"]
    return solicitud_caja_processor.procesar_solicitud_caja(tool_args)


# ─────────────────────────────────────────────────────────────────────────
# 2. yoko_crear_solicitud
# ─────────────────────────────────────────────────────────────────────────

@register(
    name="yoko_crear_solicitud",
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
            "centro_costo":  {"type": "string", "description": "Centro de costo asociado, si aplica en la empresa."},
            "total_general": {"type": "number", "description": "Monto total a solicitar (numérico)."},
            "detalle_gasto": {"type": "string", "description": "Descripción detallada del gasto a realizar."},
            "aprobador_id":  {"type": "string", "description": "Record ID del aprobador (APROBADOR_2). Obligatorio solo si la empresa tiene requiere_aprobacion=true. Si la empresa NO requiere aprobación, omitir y la solicitud queda en PENDIENTE_PAGO."},
            "residente_id":  {"type": "string", "description": "Record ID del residente (APROBADOR_1) elegido por el usuario. Omitir si el usuario indica que no aplica."},
        },
        "required": ["plazo", "motivo", "moneda", "total_general", "detalle_gasto"],
    },
    category="accion",
)
def crear_solicitud(args: dict, context: dict) -> dict:
    plazo = args["plazo"]
    motivo = args["motivo"]
    moneda = args["moneda"]
    centro_costo = args.get("centro_costo")
    total_general = args["total_general"]
    detalle_gasto = args["detalle_gasto"]
    aprobador_id = args.get("aprobador_id")  # opcional: solo si la empresa requiere aprobación
    residente_id = args.get("residente_id")  # opcional

    config = context.get("config") or {}
    dni = _user_dni(context)
    user = context.get("user") or {}
    nombre = user.get("nombre") or ""
    record_id = user.get("record_id")

    # ── Validaciones ANTES de tocar Airtable ──
    # Usamos total_general como monto. Ya no existe origen separado.
    validar_monto_contra_tope(total_general, config)

    # ── Estado inicial ──
    # Si la empresa no requiere aprobación (o el LLM no envía aprobador_id porque
    # consultar_aprobador devolvió vacío), la solicitud salta el flujo de
    # aprobación y queda directo lista para que Tesorería procese el pago.
    if aprobador_id:
        estado = "PENDIENTE_APROBACION_RESIDENTE" if residente_id else "PENDIENTE_APROBACION_JEFATURA_SEDE"
    else:
        estado = "PENDIENTE_PAGO"

    # ── Escritura ──
    fields = {
        "NOMBRE":        nombre,
        "PLAZO":         plazo,
        "MOTIVO":        motivo,
        "MONEDA":        moneda,
        "TOTAL_GENERAL": float(total_general),
        "DETALLE_GASTO": detalle_gasto,
        "ESTADO":        estado,
    }

    if aprobador_id:
        fields["APROBADOR"] = [aprobador_id]

    if centro_costo:
        fields["CENTRO_COSTO"] = centro_costo

    if record_id:
        fields["SOLICITANTE"] = [record_id]

    if residente_id:
        fields["RESIDENTE"] = [residente_id]

    record = airtable_client.create_record(_TABLA_SOLICITUDES, fields)
    return {"id": record["id"], "fields": record["fields"]}


# ─────────────────────────────────────────────────────────────────────────
# 3. iniciar_rendicion
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
