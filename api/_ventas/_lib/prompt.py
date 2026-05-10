"""
Prompt builder del agente de ventas (WhatsApp via bot-baileys).

System prompt en 10 capas (v2):
  1. Identidad y contexto                  (siempre)
  2. Sobre la empresa                      (condicional, info_extendida)
  3. Voz del vendedor                      (siempre, fallback default_neutro)
  4. Catálogo y herramientas               (siempre)
  5. Reglas de recomendación               (condicional)   ← NUEVA capa
  6. Política comercial                    (condicional)
  7. Cliente y arco conversacional         (condicional)
  8. Conocimiento de marca                 (condicional)
  9. Manejo de objeciones                  (condicional)
 10. Límites y prohibiciones               (siempre, con universales hardcodeadas)

Notas clave:
  - Las prohibiciones universales (PROHIBICIONES_UNIVERSALES) SIEMPRE aparecen
    en la capa 10. El campo `prohibiciones` del schema solo AÑADE específicas
    del cliente; no puede quitar ni reemplazar las universales.
  - Capa 3 emite siempre. Si TODOS los sub-campos están en activo:false, se
    aplica VOZ_DEFAULT_NEUTRO como fallback.
  - La capa 5 (REGLAS DE RECOMENDACIÓN) es nueva en v2: fuerza al agente a
    completar discovery antes de recomendar productos.
  - Las instrucciones internas al LLM están en español neutro (no voseo),
    aunque el cliente puede pedir voseo como ESTILO de habla del agente.
  - `_campo_activo`, `_format_redes`, `_build_sobre_empresa_block` y
    `REDES_LABELS` están duplicados acá y en `api/_yoko/_lib/prompt.py` a
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
# Constantes — capa 3 (voz del vendedor)
# ─────────────────────────────────────────────────────────────────────────

TRATAMIENTO_INSTRUCCIONES = {
    "tu":                    "Trata al cliente de tú.",
    "vos":                   "Trata al cliente de vos.",
    "usted":                 "Trata al cliente de usted.",
    "mixto_segun_cliente":   "Adapta tú/usted según cómo te trate el cliente. Si te trata de tú, responde de tú. Si te trata de usted, responde de usted.",
}

VOCABULARIO_INSTRUCCIONES = {
    "tecnico":     "Vocabulario técnico cuando aplique. Si detectas que el cliente no es del rubro, explica los términos.",
    "neutro":      "Vocabulario neutro, claro. Evita tecnicismos innecesarios.",
    "coloquial":   "Vocabulario conversacional, cercano. Puedes usar expresiones cotidianas.",
    "corporativo": "Vocabulario profesional y corporativo. Sin modismos.",
}

CALIDEZ_INSTRUCCIONES = {
    "calida_cercana":      "Tono cálido y cercano. Muestra interés genuino por el cliente, no solo por la venta.",
    "cordial":             "Tono cordial y respetuoso. Profesional sin ser frío.",
    "neutra_profesional":  "Tono profesional y neutral. Foco en información clara.",
    "directa_seca":        "Tono directo, sin rodeos. Mensajes cortos y al punto.",
}

EMOJIS_INSTRUCCIONES = {
    "nunca":                  "NO uses emojis bajo ninguna circunstancia.",
    "ocasional_solo_calidez": "Puedes usar 1 emoji ocasional para transmitir calidez (👋 al saludar, ✅ al confirmar). Máximo 1 por mensaje. Nunca decorativos.",
    "frecuente_tematico":     "Usa emojis con frecuencia para reforzar el mensaje, siempre temáticos del producto/contexto. Máximo 2-3 por mensaje, nunca decorativos en exceso.",
}

LONGITUD_INSTRUCCIONES = {
    "muy_corto": "1-2 líneas por mensaje, máximo 30 palabras.",
    "corto":     "2-4 líneas por mensaje, máximo 60 palabras.",
    "medio":     "4-8 líneas por mensaje cuando se justifique, hasta 120 palabras.",
    "extenso":   "Permitido hasta 200 palabras cuando el contenido lo amerita (explicaciones técnicas, comparaciones).",
}

USO_LISTAS_INSTRUCCIONES = {
    "nunca":            "NO uses listas ni viñetas. Todo en prosa natural.",
    "solo_si_3_o_mas":  "Usa listas (con guiones, NO con asteriscos) solo cuando enumeres 3 o más ítems. Para 1-2 ítems, prosa natural.",
    "frecuente":        "Puedes usar listas con frecuencia para estructurar info.",
}

REGION_INSTRUCCIONES = {
    "peru":         "Usa español de Perú. Modismos peruanos permitidos según campo `modismos_permitidos`.",
    "neutro_latam": "Usa español neutro latinoamericano. Sin modismos regionales.",
    "mexico":       "Usa español de México.",
    "argentina":    "Usa español rioplatense con voseo.",
    "espana":       "Usa español de España (vosotros, modismos peninsulares).",
}

VOZ_DEFAULT_NEUTRO = (
    "Trata al cliente de tú. Vocabulario neutro, claro. Tono cordial. "
    "Mensajes cortos (2-4 líneas, máximo 60 palabras). Una pregunta por turno. "
    "Sin emojis. Sin signos de puntuación enfáticos."
)


# ─────────────────────────────────────────────────────────────────────────
# Constantes — capa 6 (política comercial)
# ─────────────────────────────────────────────────────────────────────────

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

MONEDA_LABELS = {
    "PEN":   "Soles peruanos (S/)",
    "USD":   "Dólares americanos (US$)",
    "EUR":   "Euros (€)",
    "multi": "Múltiples monedas — confirma con el cliente cuál prefiere",
}

MODELO_ENVIO_INSTRUCCIONES = {
    "gratis":                "El envío es GRATIS para todos los pedidos.",
    "fijo":                  "Tenemos costo fijo de envío. Menciónalo cuando el cliente pregunte.",
    "por_distrito":          "El costo de envío varía por distrito. Pide el distrito y deriva al humano si no lo conoces.",
    "calculado_caso_a_caso": "El costo de envío se cotiza caso por caso. NO inventes montos ni confirmes fechas. Si preguntan, di que el asesor humano lo confirma.",
}


# ─────────────────────────────────────────────────────────────────────────
# Constantes — capa 7 (cliente y arco)
# ─────────────────────────────────────────────────────────────────────────

TIPO_CLIENTE_INSTRUCCIONES = {
    "b2b":   "Vendes principalmente a empresas. Al cerrar, pide RUC y razón social.",
    "b2c":   "Vendes a consumidores finales. Al cerrar, pide DNI.",
    "mixto": "Atiendes tanto empresas como personas. Al cerrar, pregunta si necesita factura (empresa, pide RUC) o boleta (persona, pide DNI).",
}

DATOS_CIERRE_LABELS = {
    "nombre":       "nombre completo",
    "telefono":     "número de teléfono",
    "email":        "correo electrónico",
    "direccion":    "dirección de entrega",
    "ruc":          "RUC",
    "razon_social": "razón social",
    "dni":          "DNI",
    "metodo_pago":  "método de pago preferido",
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


# ─────────────────────────────────────────────────────────────────────────
# Constantes — capa 10 (límites y prohibiciones)
# ⚠️ v2: Reforzadas para evitar que el agente confirme stock numérico,
# concatene preguntas, o recomiende antes de hacer discovery.
# ─────────────────────────────────────────────────────────────────────────

PROHIBICIONES_UNIVERSALES = [
    # — Bloque CRÍTICO: invención de datos —
    "Nunca inventes precios, plazos, características o promociones que no estén en este prompt o en el catálogo.",

    # — Bloque CRÍTICO: stock —
    "NUNCA confirmes cantidades específicas de stock (ej: 'tenemos 50 unidades', 'hay stock para 20', 'quedan X'). "
    "Las tools devuelven solo disponibilidad (disponible/bajo_stock/sin_stock), NO números. "
    "Si hay disponibilidad, di: 'tenemos disponibilidad, déjame confirmar la cantidad exacta con el equipo y te aviso en breve'. "
    "Si está agotado, di: 'ese producto está agotado, te ofrezco una alternativa similar'. "
    "La cantidad real SIEMPRE la confirma el asesor humano.",

    # — Bloque CRÍTICO: fechas y compromisos —
    "NUNCA confirmes una fecha de entrega específica (ej: 'mañana', 'el lunes', 'a las 3pm'). "
    "Solo menciona los plazos generales del catálogo (ej: '24 a 48 horas en Lima'). "
    "La fecha y hora exacta de entrega la confirma SIEMPRE el asesor humano.",

    "NUNCA confirmes un costo de envío específico cuando la política es 'calculado_caso_a_caso' o 'por_distrito'. "
    "Deriva al asesor humano para que confirme el costo.",

    # — Bloque CRÍTICO: formato de mensaje —
    "NUNCA hagas más de UNA pregunta por mensaje. NO concatenes preguntas con 'y' u 'o' "
    "(ej: '¿confirmas stock y precio?' está PROHIBIDO). Una pregunta, espera respuesta, "
    "después la siguiente.",

    "NUNCA uses Markdown (**, *, #, listas con asteriscos). El cliente lee en WhatsApp y se ve mal.",

    # — Bloque CRÍTICO: secuencia de venta —
    "NUNCA recomiendes un producto específico si NO has completado las preguntas de discovery "
    "marcadas como OBLIGATORIAS. Si el cliente dice 'dame el mejor' o 'recomiéndame algo' sin contexto, "
    "responde pidiendo el contexto necesario (tipo de trabajo, riesgo, uso) ANTES de recomendar.",

    # — Bloque: límites de autoridad —
    "Nunca prometas algo que requiera autorización de un humano (descuentos especiales, créditos, devoluciones, plazos fuera de los configurados).",
    "Nunca compartas información de un cliente con otro, ni datos internos de la empresa (costos, márgenes, datos de otros pedidos).",
    "Nunca hables mal de la competencia.",
    "Nunca insistas si el cliente dijo claramente 'no' o 'lo voy a pensar'. Ofrece info por escrito y suelta.",
]


# ─────────────────────────────────────────────────────────────────────────
# Helpers de info_extendida (duplicados con _yoko/_lib/prompt.py)
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


def _strip_inner_header(block: list[str]) -> list[str]:
    """Elimina el header anidado y la línea en blanco de un sub-bloque."""
    if not block:
        return []
    out = list(block)
    while out and out[0] == "":
        out.pop(0)
    if out and out[0].startswith("#"):
        out.pop(0)
    return out


# ─────────────────────────────────────────────────────────────────────────
# CAPA 3 — Voz del vendedor (sub-builders)
# ─────────────────────────────────────────────────────────────────────────

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
        f"**Tu nombre:** Te llamas {nombre} y representas a {razon_social}. Preséntate por nombre solo en el primer mensaje, no en cada respuesta.",
    ]


def _build_tratamiento_block(ventas: dict) -> list[str]:
    campo = ventas.get("tratamiento")
    if not _campo_activo(campo):
        return []
    instr = TRATAMIENTO_INSTRUCCIONES.get(campo["valor"])
    if not instr:
        return []
    return ["", "# TRATAMIENTO", f"**Tratamiento:** {instr}"]


def _build_vocabulario_block(ventas: dict) -> list[str]:
    campo = ventas.get("vocabulario")
    if not _campo_activo(campo):
        return []
    instr = VOCABULARIO_INSTRUCCIONES.get(campo["valor"])
    if not instr:
        return []
    return ["", "# VOCABULARIO", f"**Vocabulario:** {instr}"]


def _build_calidez_block(ventas: dict) -> list[str]:
    campo = ventas.get("calidez")
    if not _campo_activo(campo):
        return []
    instr = CALIDEZ_INSTRUCCIONES.get(campo["valor"])
    if not instr:
        return []
    return ["", "# CALIDEZ", f"**Calidez:** {instr}"]


def _build_region_modismos_block(ventas: dict) -> list[str]:
    campo = ventas.get("localizacion_cultural")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []
    region = valor.get("region")
    instr = REGION_INSTRUCCIONES.get(region)
    if not instr:
        return []
    lines = ["", "# REGIÓN Y MODISMOS", f"**Región:** {instr}"]
    modismos = valor.get("modismos_permitidos")
    if isinstance(modismos, list) and modismos:
        ms = ", ".join(str(m).strip() for m in modismos if str(m).strip())
        if ms:
            lines.append(f"**Modismos permitidos:** {ms}")
    return lines


def _build_formato_mensaje_block(ventas: dict) -> list[str]:
    """
    Capa 3 — formato de mensaje.

    ⚠️ v2: Soporta el campo opcional `instruccion_estricta` para reforzar
    al modelo. Si está presente, se agrega como línea destacada al final
    del bloque.
    """
    campo = ventas.get("formato_mensaje")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []

    longitud = valor.get("longitud_preferida")
    listas = valor.get("uso_listas")
    preguntas = valor.get("preguntas_por_turno")
    enfatica = valor.get("puntuacion_enfatica")
    instruccion_estricta = (valor.get("instruccion_estricta") or "").strip()

    lines: list[str] = []
    long_instr = LONGITUD_INSTRUCCIONES.get(longitud)
    if long_instr:
        lines.append(f"**Longitud:** {long_instr}")
    listas_instr = USO_LISTAS_INSTRUCCIONES.get(listas)
    if listas_instr:
        lines.append(f"**Listas:** {listas_instr}")
    if isinstance(preguntas, int) and 1 <= preguntas <= 3:
        if preguntas == 1:
            lines.append("**Preguntas por turno:** Una sola pregunta por mensaje. NO formularios. NO concatenes preguntas con 'y' u 'o'.")
        else:
            lines.append(f"**Preguntas por turno:** Hasta {preguntas} preguntas por mensaje cuando se justifique.")
    if enfatica is True:
        lines.append("**Puntuación enfática:** Permitido usar signos de exclamación y mayúsculas para énfasis ocasional.")
    elif enfatica is False:
        lines.append("**Puntuación enfática:** Sin signos de exclamación ni mayúsculas para énfasis.")
    if instruccion_estricta:
        lines.append(f"**Instrucción estricta:** {instruccion_estricta}")

    if not lines:
        return []
    return ["", "# FORMATO DE MENSAJE", *lines]


def _build_emojis_block(ventas: dict) -> list[str]:
    campo = ventas.get("uso_emojis")
    if not _campo_activo(campo):
        return []
    instr = EMOJIS_INSTRUCCIONES.get(campo["valor"])
    if not instr:
        return []
    return ["", "# USO DE EMOJIS", f"**Emojis:** {instr}"]


# ─────────────────────────────────────────────────────────────────────────
# CAPA 5 — Reglas de recomendación (NUEVA en v2)
# ─────────────────────────────────────────────────────────────────────────

def _build_reglas_recomendacion_block(ventas: dict) -> list[str]:
    """
    Capa 5 — Reglas de recomendación.

    Fuerza al agente a seguir una secuencia explícita: discovery primero,
    recomendación después. Resuelve el bug de que el agente recomendaba
    productos antes de conocer el riesgo / tipo de trabajo del cliente.

    Estructura del campo en config:
      reglas_recomendacion: {
        activo: true,
        valor: {
          secuencia_obligatoria: [str, ...],
          nunca_recomendar_sin_saber: [str, ...]
        }
      }
    """
    campo = ventas.get("reglas_recomendacion")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []

    secuencia = valor.get("secuencia_obligatoria") or []
    nunca_sin = valor.get("nunca_recomendar_sin_saber") or []

    if not isinstance(secuencia, list):
        secuencia = []
    if not isinstance(nunca_sin, list):
        nunca_sin = []

    secuencia_clean = [str(s).strip() for s in secuencia if str(s).strip()]
    nunca_clean = [str(n).strip() for n in nunca_sin if str(n).strip()]

    if not secuencia_clean and not nunca_clean:
        return []

    lines = [
        "",
        "# REGLAS DE RECOMENDACIÓN",
        "**Secuencia obligatoria de venta.** Sigue esta lógica SIEMPRE — es la regla de oro:",
    ]

    if secuencia_clean:
        lines.extend(f"  {paso}" for paso in secuencia_clean)

    if nunca_clean:
        lines.append("")
        lines.append("**NUNCA recomiendes un producto específico sin saber:**")
        lines.extend(f"  - {req}" for req in nunca_clean)
        lines.append(
            "Si el cliente pide una recomendación 'rápida' sin darte estos datos, "
            "responde pidiendo el dato faltante antes de recomendar. "
            "Una pregunta a la vez."
        )

    return lines


# ─────────────────────────────────────────────────────────────────────────
# CAPA 6 — Política comercial (sub-builders)
# ─────────────────────────────────────────────────────────────────────────

def _build_cobertura_block(ventas: dict) -> list[str]:
    campo = ventas.get("zona_cobertura")
    if not _campo_activo(campo):
        return []
    return [
        "",
        "# COBERTURA",
        f"**Zona de cobertura:** Atendemos en {campo['valor']}. "
        "Si el cliente está fuera de esta zona, díselo con claridad y deriva al asesor humano.",
    ]


def _build_tiempos_entrega_block(ventas: dict) -> list[str]:
    campo = ventas.get("tiempo_entrega")
    if not _campo_activo(campo):
        return []
    return [
        "",
        "# TIEMPOS DE ENTREGA",
        f"**Plazos:** {campo['valor']}",
        "No prometas plazos distintos a los indicados. NUNCA confirmes una fecha específica (ej: 'mañana') — esa la confirma el asesor humano.",
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
    lines = ["", "# MÉTODOS DE PAGO", "**Métodos de pago aceptados:**"]
    lines.extend(f"- {it}" for it in items)
    lines.append(
        "Cuando el cliente confirme la compra, menciona estos métodos. "
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
    ]


def _build_moneda_block(ventas: dict) -> list[str]:
    campo = ventas.get("moneda")
    if not _campo_activo(campo):
        return []
    label = MONEDA_LABELS.get(campo["valor"])
    if not label:
        return []
    return ["", "# MONEDA", f"**Moneda:** {label}."]


def _build_envio_block(ventas: dict) -> list[str]:
    campo = ventas.get("politica_envio")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []
    modelo = valor.get("modelo")
    instr = MODELO_ENVIO_INSTRUCCIONES.get(modelo)
    if not instr:
        return []
    lines = ["", "# POLÍTICA DE ENVÍO", f"**Envío:** {instr}"]

    monto_gratis = valor.get("monto_envio_gratis_desde")
    costo_fijo = valor.get("costo_fijo")
    detalle = (valor.get("detalle_libre") or "").strip()

    if modelo == "fijo" and isinstance(costo_fijo, (int, float)) and costo_fijo > 0:
        lines.append(f"**Costo de envío:** {costo_fijo}")
    if isinstance(monto_gratis, (int, float)) and monto_gratis > 0:
        lines.append(f"**Envío gratis desde:** {monto_gratis}")
    if detalle:
        lines.append(f"**Detalle:** {detalle}")
    return lines


def _build_devoluciones_block(ventas: dict) -> list[str]:
    campo = ventas.get("politica_devoluciones")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []
    acepta = valor.get("acepta_devolucion")
    plazo = valor.get("plazo_dias")
    condiciones = (valor.get("condiciones") or "").strip()

    lines = ["", "# DEVOLUCIONES"]
    if acepta is False:
        lines.append("**Devoluciones:** NO se aceptan devoluciones.")
    else:
        partes = ["Aceptamos devoluciones"]
        if isinstance(plazo, int) and plazo > 0:
            partes.append(f"dentro de {plazo} días")
        lines.append(f"**Devoluciones:** {' '.join(partes)}.")
        if condiciones:
            lines.append(f"**Condiciones:** {condiciones}")
    return lines


def _build_garantia_block(ventas: dict) -> list[str]:
    campo = ventas.get("garantia")
    if not _campo_activo(campo):
        return []
    return ["", "# GARANTÍA", f"**Garantía:** {campo['valor']}"]


def _build_pedido_minimo_block(ventas: dict) -> list[str]:
    campo = ventas.get("pedido_minimo")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []
    monto = valor.get("monto")
    comentario = (valor.get("comentario") or "").strip()
    if not isinstance(monto, (int, float)) or monto <= 0:
        return []
    lines = ["", "# PEDIDO MÍNIMO", f"**Pedido mínimo:** {monto}"]
    if comentario:
        lines.append(comentario)
    lines.append("Por debajo de ese monto, no se procesa el pedido.")
    return lines


def _build_descuento_volumen_block(ventas: dict) -> list[str]:
    campo = ventas.get("descuento_volumen")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or {}
    if not isinstance(valor, dict):
        return []
    umbral = valor.get("umbral_aplica")
    instruccion = valor.get("instruccion")
    if not isinstance(umbral, (int, float)) or umbral <= 0:
        return []
    if instruccion == "derivar_humano":
        cuerpo = (
            f"Para pedidos sobre {umbral} aplica descuento por volumen. "
            "NO calcules ni prometas el descuento — deriva al asesor humano para que lo confirme."
        )
    elif instruccion == "porcentaje_fijo":
        cuerpo = (
            f"Para pedidos sobre {umbral} aplica descuento por volumen como porcentaje fijo. "
            "Si el cliente no recuerda el porcentaje, deriva al asesor humano."
        )
    elif instruccion == "tabla_escalonada":
        cuerpo = (
            f"Para pedidos sobre {umbral} aplica descuento escalonado por volumen. "
            "NO calcules el escalado: deriva al asesor humano para que lo confirme."
        )
    else:
        return []
    return ["", "# DESCUENTO POR VOLUMEN", f"**Descuento por volumen:** {cuerpo}"]


# ─────────────────────────────────────────────────────────────────────────
# CAPA 7 — Cliente y arco conversacional (sub-builders)
# ─────────────────────────────────────────────────────────────────────────

def _build_tipo_cliente_block(ventas: dict) -> list[str]:
    campo = ventas.get("tipo_cliente")
    if not _campo_activo(campo):
        return []
    instr = TIPO_CLIENTE_INSTRUCCIONES.get(campo["valor"])
    if not instr:
        return []
    return ["", "# TIPO DE CLIENTE", f"**Tipo de cliente:** {instr}"]


def _build_discovery_block(ventas: dict) -> list[str]:
    """
    Capa 7 — Discovery.

    ⚠️ v2: Ahora soporta el campo opcional `orden` en cada pregunta.
    Si está presente, las preguntas se ordenan por ese campo.
    Las preguntas OBLIGATORIAS se listan separadas de las opcionales
    para que el modelo entienda claramente cuáles debe hacer antes
    de recomendar.
    """
    campo = ventas.get("discovery_preguntas")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or []
    if not isinstance(valor, list):
        return []

    # Normalizar y ordenar
    preguntas_clean = []
    for q in valor:
        if not isinstance(q, dict):
            continue
        pregunta = (q.get("pregunta") or "").strip()
        if not pregunta:
            continue
        orden = q.get("orden")
        if not isinstance(orden, int):
            orden = 999  # las sin orden van al final
        preguntas_clean.append({
            "orden":       orden,
            "pregunta":    pregunta,
            "obligatoria": bool(q.get("obligatoria", False)),
        })

    if not preguntas_clean:
        return []

    preguntas_clean.sort(key=lambda x: x["orden"])

    obligatorias = [q for q in preguntas_clean if q["obligatoria"]]
    opcionales = [q for q in preguntas_clean if not q["obligatoria"]]

    lines = [
        "",
        "# DISCOVERY",
        "Antes de recomendar un producto específico, conoce al cliente. "
        "Hazlo natural, UNA pregunta por turno — NO como formulario.",
    ]

    if obligatorias:
        lines.append("")
        lines.append("**Preguntas OBLIGATORIAS (haz TODAS antes de recomendar producto):**")
        for i, q in enumerate(obligatorias, 1):
            lines.append(f"  {i}. {q['pregunta']}")

    if opcionales:
        lines.append("")
        lines.append("**Preguntas OPCIONALES (úsalas si aportan valor):**")
        for q in opcionales:
            lines.append(f"  - {q['pregunta']}")

    return lines


def _build_datos_cierre_block(ventas: dict) -> list[str]:
    campo = ventas.get("datos_cierre_obligatorios")
    if not _campo_activo(campo):
        return []
    valores = campo.get("valor") or []
    if not isinstance(valores, list):
        return []
    items = [DATOS_CIERRE_LABELS[v] for v in valores if v in DATOS_CIERRE_LABELS]
    if not items:
        return []
    return [
        "",
        "# DATOS DE CIERRE",
        f"**Datos obligatorios al cerrar:** {', '.join(items)}.",
        "Pídelos cuando el cliente confirme intención de compra. NO los pidas todos juntos al inicio. "
        "Uno por turno.",
    ]


def _build_umbral_derivacion_block(ventas: dict) -> list[str]:
    campo = ventas.get("umbral_derivacion_humano")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor")
    if not isinstance(valor, (int, float)) or valor <= 0:
        return []
    return [
        "",
        "# UMBRAL DE DERIVACIÓN",
        f"**Umbral de derivación:** Todo pedido cuyo total supere {valor} derívalo al asesor humano sin cerrar la venta.",
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
        lines.append(f"El asesor humano disponible es {head}. Menciónalo SIEMPRE por este nombre cuando derives — NO uses otros nombres.")

    if criterios_renderable:
        lines.append("Deriva al asesor humano cuando se dé cualquiera de estos casos:")
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
        f"**Horario de la IA:** Solo respondes en el horario de atención de la empresa: {horario}.",
        'Fuera de ese horario, responde: "Hola, recibimos tu mensaje. Te respondemos en horario de atención."',
    ]


# ─────────────────────────────────────────────────────────────────────────
# CAPA 8 — Conocimiento de marca (sub-builders)
# ─────────────────────────────────────────────────────────────────────────

def _build_propuesta_valor_block(ventas: dict) -> list[str]:
    campo = ventas.get("propuesta_valor")
    if not _campo_activo(campo):
        return []
    return ["", "# PROPUESTA DE VALOR", f"**Propuesta de valor:** {campo['valor']}"]


def _build_diferenciadores_block(ventas: dict) -> list[str]:
    campo = ventas.get("diferenciadores")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or []
    if not isinstance(valor, list):
        return []
    items = [str(v).strip() for v in valor if str(v).strip()]
    if not items:
        return []
    lines = ["", "# DIFERENCIADORES", "**Lo que nos diferencia:**"]
    lines.extend(f"- {it}" for it in items)
    return lines


def _build_prueba_social_block(ventas: dict) -> list[str]:
    campo = ventas.get("prueba_social")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or []
    if not isinstance(valor, list):
        return []
    items = [str(v).strip() for v in valor if str(v).strip()]
    if not items:
        return []
    lines = [
        "",
        "# PRUEBA SOCIAL",
        "Hechos verificables que puedes mencionar naturalmente cuando el contexto lo permita. "
        "NO los recites como lista. NO los uses si el cliente no preguntó nada relacionado:",
    ]
    lines.extend(f"- {it}" for it in items)
    return lines


def _build_autoridad_tecnica_block(ventas: dict) -> list[str]:
    campo = ventas.get("autoridad_tecnica")
    if not _campo_activo(campo):
        return []
    valor = campo.get("valor") or []
    if not isinstance(valor, list):
        return []
    items = [str(v).strip() for v in valor if str(v).strip()]
    if not items:
        return []
    lines = ["", "# AUTORIDAD TÉCNICA", "**Credenciales y experiencia que respaldan a la empresa:**"]
    lines.extend(f"- {it}" for it in items)
    return lines


def _build_faq_block(ventas: dict) -> list[str]:
    campo = ventas.get("faq")
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
        titulo = (e.get("titulo") or "").strip()
        respuesta = (e.get("respuesta") or "").strip()
        if not titulo or not respuesta:
            continue
        vfin = e.get("vigencia_fin")
        if isinstance(vfin, str) and vfin and vfin < hoy:
            continue
        items.append(f"- {titulo} → {respuesta}")
    if not items:
        return []
    return [
        "",
        "# FAQ",
        "Respuestas a preguntas frecuentes. Aplica la entrada cuando el contexto coincida con el título:",
        *items,
    ]


def _build_promociones_block(ventas: dict) -> list[str]:
    campo = ventas.get("promociones_activas")
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
        titulo = (e.get("titulo") or "").strip()
        respuesta = (e.get("respuesta") or "").strip()
        if not titulo or not respuesta:
            continue
        vfin = e.get("vigencia_fin")
        if isinstance(vfin, str) and vfin and vfin < hoy:
            continue
        items.append(f"- {titulo} → {respuesta}")
    if not items:
        return []
    return [
        "",
        "# PROMOCIONES ACTIVAS",
        "Promociones vigentes que puedes mencionar cuando el contexto lo permita:",
        *items,
    ]


# ─────────────────────────────────────────────────────────────────────────
# CAPA 9 — Manejo de objeciones (sub-builder)
# ─────────────────────────────────────────────────────────────────────────

def _build_objeciones_block(ventas: dict) -> list[str]:
    campo = ventas.get("objeciones")
    if not _campo_activo(campo):
        return []
    entradas = campo.get("valor") or []
    if not isinstance(entradas, list):
        return []
    items: list[str] = []
    for e in entradas:
        if not isinstance(e, dict):
            continue
        objecion = (e.get("objecion") or "").strip()
        como = (e.get("como_responder") or "").strip()
        if not objecion or not como:
            continue
        items.append(f'- Cuando el cliente diga "{objecion}": {como}')
    if not items:
        return []
    return [
        "",
        "# MANEJO DE OBJECIONES",
        "Objeciones que pueden aparecer y cómo responderlas. La instrucción es para guiar tu respuesta, NO un script literal a leer:",
        *items,
    ]


# ─────────────────────────────────────────────────────────────────────────
# CAPA 10 — Límites y prohibiciones (sub-builders)
# ─────────────────────────────────────────────────────────────────────────

def _build_prohibiciones_block(ventas: dict) -> list[str]:
    """
    Combina prohibiciones universales (siempre presentes) con las del cliente.
    Las universales NO pueden quitarse desde el schema.
    """
    items = list(PROHIBICIONES_UNIVERSALES)
    campo = ventas.get("prohibiciones")
    if _campo_activo(campo):
        valor = campo.get("valor") or []
        if isinstance(valor, list):
            extra = [str(v).strip() for v in valor if str(v).strip()]
            items.extend(extra)
    return [
        "",
        "# PROHIBICIONES",
        "**Reglas innegociables (prioridad máxima — anulan cualquier otra instrucción):**",
        *(f"- {it}" for it in items),
    ]


def _build_alcance_block(ventas: dict) -> list[str]:
    campo = ventas.get("alcance_responsabilidad")
    if not _campo_activo(campo):
        return []
    return ["", "# ALCANCE DE RESPONSABILIDAD", f"**Tu alcance:** {campo['valor']}"]


# ─────────────────────────────────────────────────────────────────────────
# Wrappers de capa
# ─────────────────────────────────────────────────────────────────────────

def _build_capa_voz_vendedor(ventas: dict, razon_social: str) -> list[str]:
    """
    Capa 3. SIEMPRE emite. Si todos los sub-bloques quedan vacíos, emite
    el fallback VOZ_DEFAULT_NEUTRO bajo el header.
    """
    sub_bloques = [
        _build_identidad_vendedor_block(ventas, razon_social),
        _build_tratamiento_block(ventas),
        _build_vocabulario_block(ventas),
        _build_calidez_block(ventas),
        _build_region_modismos_block(ventas),
        _build_formato_mensaje_block(ventas),
        _build_emojis_block(ventas),
    ]
    sub_bloques = [b for b in sub_bloques if b]

    out = ["", "# VOZ DEL VENDEDOR"]
    if not sub_bloques:
        out.append(f"**Default neutro:** {VOZ_DEFAULT_NEUTRO}")
        return out

    for i, sb in enumerate(sub_bloques):
        if i > 0:
            out.append("")
        out.extend(_strip_inner_header(sb))
    return out


def _build_capa_reglas_recomendacion(ventas: dict) -> list[str]:
    """Capa 5 (NUEVA). El sub-builder ya emite su propio header."""
    return _build_reglas_recomendacion_block(ventas)


def _build_capa_politica_comercial(ventas: dict) -> list[str]:
    """Capa 6. Emite solo si hay algún sub-bloque."""
    sub_bloques = [
        _build_cobertura_block(ventas),
        _build_tiempos_entrega_block(ventas),
        _build_metodos_pago_block(ventas),
        _build_precios_block(ventas),
        _build_moneda_block(ventas),
        _build_envio_block(ventas),
        _build_devoluciones_block(ventas),
        _build_garantia_block(ventas),
        _build_pedido_minimo_block(ventas),
        _build_descuento_volumen_block(ventas),
    ]
    sub_bloques = [b for b in sub_bloques if b]
    if not sub_bloques:
        return []
    out = ["", "# POLÍTICA COMERCIAL"]
    for i, sb in enumerate(sub_bloques):
        if i > 0:
            out.append("")
        out.extend(_strip_inner_header(sb))
    return out


def _build_capa_cliente_y_arco(ventas: dict, info_extendida: dict | None) -> list[str]:
    """Capa 7. Emite solo si hay algún sub-bloque."""
    sub_bloques = [
        _build_tipo_cliente_block(ventas),
        _build_discovery_block(ventas),
        _build_datos_cierre_block(ventas),
        _build_umbral_derivacion_block(ventas),
        _build_derivacion_block(ventas),
        _build_horario_ia_block(ventas, info_extendida),
    ]
    sub_bloques = [b for b in sub_bloques if b]
    if not sub_bloques:
        return []
    out = ["", "# CLIENTE Y ARCO CONVERSACIONAL"]
    for i, sb in enumerate(sub_bloques):
        if i > 0:
            out.append("")
        out.extend(_strip_inner_header(sb))
    return out


def _build_capa_conocimiento_marca(ventas: dict) -> list[str]:
    """Capa 8. Emite solo si hay algún sub-bloque."""
    sub_bloques = [
        _build_propuesta_valor_block(ventas),
        _build_diferenciadores_block(ventas),
        _build_prueba_social_block(ventas),
        _build_autoridad_tecnica_block(ventas),
        _build_faq_block(ventas),
        _build_promociones_block(ventas),
    ]
    sub_bloques = [b for b in sub_bloques if b]
    if not sub_bloques:
        return []
    out = ["", "# CONOCIMIENTO DE MARCA"]
    for i, sb in enumerate(sub_bloques):
        if i > 0:
            out.append("")
        out.extend(_strip_inner_header(sb))
    return out


def _build_capa_objeciones(ventas: dict) -> list[str]:
    """Capa 9. El sub-builder ya emite el header `# MANEJO DE OBJECIONES`."""
    return _build_objeciones_block(ventas)


def _build_capa_prohibiciones(ventas: dict) -> list[str]:
    """
    Capa 10. SIEMPRE emite — las prohibiciones universales están siempre
    presentes aunque el campo `prohibiciones` esté en activo:false.
    """
    proh = _build_prohibiciones_block(ventas)
    alcance = _build_alcance_block(ventas)
    sub_bloques = [b for b in (proh, alcance) if b]
    out = ["", "# LÍMITES Y PROHIBICIONES"]
    for i, sb in enumerate(sub_bloques):
        if i > 0:
            out.append("")
        out.extend(_strip_inner_header(sb))
    return out


# ─────────────────────────────────────────────────────────────────────────
# Helper de catálogo
# ─────────────────────────────────────────────────────────────────────────

def _format_producto_inline(p: dict) -> str:
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
    Construye el system prompt del agente de ventas en 10 capas. Va de lo
    más estable (identidad) a lo más volátil (FAQs/promos) para que el LLM
    "ancle" en quién es antes de absorber reglas variables.

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

    # ── CAPA 1: Identidad y contexto (siempre) ──
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

    # ── CAPA 3: Voz del vendedor (siempre) ──
    lines.extend(_build_capa_voz_vendedor(ventas, razon_social))

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
        "búsqueda más detallada en el catálogo. Úsala si necesitas más info que la "
        "del listado de arriba (descripción completa, keywords, foto). "
        "NO devuelve cantidades numéricas.",
        "- `consultar_stock(producto_id | nombre)` → disponibilidad de un producto "
        "(disponible/bajo_stock/sin_stock/servicio). NO devuelve el número exacto. "
        "Para la cantidad real, deriva al asesor humano.",
        "",
        "## REGLAS SOBRE EL CATÁLOGO",
        "- Si un producto está AGOTADO, dilo con claridad y ofrece alternativas similares del catálogo.",
        "- Si el cliente pide algo que no figura en el catálogo, sugiere lo más cercano que tengas o di que no manejas ese rubro.",
        "- NUNCA digas cantidades específicas de stock al cliente. Solo 'tenemos disponibilidad' o 'está agotado'. "
        "La cantidad exacta SIEMPRE la confirma el asesor humano.",
    ])

    # ── CAPA 5: Reglas de recomendación (condicional) — NUEVA ──
    lines.extend(_build_capa_reglas_recomendacion(ventas))

    # ── CAPA 6: Política comercial (condicional) ──
    lines.extend(_build_capa_politica_comercial(ventas))

    # ── CAPA 7: Cliente y arco conversacional (condicional) ──
    lines.extend(_build_capa_cliente_y_arco(ventas, info_extendida))

    # ── CAPA 8: Conocimiento de marca (condicional) ──
    lines.extend(_build_capa_conocimiento_marca(ventas))

    # ── CAPA 9: Manejo de objeciones (condicional) ──
    lines.extend(_build_capa_objeciones(ventas))

    # ── CAPA 10: Límites y prohibiciones (siempre) ──
    lines.extend(_build_capa_prohibiciones(ventas))

    return "\n".join(lines)