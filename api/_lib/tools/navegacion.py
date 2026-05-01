"""
Tool de navegación — categoría 'navegacion'.

Importar este módulo registra la tool `navegar_ui` en `tool_registry.TOOLS`.

La tool no toca datos: devuelve un objeto `_action` que el frontend
interpreta para hacer router.push() a la sección correspondiente.

El cliente (chat.py + frontend) sabe que cualquier resultado con la
clave `_action` debe traducirse a una acción visual además de mostrar
el mensaje del LLM.
"""

from ..tool_registry import register


# Mapeo sección → módulo dueño. Las 7 secciones del enum corresponden a
# los submenús de "Gestión de Caja Chica" (ver src/features/modules/modulesConfig.js).
_SECCION_TO_MODULO: dict[str, str] = {
    "dashboard":      "gestion-caja",
    "solicitudes":    "gestion-caja",
    "aprobaciones":   "gestion-caja",
    "pagos":          "gestion-caja",
    "rendiciones":    "gestion-caja",
    "reportes":       "gestion-caja",
    "configuracion":  "gestion-caja",
}

# Mapeo sección → ?section= que entiende el frontend. Coincide con los ids
# de los submenús (la pantalla `GestionCajaChicaScreen` lee useSearchParams).
_SECCION_A_QUERY: dict[str, str] = {
    "dashboard":      "inicio",
    "solicitudes":    "solicitudes",
    "aprobaciones":   "aprobaciones",
    "pagos":          "pagos",
    "rendiciones":    "rendiciones",
    "reportes":       "reportes",
    "configuracion":  "configuracion",
}


@register(
    name="navegar_ui",
    description=(
        "Lleva al usuario a una pantalla específica de la app. Úsalo cuando "
        "el usuario pida 'llevame a X' o cuando la respuesta natural sea "
        "abrir una pantalla en lugar de explicar texto."
    ),
    parameters={
        "type": "object",
        "properties": {
            "seccion": {
                "type": "string",
                "enum": [
                    "dashboard", "solicitudes", "aprobaciones",
                    "pagos", "rendiciones", "reportes", "configuracion",
                ],
                "description": "Sección destino dentro del módulo.",
            },
        },
        "required": ["seccion"],
    },
    category="navegacion",
)
def navegar_ui(args: dict, context: dict) -> dict:
    seccion = args.get("seccion")

    modulo = _SECCION_TO_MODULO.get(seccion)
    if not modulo:
        # Esto no debería pasar porque el enum del schema lo previene, pero
        # somos defensivos por si el modelo "alucina" un valor.
        return {
            "error": "seccion_desconocida",
            "detail": f"La sección '{seccion}' no existe en este módulo.",
        }

    config = context.get("config") or {}
    modulos_habilitados = (config.get("empresa") or {}).get("modules", []) or []

    if modulo not in modulos_habilitados:
        return {
            "error":   "modulo_no_habilitado",
            "detail": (
                f"El módulo '{modulo}' no está habilitado para esta empresa. "
                f"Indícale al usuario que esa funcionalidad no está disponible."
            ),
            "seccion": seccion,
        }

    return {
        "_action": {
            "type":   "navigate",
            "path":   f"/modulos/{modulo}",
            "params": {"section": _SECCION_A_QUERY[seccion]},
        },
        "seccion": seccion,
    }
