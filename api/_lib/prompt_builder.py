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

from datetime import date

# Mapeo id de módulo → nombre legible para el LLM.
# Si un id no está acá, se usa un fallback titlecased.
MODULE_NAMES = {
    "alerta-segura":         "Notificaciones y Alertas",
    "gestion-caja":          "Gestión de Caja Chica",
    "facturas-inteligentes": "Facturas Inteligentes",
    "configuracion-empresa": "Configuración de Empresa",
}

# Labels visibles para los IDs de redes sociales en empresa.info_extendida.
REDES_LABELS = {
    "instagram": "Instagram",
    "facebook":  "Facebook",
    "linkedin":  "LinkedIn",
    "tiktok":    "TikTok",
    "whatsapp":  "WhatsApp",
    "youtube":   "YouTube",
    "otro":      "Otro",
}

# ─────────────────────────────────────────────────────────────────────────
# Constantes para el bloque ventas
# ─────────────────────────────────────────────────────────────────────────

ESTILO_INSTRUCCIONES = {
    "formal_profesional": "Tratá al cliente de **usted**. Vocabulario profesional y corporativo, sin modismos.",
    "cercano_amigable":   "Tratá al cliente de **tú**. Tono conversacional y cálido.",
    "tecnico_consultivo": "Tratá al cliente de **usted**. Vocabulario técnico cuando aplique, pero explicá los términos si detectás que el cliente no es del rubro.",
    "casual_directo":     "Tratá al cliente de **tú**. Mensajes muy cortos y directos, sin rodeos.",
}

TIPO_CLIENTE_INSTRUCCIONES = {
    "b2b":   "Vendés principalmente a empresas. Al cerrar, pedí RUC y razón social.",
    "b2c":   "Vendés a consumidores finales. Al cerrar, pedí DNI.",
    "mixto": "Atendés tanto empresas como personas. Al cerrar, preguntá si necesita factura (empresa, pedí RUC) o boleta (persona, pedí DNI).",
}

IGV_FRASES = {
    "incluido":    "ya incluyen IGV",
    "no_incluido": "NO incluyen IGV (se agrega al final)",
    "referencial": "son referenciales — el precio final se confirma en cotización formal",
}

COMPROBANTES_FRASES = {
    "boleta":  "solo boleta",
    "factura": "solo factura",
    "ambos":   "boleta o factura según el tipo de cliente",
}

METODOS_PAGO_LABELS = {
    "efectivo":            "Efectivo",
    "yape_plin":           "Yape / Plin",
    "transferencia":       "Transferencia bancaria",
    "tarjeta_pos":         "Tarjeta (POS presencial)",
    "tarjeta_online":      "Tarjeta online",
    "credito_empresarial": "Crédito empresarial (30/60/90 días)",
    "contra_entrega":      "Contra-entrega",
}

CRITERIOS_DERIVACION_LABELS = {
    "cotizacion_formal":     "Pide cotización formal o factura proforma",
    "descuento_negociacion": "Pide descuento especial o negociación",
    "modificar_pedido":      "Quiere modificar o cancelar un pedido en curso",
    "queja_reclamo":         "Expresa queja, reclamo o tono molesto",
    "fuera_catalogo":        "Pide algo que no figura en el catálogo",
    "menciona_competencia":  "Menciona competencia o compara precios",
    "intencion_compra":      "Confirma intención clara de compra",
    "conversacion_larga":    "La conversación supera 10 mensajes sin avanzar",
}

INFO_ADICIONAL_PREFIJOS = {
    "faq":                "[FAQ]",
    "promocion":          "[Promoción]",
    "servicio_adicional": "[Servicio adicional]",
    "info_importante":    "[Información importante]",
    "politica":           "[Política]",
}


def _campo_activo(campo: dict | None) -> bool:
    """
    True solo si el toggle está prendido Y el valor no es vacío.

    Casos que cuentan como "vacío" → False:
      • valor None
      • string ""
      • list []
      • dict {}
    """
    if not campo or not campo.get("activo"):
        return False
    valor = campo.get("valor")
    if valor in (None, ""):
        return False
    if isinstance(valor, (list, dict)) and not valor:
        return False
    return True


