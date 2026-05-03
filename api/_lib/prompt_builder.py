"""
Prompt builder — arma el system prompt en 5 capas:

  1. Identidad        ← config.empresa.agent.name + razon_social
  2. Capacidades      ← config.empresa.modules
  3. Usuario actual   ← user (de la sesión)
  4. Reglas proceso   ← config.proceso.caja_chica (Airtable Config_*)
  5. Comportamiento   ← constantes literales

Las secciones de "centros de costo" y "tipos de gasto" se omiten por
completo cuando los flags `aplica_centro_costo` / `aplica_tipo_gasto`
del proceso son False.

`build_tools_list` es un stub por ahora — se llenará cuando construyamos
api/_lib/tool_registry.py.
"""

# Mapeo id de módulo → nombre legible para el LLM.
# Si un id no está acá, se usa un fallback titlecased.
MODULE_NAMES = {
    "alerta-segura":         "Notificaciones y Alertas",
    "gestion-caja":          "Gestión de Caja Chica",
    "facturas-inteligentes": "Facturas Inteligentes",
    "configuracion-empresa": "Configuración de Empresa",
}


# ─────────────────────────────────────────────────────────────────────────
# Helpers de formateo
# ─────────────────────────────────────────────────────────────────────────

def _module_name(module_id: str) -> str:
    """Convierte un id de módulo en su nombre legible."""
    if module_id in MODULE_NAMES:
        return MODULE_NAMES[module_id]
    return module_id.replace("-", " ").replace("_", " ").title()


def _format_modules(modules: list) -> str:
    """Lista de ids → frase tipo 'A, B y C'."""
    if not modules:
        return "ninguno habilitado"
    names = [_module_name(m) for m in modules]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " y " + names[-1]


def _format_money(value) -> str:
    """Formatea un número con separador de miles (estilo S/2,000)."""
    if value is None:
        return "no configurado"
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        try:
            return f"{float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)


