"""
Validadores de reglas de negocio.

Lanzan `ValidationError` cuando una validación falla. El `tool_registry`
captura esa excepción y devuelve al LLM `{"error": "validacion", "detail": ...}`,
de modo que el modelo puede explicarle el problema al usuario sin que la
request entera caiga.

Las validaciones leen los topes y catálogos del dict `config` (que viene
de `config_loader.load_full_config()`).
"""

from datetime import datetime


class ValidationError(Exception):
    """Error de regla de negocio recuperable a nivel de tool."""


def _proceso_caja_chica(config: dict) -> dict:
    """Helper: navega config → proceso.caja_chica con defaults seguros."""
    return ((config or {}).get("proceso", {}) or {}).get("caja_chica", {}) or {}


def validar_monto_contra_tope(monto: float, config: dict) -> None:
    """
    Verifica que `monto` no exceda el tope máximo por solicitud.
    """
    if monto is None:
        raise ValidationError("Falta el monto de la solicitud.")
    try:
        monto_f = float(monto)
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Monto inválido: {monto!r}.") from e

    if monto_f <= 0:
        raise ValidationError("El monto debe ser mayor a cero.")

    proceso = _proceso_caja_chica(config)
    activo = bool(proceso.get("monto_maximo_activo", False))
    tope = proceso.get("monto_maximo")

    if not activo or tope is None:
        return

    try:
        tope_f = float(tope)
    except (ValueError, TypeError):
        return

    if monto_f > tope_f:
        raise ValidationError(
            f"El monto S/{monto_f:,.2f} excede el tope máximo por solicitud de "
            f"S/{tope_f:,.2f}."
        )





def validar_plazo_rendicion(id_solicitud: str, config: dict) -> None:
    """
    Verifica que la solicitud `id_solicitud` no haya excedido el plazo
    de rendición configurado para su origen (sede / centro_costo).

    Lee la solicitud desde Airtable para obtener `origen` y `fecha_pago`
    (o `fecha` como fallback). Compara contra el plazo en
    `config.proceso.caja_chica.plazo_rendicion_<origen>`.

    Lanza ValidationError si:
      - Falta el id de solicitud
      - La solicitud no existe / no se puede leer
      - La solicitud no tiene origen válido o fecha
      - Han transcurrido más días que el plazo configurado
    """
    if not id_solicitud or not str(id_solicitud).strip():
        raise ValidationError("Falta el id de la solicitud.")

    # Import local para evitar ciclos al cargar el módulo.
    from . import airtable_client
    from .airtable_client import AirtableError

    try:
        record = airtable_client.get_record("Solicitudes", id_solicitud)
    except AirtableError as e:
        raise ValidationError(
            f"No se pudo leer la solicitud '{id_solicitud}' desde Airtable: {e}"
        ) from e

    fields = record.get("fields", {}) or {}
    origen = fields.get("origen")
    fecha_pago_raw = fields.get("fecha_pago") or fields.get("fecha")

    if origen not in ("sede", "centro_costo"):
        raise ValidationError(
            f"La solicitud '{id_solicitud}' no tiene un 'origen' válido "
            f"(esperado 'sede' o 'centro_costo', encontrado {origen!r})."
        )

    if not fecha_pago_raw:
        raise ValidationError(
            f"La solicitud '{id_solicitud}' no tiene fecha de pago "
            f"registrada — no se puede validar el plazo de rendición."
        )

    proceso = _proceso_caja_chica(config)
    plazo = proceso.get(f"plazo_rendicion_{origen}")
    if plazo is None:
        # Sin plazo configurado, no validamos (el config_loader habrá
        # advertido por stderr). El LLM puede notar que el plazo no está
        # definido en el sistema.
        return

    try:
        plazo_dias = int(plazo)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"Plazo de rendición mal configurado: {plazo!r}."
        ) from e

    # Fecha de pago: aceptamos 'YYYY-MM-DD' o ISO completo. Truncamos a 10
    # caracteres para usar fromisoformat con la fecha pelada.
    try:
        fecha_pago = datetime.fromisoformat(str(fecha_pago_raw)[:10]).date()
    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"Fecha de pago con formato inválido: {fecha_pago_raw!r}."
        ) from e

    hoy = datetime.now().date()
    dias_transcurridos = (hoy - fecha_pago).days

    if dias_transcurridos > plazo_dias:
        raise ValidationError(
            f"Plazo de rendición vencido: han transcurrido {dias_transcurridos} "
            f"días desde el pago, y el plazo máximo para origen '{origen}' "
            f"es de {plazo_dias} días calendario."
        )