def _format_redes(redes_valor: list) -> str:
    """Renderiza redes_sociales.valor como 'Instagram (url), Facebook (url)'."""
    if not isinstance(redes_valor, list):
        return ""
    items = []
    for r in redes_valor:
        if not isinstance(r, dict):
            continue
        red_id = r.get("red")
        url = r.get("url")
        if not red_id or not url:
            continue
        label = REDES_LABELS.get(red_id, red_id.title())
        items.append(f"{label} ({url})")
    return ", ".join(items)


def _build_sobre_empresa_block(info_extendida: dict | None) -> list[str]:
    """
    Devuelve las líneas del bloque '# SOBRE LA EMPRESA'.
    Si NINGÚN campo está activo, devuelve [] → caller no imprime nada.

    Orden de los campos en el output (estable):
      rubro, descripcion, direccion, email_contacto, horario_atencion, redes_sociales.
    """
    if not isinstance(info_extendida, dict):
        return []

    lines: list[str] = []
    rubro = info_extendida.get("rubro")
    desc = info_extendida.get("descripcion")
    direc = info_extendida.get("direccion")
    email = info_extendida.get("email_contacto")
    horario = info_extendida.get("horario_atencion")
    redes = info_extendida.get("redes_sociales")

    if _campo_activo(rubro):
        lines.append(f"- Rubro: {rubro['valor']}")
    if _campo_activo(desc):
        lines.append(f"- Descripción: {desc['valor']}")
    if _campo_activo(direc):
        lines.append(f"- Dirección: {direc['valor']}")
    if _campo_activo(email):
        lines.append(f"- Email de contacto: {email['valor']}")
    if _campo_activo(horario):
        lines.append(f"- Horario de atención: {horario['valor']}")
    if _campo_activo(redes):
        rendered = _format_redes(redes["valor"])
        if rendered:
            lines.append(f"- Redes: {rendered}")

    if not lines:
        return []
    return ["", "# SOBRE LA EMPRESA", *lines]


# ─────────────────────────────────────────────────────────────────────────
# Bloques del prompt de ventas (config.ventas.*)
# Cada helper devuelve list[str] con las líneas del bloque (incluyendo "" y header)
# o [] si el bloque debe omitirse por completo.
# ─────────────────────────────────────────────────────────────────────────

def _build_estilo_block(ventas: dict) -> list[str]:
    """
    Estándalone devuelve `["", "# ESTILO DE COMUNICACIÓN", "**Tono...** ...]`.
    El prefijo `**Tono y tratamiento:**` está en el contenido, NO en el header,
    para que sobreviva al strip cuando se agrupa bajo "# CÓMO COMUNICARTE".
    """
    campo = ventas.get("estilo_vendedor")
    if not _campo_activo(campo):
        return []
    instr = ESTILO_INSTRUCCIONES.get(campo["valor"])
    if not instr:
        return []
    return ["", "# ESTILO DE COMUNICACIÓN", f"**Tono y tratamiento:** {instr}"]


def _build_identidad_vendedor_block(ventas: dict, razon_social: str) -> list[str]:
    campo = ventas.get("nombre_vendedor")
    if not _campo_activo(campo):
        return []
    nombre = str(campo["valor"]).strip()
    if not nombre:
        return []
    return [
        "",
        "# IDENTIDAD DEL VENDEDOR",
        f"**Tu nombre:** Te llamás {nombre} y representás a {razon_social}. Presentate por nombre solo en el primer mensaje, no en cada respuesta.",
    ]


def _build_cliente_objetivo_block(ventas: dict) -> list[str]:
    campo = ventas.get("tipo_cliente")
    if not _campo_activo(campo):
        return []
    instr = TIPO_CLIENTE_INSTRUCCIONES.get(campo["valor"])
    if not instr:
        return []
    return ["", "# CLIENTE OBJETIVO", f"**Tipo de cliente:** {instr}"]


def _build_cobertura_block(ventas: dict) -> list[str]:
    campo = ventas.get("zona_cobertura")
    if not _campo_activo(campo):
        return []
    return [
        "",
        "# COBERTURA",
        f"**Zona de cobertura:** Atendemos en {campo['valor']}. "
        "Si el cliente está fuera de esta zona, decílo con claridad y derivá al asesor humano.",
    ]


def _build_tiempos_entrega_block(ventas: dict) -> list[str]:
    campo = ventas.get("tiempo_entrega")
    if not _campo_activo(campo):
        return []
    return [
        "",
        "# TIEMPOS DE ENTREGA / RESPUESTA",
        f"**Plazos:** {campo['valor']}",
        "No prometás plazos distintos a los indicados.",
    ]


