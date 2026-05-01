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


def _format_centros(centros: list) -> str:
    """Lista compacta de centros de costo activos."""
    activos = [c for c in centros if c.get("activo")]
    if not activos:
        return "ninguno configurado todavía."
    return ", ".join(
        f"{c.get('codigo','?')} {c.get('nombre','?')}" for c in activos
    )


def _format_tipos(tipos: list) -> str:
    """Lista compacta de tipos de gasto activos."""
    activos = [t for t in tipos if t.get("activo")]
    if not activos:
        return "ninguno configurado todavía."
    return ", ".join(
        f"{t.get('codigo','?')} {t.get('nombre','?')}" for t in activos
    )


# ─────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────

def build_system_prompt(config: dict, user: dict) -> str:
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
    """
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
    aplica_cc = bool(proceso.get("aplica_centro_costo", True))
    aplica_tg = bool(proceso.get("aplica_tipo_gasto", False))

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
        "# REGLAS DEL PROCESO DE CAJA CHICA",
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
        aprobadores = proceso.get("aprobadores") or []
        if aprobadores:
            lines.append(f"- Aprobadores:{_format_aprobadores(aprobadores)}")
        else:
            lines.append(
                "- La lista de aprobadores específicos aún no está configurada "
                "en el sistema (Airtable Aprobadores vacía)."
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

    # ── Catálogos condicionales ──
    if aplica_cc:
        lines.append(
            f"- Centros de costo activos: {_format_centros(proceso.get('centros_costo', []))}"
        )
    if aplica_tg:
        lines.append(
            f"- Tipos de gasto válidos: {_format_tipos(proceso.get('tipos_gasto', []))}"
        )

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
