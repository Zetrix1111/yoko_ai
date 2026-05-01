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


def validar_monto_contra_tope(
    monto: float,
    dni: str,
    origen: str,
    config: dict,
) -> None:
    """
    Verifica que `monto` no exceda el tope semanal según `origen` (sede/obra).

    No considera el "ya consumido" en la semana — para eso se usa la tool
    `consultar_tope_disponible`. Esta validación es solo contra el tope
    nominal (límite duro por transacción individual).

    Lanza ValidationError si:
      - monto no es numérico
      - origen no es 'sede' u 'obra'
      - monto > tope configurado
    """
    if monto is None:
        raise ValidationError("Falta el monto de la solicitud.")
    try:
        monto_f = float(monto)
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Monto inválido: {monto!r}.") from e

    if monto_f <= 0:
        raise ValidationError("El monto debe ser mayor a cero.")

    if origen not in ("sede", "obra"):
        raise ValidationError(
            f"Origen inválido: {origen!r}. Debe ser 'sede' u 'obra'."
        )

    proceso = _proceso_caja_chica(config)
    clave_tope = f"tope_semanal_{origen}"
    tope = proceso.get(clave_tope)

    if tope is None:
        # Si no está configurado, no podemos validar — lo dejamos pasar
        # para no bloquear el flujo. El LLM verá el resultado y advertirá.
        return

    try:
        tope_f = float(tope)
    except (ValueError, TypeError):
        return

    if monto_f > tope_f:
        # Incluimos el DNI en el mensaje para que el LLM tenga contexto del
        # usuario afectado y pueda mencionarlo si la conversación lo amerita.
        raise ValidationError(
            f"El monto S/{monto_f:,.2f} excede el tope semanal de "
            f"S/{tope_f:,.2f} para origen '{origen}' (DNI {dni})."
        )


def validar_centro_costo(codigo: str, config: dict) -> None:
    """
    Verifica que `codigo` corresponda a un centro de costo activo del tenant.

    Lanza ValidationError con la lista de códigos válidos en el detalle
    para que el LLM pueda sugerirle al usuario un centro válido.
    """
    if not codigo or not str(codigo).strip():
        raise ValidationError("Falta el código del centro de costo.")

    codigo = str(codigo).strip()
    proceso = _proceso_caja_chica(config)
    centros = proceso.get("centros_costo", []) or []

    activos = [c for c in centros if c.get("activo")]
    valid = next((c for c in activos if c.get("codigo") == codigo), None)

    if valid:
        return

    codigos_validos = [c.get("codigo", "?") for c in activos]
    if not codigos_validos:
        raise ValidationError(
            f"Centro de costo '{codigo}' no existe. No hay centros activos "
            f"configurados para esta empresa."
        )

    raise ValidationError(
        f"Centro de costo '{codigo}' no está activo o no existe. "
        f"Códigos válidos: {', '.join(codigos_validos)}."
    )


def validar_plazo_rendicion(id_solicitud: str, config: dict) -> None:
    """
    Verifica que la solicitud `id_solicitud` no haya excedido el plazo
    de rendición configurado para su origen (sede / obra).

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

    if origen not in ("sede", "obra"):
        raise ValidationError(
            f"La solicitud '{id_solicitud}' no tiene un 'origen' válido "
            f"(esperado 'sede' u 'obra', encontrado {origen!r})."
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