def _build_metodos_pago_block(ventas: dict) -> list[str]:
    campo = ventas.get("metodos_pago")
    if not _campo_activo(campo):
        return []
    valores = campo.get("valor") or []
    if not isinstance(valores, list):
        return []
    items = [METODOS_PAGO_LABELS[v] for v in valores if v in METODOS_PAGO_LABELS]
    if not items:
        return []
    lines = ["", "# MÉTODOS DE PAGO ACEPTADOS", "**Métodos de pago aceptados:**"]
    lines.extend(f"- {it}" for it in items)
    lines.append(
        "Cuando el cliente confirme la compra, mencioná estos métodos. "
        "Las cuentas bancarias específicas las coordina el asesor humano."
    )
    return lines


def _build_precios_block(ventas: dict) -> list[str]:
    campo = ventas.get("politica_precios")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []
    igv = valor.get("igv")
    comprobantes = valor.get("comprobantes")
    igv_frase = IGV_FRASES.get(igv)
    comp_frase = COMPROBANTES_FRASES.get(comprobantes)
    if not igv_frase and not comp_frase:
        return []
    partes = []
    if igv_frase:
        partes.append(f"Los precios del catálogo {igv_frase}.")
    if comp_frase:
        partes.append(f"Comprobantes que emitimos: {comp_frase}.")
    return [
        "",
        "# PRECIOS Y COMPROBANTES",
        f"**Precios y comprobantes:** {' '.join(partes)}",
        "Al cierre, pedí los datos correspondientes (RUC + razón social para factura, DNI para boleta).",
    ]


def _build_derivacion_block(ventas: dict) -> list[str]:
    asesor = ventas.get("asesor_humano")
    criterios = ventas.get("criterios_derivacion")

    asesor_on = _campo_activo(asesor)
    asesor_valor = (asesor or {}).get("valor") or {}
    asesor_nombre = (asesor_valor.get("nombre") or "").strip() if isinstance(asesor_valor, dict) else ""
    asesor_telefono = (asesor_valor.get("telefono") or "").strip() if isinstance(asesor_valor, dict) else ""
    asesor_renderable = asesor_on and (asesor_nombre or asesor_telefono)

    criterios_on = _campo_activo(criterios)
    criterios_valor = (criterios or {}).get("valor") or []
    criterios_render = [
        CRITERIOS_DERIVACION_LABELS[c]
        for c in (criterios_valor if isinstance(criterios_valor, list) else [])
        if c in CRITERIOS_DERIVACION_LABELS
    ]
    criterios_renderable = criterios_on and bool(criterios_render)

    if not asesor_renderable and not criterios_renderable:
        return []

    # La línea-etiqueta "**Derivación a humano:**" sobrevive al strip del header
    # cuando este bloque se agrupa bajo "# CLIENTE OBJETIVO Y DERIVACIÓN".
    lines = ["", "# DERIVACIÓN A HUMANO", "**Derivación a humano:**"]
    if asesor_renderable:
        partes = []
        if asesor_nombre:
            partes.append(asesor_nombre)
        if asesor_telefono:
            partes.append(f"({asesor_telefono})")
        head = " ".join(partes) if partes else "el asesor humano"
        lines.append(f"El asesor humano disponible es {head}. Mencionalo por nombre cuando derivés.")

    if criterios_renderable:
        lines.append("Derivá al asesor humano cuando se dé cualquiera de estos casos:")
        lines.extend(f"  - {c}" for c in criterios_render)

    cierre_nombre = asesor_nombre if asesor_renderable and asesor_nombre else "un asesor humano"
    lines.append(f'Mensaje de derivación sugerido: "Te paso con {cierre_nombre} para que te ayude con esto."')
    return lines


def _build_horario_ia_block(ventas: dict, info_extendida: dict | None) -> list[str]:
    campo = ventas.get("horario_ia")
    if not campo or not campo.get("activo"):
        return []
    if campo.get("valor") != "solo_horario_atencion":
        return []
    horario = "horario de oficina"
    if isinstance(info_extendida, dict):
        ha = info_extendida.get("horario_atencion")
        if _campo_activo(ha):
            horario = ha["valor"]
    return [
        "",
        "# HORARIO DE LA IA",
        f"**Horario de la IA:** Solo respondés en el horario de atención de la empresa: {horario}.",
        'Fuera de ese horario, respondé: "Hola, recibimos tu mensaje. Te respondemos en horario de atención."',
    ]