def _coerce_str(value) -> str:
    """Si Airtable devuelve un linked record (lista), toma el primer item."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value is not None else ""


def _format_aprobadores(aprobadores: list) -> str:
    """
    Formatea la lista de aprobadores como bullets en lenguaje natural.
    Devuelve string que se concatena directamente DESPUÉS de
    '- Aprobadores:' (incluye el "\\n" inicial cuando hay items).
    """
    if not aprobadores:
        return " no configurados todavía."

    # Ordenamos por nivel ascendente; nivel ausente va al final.
    def _nivel_key(a):
        try:
            return int(a.get("nivel") or 99)
        except (ValueError, TypeError):
            return 99

    items = []
    for a in sorted(aprobadores, key=_nivel_key):
        nivel = a.get("nivel", "?")
        dni = _coerce_str(a.get("aprobador_dni")) or "—"

        partes = []
        mmin = a.get("monto_min")
        mmax = a.get("monto_max")
        if mmin is not None and mmax is not None:
            partes.append(f"montos S/{_format_money(mmin)} a S/{_format_money(mmax)}")
        elif mmax is not None:
            partes.append(f"hasta S/{_format_money(mmax)}")
        elif mmin is not None:
            partes.append(f"desde S/{_format_money(mmin)}")

        if a.get("area"):
            partes.append(f"área {_coerce_str(a['area'])}")
        if a.get("tipo"):
            partes.append(f"tipo {_coerce_str(a['tipo'])}")
        if a.get("origen"):
            partes.append(f"origen {_coerce_str(a['origen'])}")

        suffix = f" ({', '.join(partes)})" if partes else ""
        items.append(f"  • Nivel {nivel}: DNI {dni}{suffix}")

    return "\n" + "\n".join(items)



# ─────────────────────────────────────────────────────────────────────────
# Sales prompt (modo "ventas") — usado por /api/sales_chat
# ─────────────────────────────────────────────────────────────────────────

def _format_producto_inline(p: dict) -> str:
    """Una línea compacta por producto para el catálogo del prompt."""
    estado = p.get("estado_stock", "")
    estado_label = {
        "disponible":  "disponible",
        "bajo_stock":  "BAJO STOCK",
        "sin_stock":   "AGOTADO",
        "servicio":    "servicio",
    }.get(estado, estado)
    precio = p.get("precio") or 0
    try:
        precio_f = float(precio)
    except (ValueError, TypeError):
        precio_f = 0.0
    nombre = p.get("nombre") or "—"
    rec_id = p.get("id") or ""
    line = f"- [{rec_id}] {nombre} — S/ {precio_f:,.2f} ({estado_label})"
    return line


def _build_sales_prompt(config: dict, ctx: dict) -> str:
    """
    Prompt especializado para el agente de ventas que corre detrás del
    bot-baileys. NO incluye la secuencia de caja chica. Embebe el catálogo
    de productos y reglas de tono comercial.
    """
    empresa = (config or {}).get("empresa", {}) or {}
    razon_social = empresa.get("razon_social") or empresa.get("id") or "la empresa"
    ruc = empresa.get("ruc") or ""

    productos = ctx.get("productos") or []
    sender = ctx.get("sender") or {}
    sender_nombre = sender.get("nombre") or "el cliente"
    sender_phone = sender.get("phone") or ""

    identidad = f"Eres un vendedor virtual de {razon_social}"
    if ruc:
        identidad += f" (RUC {ruc})"
    identidad += "."

    lines: list[str] = [
        identidad,
        "Estás respondiendo conversaciones de WhatsApp con clientes potenciales.",
        "Tu objetivo: ayudar al cliente a encontrar el producto que necesita y darle "
        "información clara y precisa para que pueda decidir comprar.",
        "",
        "# CLIENTE ACTUAL",
        f"- Nombre (pushname WhatsApp): {sender_nombre}",
        f"- Teléfono: {sender_phone or '—'}",
        "",
        "# CATÁLOGO DISPONIBLE",
        f"({len(productos)} productos/servicios activos del catálogo)",
        "",
    ]

    if productos:
        for p in productos:
            lines.append(_format_producto_inline(p))
    else:
        lines.append("(No hay productos cargados aún en el catálogo.)")

    lines.extend([
        "",
        "# HERRAMIENTAS",
        "Tienes dos herramientas disponibles:",
        "- `consultar_productos(query?, solo_disponibles?, categoria?)` → "
        "búsqueda más detallada en el catálogo. Úsala si necesitás más info que la "
        "del listado de arriba (descripción completa, keywords, foto).",
        "- `consultar_stock(producto_id | nombre)` → stock exacto de un producto.",
        "",
        "# COMPORTAMIENTO",
        "1. Saludá cordialmente la primera vez. En mensajes siguientes ya no saludes.",
        "2. Respondé en español neutro, profesional, cálido. Mensajes BREVES (2-4 líneas).",
        "3. NUNCA inventes precios, stock o características. Si no está en el catálogo, "
        "decí honestamente que vas a consultarlo con un asesor.",
        "4. Si el producto está AGOTADO, decílo con claridad y ofrecé alternativas similares.",
        "5. Si el cliente pregunta por algo que no vendés, sugerí lo más cercano que "
        "tengas o decí que no manejas ese rubro.",
        "6. Cuando el cliente muestra intención clara de compra ('quiero comprar', "
        "'me interesa', 'cómo lo pago'), pasá a modo cierre: confirmá producto y "
        "precio, pedí cantidad, y avisá que un asesor humano lo va a contactar para "
        "concretar el pago y la entrega.",
        "7. NO uses emojis. NO uses markdown (**, *, #). El cliente lo lee en WhatsApp.",
        "8. Si el cliente pide algo fuera de tu alcance (cotización formal, cambio "
        "de pedido, queja), respondé: 'Te derivo con un asesor humano para que te ayude.'",
    ])

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def build_system_prompt(
    config: dict,
    user: dict,
    extra_context: dict | None = None,
) -> str:
    """
    Construye el system prompt en español a partir de la config completa
    (estática + dinámica) y los datos del usuario actual.

    Las reglas del proceso de caja chica se arman condicionalmente según
    los flags del config.proceso.caja_chica:

      • monto_maximo_activo / monto_maximo  → tope por solicitud (o sin límite)
      • requiere_aprobacion / num_aprobadores → si pasa por aprobación
      • aprobacion_rendicion                 → si las rendiciones se aprueban
      • aplica_centro_costo                  → muestra lista de centros activos
      • aplica_tipo_gasto                    → muestra lista de tipos

    `extra_context` permite cambiar el modo del prompt:
      • {"modo": "ventas", "productos": [...], "sender": {phone, nombre}}
        → prompt especializado para el agente de ventas (WhatsApp via
        bot-baileys), con catálogo embebido y reglas de venta. NO incluye
        la secuencia de caja chica.
    """
    if extra_context and extra_context.get("modo") == "ventas":
        return _build_sales_prompt(config, extra_context)

    empresa = (config or {}).get("empresa", {}) or {}
    proceso = ((config or {}).get("proceso", {}) or {}).get("caja_chica", {}) or {}

    agent = empresa.get("agent") or {}
    agent_name = agent.get("name") or "tu asistente"
    razon_social = empresa.get("razon_social") or empresa.get("id") or "la empresa"
    ruc = empresa.get("ruc") or ""
    sistema_contable = empresa.get("sistema_contable") or "no configurado"
    modules = empresa.get("modules") or []

    # Flags del proceso (con defaults conservadores)
    monto_max_activo = bool(proceso.get("monto_maximo_activo", False))
    monto_max = proceso.get("monto_maximo", 0)
    requiere_aprob = bool(proceso.get("requiere_aprobacion", True))
    num_aprob = proceso.get("num_aprobadores")
    aprob_rendicion = bool(proceso.get("aprobacion_rendicion", False))


    # Línea de identidad: incluye RUC si está disponible
    identidad = f"Eres {agent_name}, asistente virtual de {razon_social}"
    if ruc:
        identidad += f" (RUC {ruc})"
    identidad += "."

    lines: list[str] = [
        identidad,
        f"Sistema contable destino: {sistema_contable}.",
        "",
        "# CAPACIDADES",
        f"En esta sesión puedes ayudar con los módulos: {_format_modules(modules)}.",
        "Tienes herramientas para consultar información del usuario, registrar acciones, y llevar al usuario a pantallas específicas de la app.",
        "",
        "# USUARIO ACTUAL",
        f"- Nombre: {user.get('nombre') or '—'}",
        f"- Cargo: {user.get('cargo') or '—'}",
        f"- DNI: {user.get('dni') or '—'}",
        "",
        "# SECUENCIA OPERATIVA DE CAJA CHICA",
        "El ciclo de vida de caja chica sigue estrictamente estos pasos:",
        "1. El usuario inicia creando una **Solicitud** de caja chica.",
        "2. La solicitud pasa a revisión de los **Aprobadores** (según la cantidad de niveles requeridos). Al ser aprobada, se notifica por correo.",
        "3. El tesorero procede a realizar el **Pago** de la solicitud aprobada.",
        "4. El usuario realiza la **Rendición** de los gastos efectuados con el dinero recibido.",
        "",
        "RESTRICCIÓN IMPORTANTE DE GESTIÓN POR CHAT:",
        "Como asistente IA en este chat, tu capacidad de gestión directa está limitada ÚNICAMENTE a **'Solicitudes'** y **'Rendiciones'**.",
        "Para todo lo demás (Dashboard, Aprobaciones, Pagos, Reportes o Configuración), NO intentes gestionarlo por el chat. Debes explicarle al usuario que esa acción se realiza desde el módulo visual correspondiente y usar tus herramientas (tools) para redirigirlo a esa pantalla.",
        "",
        "# REGLAS Y LÍMITES DEL PROCESO",
    ]

    # ── Monto máximo por solicitud ──
    if monto_max_activo and monto_max:
        lines.append(
            f"- Monto máximo por solicitud: S/{_format_money(monto_max)}. "
            f"No se aceptan solicitudes que excedan este monto."
        )
    else:
        lines.append(
            "- No hay un monto máximo por solicitud configurado — el sistema "
            "acepta solicitudes de cualquier monto."
        )

    # ── Flujo de aprobación ──
    if requiere_aprob:
        if num_aprob:
            lines.append(
                f"- Las solicitudes requieren {num_aprob} "
                f"{'aprobación' if int(num_aprob) == 1 else 'aprobaciones'} "
                f"antes de pasar a Pagos."
            )
    else:
        lines.append(
            "- Las solicitudes no requieren aprobación — pasan directo al "
            "estado de Pagos."
        )

    # ── Aprobación de rendición ──
    if aprob_rendicion:
        lines.append(
            "- Las rendiciones deben pasar por aprobación antes de quedar "
            "registradas como válidas."
        )
    else:
        lines.append(
            "- Las rendiciones se aceptan automáticamente al ser registradas, "
            "sin pasar por aprobación."
        )

    # ── Listas de Residentes (APROBADOR_1) y Aprobadores (APROBADOR_2) ──
    lista_ap1 = proceso.get("lista_aprobador_1") or []
    lista_ap2 = proceso.get("lista_aprobador_2") or []

    lines.append("")
    lines.append("# SELECCIÓN DE RESIDENTE Y APROBADOR AL CREAR SOLICITUD")
    lines.append(
        "Al crear una solicitud de caja chica, DEBES pedir al usuario que elija Residente y Aprobador:"
    )
    lines.append("")
    lines.append("RESIDENTE (campo opcional — APROBADOR_1):")
    lines.append("- Pregunta si la solicitud requiere la revisión de un Residente (en algunos casos no aplica).")
    lines.append("- Si el usuario dice que sí, preséntale SOLO estos nombres y pídele que elija uno:")
    if lista_ap1:
        for a in lista_ap1:
            lines.append(f"  • {a['nombre']} (id interno: {a['id']})")
    else:
        lines.append("  (No hay residentes configurados aún.)")
    lines.append("- Usa el id interno del elegido como valor del parámetro `residente_id` en la tool.")
    lines.append("- Si el usuario dice que no aplica, omite el parámetro `residente_id`.")
    lines.append("")
    lines.append("APROBADOR (campo obligatorio — APROBADOR_2):")
    lines.append("- Siempre debes pedir que elija un Aprobador. Preséntale SOLO estos nombres:")
    if lista_ap2:
        for a in lista_ap2:
            lines.append(f"  • {a['nombre']} (id interno: {a['id']})")
    else:
        lines.append("  (No hay aprobadores configurados aún.)")
    lines.append("- Usa el id interno del elegido como valor del parámetro `aprobador_id` en la tool.")


    lines.extend([
        "",
        "# COMPORTAMIENTO",
        "- Responde siempre en español, conciso, tono profesional.",
        "- Nunca inventes datos. Si no encuentras un registro, dilo claramente.",
        "- Para consultar el estado de solicitudes/rendiciones/pagos, usa las tools `consultar_*`.",
        "- Para crear o registrar algo, primero confirma los datos con el usuario en lenguaje natural, luego llama la tool.",
        "- Si el usuario excede un tope o plazo, NO rechaces. Explica el límite y sugiere alternativas concretas.",
        "- Para llevar al usuario a una pantalla, usa `navegar_ui`. No le digas \"haz click aquí\".",
        "- Si pregunta por un módulo no habilitado, indica que no está disponible.",
        "- IMPORTANTE: Cuando necesites pedir varios datos obligatorios (ej. para crear una solicitud), NO pidas todos los campos de golpe. Pídelos de forma conversacional y natural, preguntando máximo 1 o 2 cosas a la vez.",
        "",
        "# MANEJO DE ARCHIVOS ADJUNTOS",
        "Cuando el usuario adjunta un archivo (foto, PDF, Excel, Word), el sistema ya lo procesa automáticamente y te entrega los datos extraídos en formato:",
        "  [Datos extraídos del archivo adjunto:",
        "    - campo: valor",
        "    ...]",
        "REGLAS OBLIGATORIAS al recibir datos de un archivo:",
        "1. Trata esos datos como CONFIRMADOS por el usuario. NO vuelvas a preguntar por ellos.",
        "2. Presenta un resumen de los datos encontrados y pregunta SOLO por los campos que FALTEN.",
        "3. Si todos los campos requeridos están presentes, muestra el resumen completo y pide confirmación final ('¿Confirmas que cree la solicitud con estos datos?').",
        "4. Si algún campo fue extraído con incertidumbre (valor inusual), puedes mencionarlo pero no re-preguntar todos.",
    ])

    return "\n".join(lines)


def build_tools_list(config: dict) -> list[dict]:
    """
    Devuelve la lista de tools en el formato que espera la API de OpenAI
    (`client.chat.completions.create(tools=...)`).

    Side-effect importante: importar este módulo (vía la rama abajo)
    triggerea el `@register` de cada handler. Así garantizamos que el
    registry esté poblado sin que el caller tenga que importar las tools
    manualmente.
    """
    # Imports locales para que (a) el side-effect del decorador corra al
    # menos una vez y (b) no haya importaciones circulares al cargar.
    from . import tool_registry
    from .tools import consulta, accion, navegacion  # noqa: F401

    modules = (config.get("empresa") or {}).get("modules", []) if config else []
    return tool_registry.get_openai_tools_array(modules)
