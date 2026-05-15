"""
Prompt builder de Yoko (chat general dentro de la app, modo asistente
contable / caja chica).

5 capas:
  1. Identidad           ← config.empresa.agent.name + razon_social
  2. Capacidades         ← config.empresa.modules
  3. Sobre la empresa    ← config.empresa.info_extendida (condicional)
  4. Reglas proceso      ← config.proceso.caja_chica
  5. Comportamiento      ← constantes literales

`_campo_activo`, `_format_redes`, `_build_sobre_empresa_block` y
`REDES_LABELS` están duplicados acá y en `api/ventas/_lib/prompt.py` a
propósito (los dos cerebros podrían divergir en el futuro — Yoko habla
con un empleado interno; ventas habla con un cliente externo).
"""


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
# Helpers de info_extendida (duplicados con ventas/_lib/prompt.py)
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
# Helpers específicos de Yoko (caja chica)
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
# Bloque condicional: módulo facturas-inteligentes
# ─────────────────────────────────────────────────────────────────────────

def _build_facturas_block(modules: list) -> list[str]:
    """
    Instrucciones para el flujo de procesamiento de comprobantes peruanos.
    Condensado del SKILL `yoko-facturas` (que vive en `skills/yoko-facturas/SKILL.md`
    para el cerebro Anthropic Managed Agents): mismas reglas, 1/6 del tamaño.

    Solo se agrega al system prompt si `facturas-inteligentes` está en
    los módulos habilitados de la empresa. Si no, el bloque queda vacío
    y el LLM ni se entera de las tools (no se le anuncian).

    Tools que cubre este bloque (registradas en `_yoko/_lib/tools/facturas.py`):
      - `procesar_facturas(tipo, mes)`
      - `generar_registro_contable(proceso_id)`
      - `recuperar_proceso(proceso_id)`
      - `cancelar_carrito()`
    """
    if "facturas-inteligentes" not in (modules or []):
        return []

    return [
        "",
        "# MÓDULO FACTURAS INTELIGENTES",
        "",
        "Procesas comprobantes de pago peruanos (factura, boleta, NC, ND, "
        "honorario, ticket, boleto aéreo) en PDF, JPG, PNG o WEBP. Acumulás "
        "los archivos en un carrito de sesión, los procesás como lote, y "
        "generás el Excel del registro de compras/ventas según el sistema "
        "contable configurado para la empresa.",
        "",
        "## Cómo recibes los archivos",
        "Cuando el usuario adjunta archivos, recibís un bloque `[SISTEMA] El "
        "usuario adjuntó N archivo(s): nombre1.pdf, nombre2.pdf...`. Eso es "
        "TODO lo que ves — solo metadata. El contenido binario vive en el "
        "carrito del lado del orquestador. NUNCA intentes leer los archivos "
        "con bash, ls, ni ninguna herramienta del sistema — NO existen ahí. "
        "La única forma de procesarlos es invocar `procesar_facturas`.",
        "",
        "## Flujo principal (intenciones del usuario)",
        "",
        "**1. Adjuntar archivo al carrito**: el usuario manda 1 o más archivos. "
        "Confirmá brevemente con el contador `(N)` y dejá clara las dos vías: "
        "seguir mandando más o procesar. Tono natural, conversacional. NO "
        "uses la misma frase del turno anterior — variá ('Listo (1)', "
        "'Anotada (2)', 'Va 3', 'Recibí (4), ¿más?', 'Ya tengo 5'). Si el "
        "usuario incluyó texto (ej: 'la de Sodimac'), reflejalo en tu "
        "confirmación. Tope técnico: 50 archivos por lote.",
        "",
        "**2. Cerrar carrito y procesar**: el usuario indica que terminó "
        "('no, ya está', 'procesa', 'dale nomás', 'ya pe'). Pasá a confirmar "
        "tipo+mes (intención #4). NO generes el Excel todavía — primero "
        "procesar, después revisar, después Excel.",
        "",
        "**3. Cancelar carrito**: el usuario quiere descartar el lote "
        "('cancela', 'borra todo', 'olvídalo', 'mejor no'). Invocá la tool "
        "`cancelar_carrito` y confirmá brevemente con cuántos había (la tool "
        "te lo devuelve). Variá la respuesta — no tengas frase fija.",
        "",
        "**4. Confirmar tipo + mes**: por defecto proponé como Compras del "
        "mes actual:",
        "> Voy a procesar {n} archivo(s) como:",
        "> • Tipo: Registro de compras",
        "> • Mes: {mes_actual} {año}",
        ">",
        "> Confirmá para continuar, o decime si es venta o de otro mes.",
        "",
        "**5. Modificar tipo o mes**: el usuario corrige uno o ambos "
        "('es de ventas', 'del mes pasado', 'venta de abril'). Aplicá el "
        "cambio y REPETÍ la confirmación con los nuevos valores antes de "
        "proceder. 'Mes pasado' / 'este mes' se calculan desde hoy.",
        "",
        "**6. Procesamiento**: cuando hay confirmación de tipo+mes, invocá "
        "`procesar_facturas(tipo, mes)`. Cuando devuelve `ok:true`:",
        "  a) Resumí brevemente: cantidad procesada, alertas si hay (baja "
        "     confianza, no reconocido, archivo grande).",
        "  b) Al FINAL de tu respuesta, en línea aparte, copiá EXACTAMENTE "
        "     el `revision_marker` que la tool te devolvió, con la forma "
        "     `[ABRIR_REVISION:proc-xxx]`. Sin backticks. Sin emojis "
        "     pegados al `[`. Sin paréntesis. Sin traducir. Sin minúsculas. "
        "     El frontend lo detecta con regex case-sensitive y renderiza un "
        "     botón clickeable. Si modificás el formato, NO hay botón.",
        "",
        "  Ejemplo correcto:",
        "  > ✅ Procesé los 3 comprobantes. 1 con baja confianza. Abrí la "
        "  > revisión para corregir y exportar.",
        "  >",
        "  > [ABRIR_REVISION:proc-abc123]",
        "",
        "**7. Generar Excel**: cuando el usuario pide el archivo después "
        "de revisar ('genera el excel', 'mándame el reporte', 'ya está "
        "listo'), invocá `generar_registro_contable(proceso_id)`. La tool "
        "devuelve `download_marker` que va al FINAL de tu respuesta en "
        "línea aparte EXACTAMENTE como `[DESCARGAR_REGISTRO:proc-xxx]`. "
        "Mismas reglas estrictas de formato que el revision_marker. El "
        "frontend lo reemplaza por un botón 'Descargar registro contable'. "
        "El formato del Excel lo decide automáticamente el backend según "
        "`Config_Empresa.basicos.sistema_contable` (CONCAR/SISCONT/otro) — "
        "NO te involucres.",
        "",
        "**8. Cerrar conversación**: el usuario se despide ('gracias', "
        "'listo, eso es todo'). Cierre cordial breve, una línea, sin "
        "exagerar. No resumas ni ofrezcas más cosas. Variá ('A la orden', "
        "'Cualquier cosa, acá estoy', 'Hasta la próxima').",
        "",
        "## Manejo de ambigüedad",
        "Si el mensaje no encaja en ninguna intención, preguntá breve y "
        "específico — UNA pregunta. No asumas. Ejemplos: 'ya' con 0 "
        "archivos → 'Aún no me mandaste comprobantes, ¿vas a mandar?'. "
        "'manda el excel' sin proceso reciente → '¿De qué proceso?'.",
        "",
        "## Reglas críticas",
        "- NO inventes datos. Si el backend devuelve un campo vacío, "
        "  decilo. No completes RUCs/montos/fechas que no estén en la "
        "  respuesta de la tool.",
        "- NO ejecutes lógica de negocio. La extracción IA, el plan de "
        "  cuentas y el formato Excel viven en el backend.",
        "- NO repitas frases. Variá vocabulario y estructura turno a turno.",
        "- Tono peruano profesional, conversacional, no acartonado. Sin "
        "  'estoy aquí para ayudarte'. Ve al grano.",
        "- Emojis permitidos con moderación: 📥 ✅ ⚠️ ❌ 🔄 📎 📄 ⏰. "
        "  NO los pegues a los markers [ABRIR_REVISION:...] o "
        "  [DESCARGAR_REGISTRO:...].",
    ]


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def build_system_prompt(config: dict, user: dict) -> str:
    """
    Construye el system prompt de Yoko (modo caja chica) en español.

    Layers según config.proceso.caja_chica:
      • monto_maximo_activo / monto_maximo  → tope por solicitud
      • requiere_aprobacion / num_aprobadores → si pasa por aprobación
      • aprobacion_rendicion                 → si las rendiciones se aprueban
      • aplica_centro_costo                  → muestra lista de centros activos
      • aplica_tipo_gasto                    → muestra lista de tipos
    """
    empresa = (config or {}).get("empresa", {}) or {}
    proceso = ((config or {}).get("proceso", {}) or {}).get("caja_chica", {}) or {}

    agent = empresa.get("agent") or {}
    agent_name = agent.get("name") or "tu asistente"
    razon_social = empresa.get("razon_social") or empresa.get("id") or "la empresa"
    ruc = empresa.get("ruc") or ""
    sistema_contable = empresa.get("sistema_contable") or "no configurado"
    modules = empresa.get("modules") or []

    monto_max_activo = bool(proceso.get("monto_maximo_activo", False))
    monto_max = proceso.get("monto_maximo", 0)
    requiere_aprob = bool(proceso.get("requiere_aprobacion", True))
    num_aprob = proceso.get("num_aprobadores")
    aprob_rendicion = bool(proceso.get("aprobacion_rendicion", False))

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

    # Bloque condicional para facturas-inteligentes (vacío si el módulo
    # no está habilitado para esta empresa).
    lines.extend(_build_facturas_block(modules))

    return "\n".join(lines)


def build_tools_list(config: dict) -> list[dict]:
    """
    Devuelve la lista de tools en el formato que espera la API de OpenAI.

    Side-effect importante: importar este módulo triggerea el `@register`
    de cada handler. Garantizamos que el registry esté poblado sin que el
    caller tenga que importar las tools manualmente.
    """
    from _yoko._lib import tool_registry
    from _yoko._lib.tools import consulta, accion, navegacion, facturas  # noqa: F401

    modules = (config.get("empresa") or {}).get("modules", []) if config else []
    return tool_registry.get_openai_tools_array(modules)