def _strip_inner_header(block: list[str]) -> list[str]:
    """
    Elimina el header `# XYZ` y la línea en blanco que lo precede de un
    sub-bloque, dejando solo el contenido. Usado por los wrappers de capa
    cuando agrupan varios sub-bloques bajo un header común y no queremos
    headers anidados.

    Si el bloque no tiene header (p. ej. ya fue stripped), lo devuelve tal cual.
    """
    if not block:
        return []
    out = list(block)
    # Quitar líneas en blanco iniciales
    while out and out[0] == "":
        out.pop(0)
    # Quitar el header (si la primera línea empieza con "#")
    if out and out[0].startswith("#"):
        out.pop(0)
    return out


# ─────────────────────────────────────────────────────────────────────────
# Wrappers de capa para el prompt de ventas (paso 7)
# Agrupan sub-bloques bajo un header de capa y eliminan los headers
# internos de los sub-bloques. Cada wrapper devuelve [] si NINGÚN
# sub-bloque tiene contenido.
# ─────────────────────────────────────────────────────────────────────────

def _build_capa_comunicacion(ventas: dict, razon_social: str) -> list[str]:
    """Capa 3: cómo comunicarte. Agrupa estilo + identidad del vendedor."""
    estilo = _build_estilo_block(ventas)
    identidad = _build_identidad_vendedor_block(ventas, razon_social)

    sub_bloques = [b for b in (estilo, identidad) if b]
    if not sub_bloques:
        return []

    out = ["", "# CÓMO COMUNICARTE"]
    for sb in sub_bloques:
        out.extend(_strip_inner_header(sb))
    return out


def _build_capa_reglas_operativas(ventas: dict) -> list[str]:
    """Capa 5: reglas operativas. Cobertura + tiempos + métodos de pago + precios."""
    cobertura = _build_cobertura_block(ventas)
    tiempos   = _build_tiempos_entrega_block(ventas)
    pagos     = _build_metodos_pago_block(ventas)
    precios   = _build_precios_block(ventas)

    sub_bloques = [b for b in (cobertura, tiempos, pagos, precios) if b]
    if not sub_bloques:
        return []

    out = ["", "# REGLAS OPERATIVAS"]
    for i, sb in enumerate(sub_bloques):
        if i > 0:
            out.append("")  # separador visual entre sub-bloques
        out.extend(_strip_inner_header(sb))
    return out


def _build_capa_cliente_y_derivacion(ventas: dict, info_extendida: dict | None) -> list[str]:
    """Capa 6: cliente objetivo + derivación a humano + horario de la IA."""
    cliente_obj = _build_cliente_objetivo_block(ventas)
    derivacion  = _build_derivacion_block(ventas)
    horario     = _build_horario_ia_block(ventas, info_extendida)

    sub_bloques = [b for b in (cliente_obj, derivacion, horario) if b]
    if not sub_bloques:
        return []

    out = ["", "# CLIENTE OBJETIVO Y DERIVACIÓN"]
    for i, sb in enumerate(sub_bloques):
        if i > 0:
            out.append("")
        out.extend(_strip_inner_header(sb))
    return out


