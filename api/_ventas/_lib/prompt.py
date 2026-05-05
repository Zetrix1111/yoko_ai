"""
Prompt builder del agente de ventas (WhatsApp via bot-baileys).

System prompt en 8 capas:
  1. Identidad y cliente actual         (siempre)
  2. Sobre la empresa                   (condicional, info_extendida)
  3. Cómo comunicarte                   (condicional, estilo + nombre vendedor)
  4. Catálogo y herramientas            (siempre)
  5. Reglas operativas                  (condicional)
  6. Cliente objetivo y derivación      (condicional)
  7. Conocimiento adicional             (condicional, info_adicional)
  8. Comportamiento y formato           (siempre)

`_campo_activo`, `_format_redes`, `_build_sobre_empresa_block` y
`REDES_LABELS` están duplicados acá y en `api/yoko/_lib/prompt.py` a
propósito (los dos cerebros podrían divergir en el futuro).
"""

from datetime import date


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
# Constantes específicas de ventas
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


# ─────────────────────────────────────────────────────────────────────────
# Helpers de info_extendida (duplicados con yoko/_lib/prompt.py)
# ─────────────────────────────────────────────────────────────────────────

def _campo_activo(campo: dict | None) -> bool:
    """True solo si el toggle está prendido Y el valor no es vacío."""
    if not campo or not campo.get("activo"):
        return False
    valor = campo.get("valor")
    if valor in (None, ""):
        return False
    if isinstance(valor, (list, dict)) and not valor:
        return False
    return True


def _format_redes(redes_valor: list) -> str:
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
# 11 helpers de bloques de ventas
# Cada uno: standalone devuelve ["", "# HEADER", contenido...] o [].
# La línea-etiqueta `**Foo:**` en el contenido sobrevive al strip header
# cuando se agrupan bajo un header de capa.
# ─────────────────────────────────────────────────────────────────────────

def _build_estilo_block(ventas: dict) -> list[str]:
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
# Wrappers de capas (paso 7 — agrupan helpers bajo header común)
# ─────────────────────────────────────────────────────────────────────────

def _strip_inner_header(block: list[str]) -> list[str]:
    """
    Elimina el header `# XYZ` y la línea en blanco que lo precede de un
    sub-bloque. Usado por los wrappers de capa para evitar headers anidados.
    """
    if not block:
        return []
    out = list(block)
    while out and out[0] == "":
        out.pop(0)
    if out and out[0].startswith("#"):
        out.pop(0)
    return out


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
            out.append("")
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


# ─────────────────────────────────────────────────────────────────────────
# Helper de catálogo
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
    return f"- [{rec_id}] {nombre} — S/ {precio_f:,.2f} ({estado_label})"


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def build_prompt(config: dict, ctx: dict) -> str:
    """
    Construye el system prompt del agente de ventas en 8 capas. Va de lo
    más estable (identidad) a lo más volátil (FAQs/promos) para que el
    LLM "ancle" en quién es antes de absorber reglas variables.

    `ctx`:
      • productos: list de dicts del catálogo
      • sender:    {nombre, phone} del cliente WhatsApp actual
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