def _build_info_adicional_block(ventas: dict) -> list[str]:
    campo = ventas.get("info_adicional")
    if not _campo_activo(campo):
        return []
    entradas = campo.get("valor") or []
    if not isinstance(entradas, list):
        return []

    hoy = date.today().isoformat()
    items: list[str] = []
    for e in entradas:
        if not isinstance(e, dict):
            continue
        cat = e.get("categoria")
        titulo = (e.get("titulo") or "").strip()
        respuesta = (e.get("respuesta") or "").strip()
        if not cat or not titulo or not respuesta:
            continue
        prefijo = INFO_ADICIONAL_PREFIJOS.get(cat)
        if not prefijo:
            continue
        # Filtrar promociones vencidas
        vfin = e.get("vigencia_fin")
        if isinstance(vfin, str) and vfin and vfin < hoy:
            continue
        items.append(f"{prefijo} {titulo} → {respuesta}")

    if not items:
        return []
    return [
        "",
        "# INFORMACIÓN ADICIONAL",
        "Conocimiento que podés usar para responder. Aplicá la entrada cuando el contexto coincida con el título.",
        "",
        *items,
    ]


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
    Prompt del agente de ventas (WhatsApp via bot-baileys), estructurado en 8 capas:

      1. Identidad y cliente actual         (siempre)
      2. Sobre la empresa                   (condicional, info_extendida)
      3. Cómo comunicarte                   (condicional, estilo + nombre vendedor)
      4. Catálogo y herramientas            (siempre)
      5. Reglas operativas                  (condicional, cobertura/tiempos/pagos/precios)
      6. Cliente objetivo y derivación      (condicional, tipo cliente/asesor/criterios/horario)
      7. Conocimiento adicional             (condicional, info_adicional)
      8. Comportamiento y formato           (siempre)

    El orden va de lo más estable (identidad) a lo más volátil (FAQs/promos)
    para que el LLM "ancle" en quién es antes de absorber reglas variables.
    """
    empresa = (config or {}).get("empresa", {}) or {}
    ventas = (config or {}).get("ventas", {}) or {}
    info_extendida = empresa.get("info_extendida") or {}
    razon_social = empresa.get("razon_social") or empresa.get("id") or "la empresa"
    ruc = empresa.get("ruc") or ""

    productos = ctx.get("productos") or []
    sender = ctx.get("sender") or {}
    sender_nombre = sender.get("nombre") or "el cliente"
    sender_phone = sender.get("phone") or ""

    lines: list[str] = []

    # ── CAPA 1: Identidad y cliente actual (siempre) ──
    identidad = f"Eres un vendedor virtual de {razon_social}"
    if ruc:
        identidad += f" (RUC {ruc})"
    identidad += "."
    lines.extend([
        identidad,
        "Estás respondiendo conversaciones de WhatsApp con clientes potenciales.",
        "Tu objetivo: ayudar al cliente a encontrar el producto que necesita y darle "
        "información clara y precisa para que pueda decidir comprar.",
        "",
        "# CLIENTE ACTUAL",
        f"- Nombre (pushname WhatsApp): {sender_nombre}",
        f"- Teléfono: {sender_phone or '—'}",
    ])

    # ── CAPA 2: Sobre la empresa (condicional) ──
    lines.extend(_build_sobre_empresa_block(info_extendida))

    # ── CAPA 3: Cómo comunicarte (condicional, agrupada) ──
    lines.extend(_build_capa_comunicacion(ventas, razon_social))

    # ── CAPA 4: Catálogo y herramientas (siempre) ──
    lines.extend([
        "",
        "# CATÁLOGO DISPONIBLE",
        f"({len(productos)} productos/servicios activos del catálogo)",
        "",
    ])
    if productos:
        for p in productos:
            lines.append(_format_producto_inline(p))
    else:
        lines.append("(No hay productos cargados aún en el catálogo.)")

    lines.extend([
        "",
        "## HERRAMIENTAS DEL CATÁLOGO",
        "- `consultar_productos(query?, solo_disponibles?, categoria?)` → "
        "búsqueda más detallada en el catálogo. Úsala si necesitás más info que la "
        "del listado de arriba (descripción completa, keywords, foto).",
        "- `consultar_stock(producto_id | nombre)` → stock exacto de un producto.",
    ])

    # ── CAPA 5: Reglas operativas (condicional, agrupada) ──
    lines.extend(_build_capa_reglas_operativas(ventas))

    # ── CAPA 6: Cliente objetivo y derivación (condicional, agrupada) ──
    lines.extend(_build_capa_cliente_y_derivacion(ventas, info_extendida))

    # ── CAPA 7: Conocimiento adicional (condicional) ──
    lines.extend(_build_info_adicional_block(ventas))

    # ── CAPA 8: Comportamiento y formato (siempre) ──
    lines.extend([
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
        "7. NO uses emojis. NO uses markdown (**, *, #) en tus respuestas. El cliente "
        "lo lee en WhatsApp. Los `**` que ves arriba son solo etiquetas para que vos "
        "identifiques cada sub-sección — NO los copies en tu respuesta.",
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
    ]

    # # SOBRE LA EMPRESA — solo si al menos un campo de info_extendida está activo.
    # Si todos los toggles están en false (default), esta sección no aparece y
    # el prompt queda byte-idéntico al previo a esta feature.
    sobre_empresa = _build_sobre_empresa_block(empresa.get("info_extendida"))
    if sobre_empresa:
        lines.extend(sobre_empresa)

    lines.extend([
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
    ])

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
