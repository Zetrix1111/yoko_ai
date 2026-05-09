"""
api/_lib/extraction/registry.py

Registro lazy de templates de extracción. Descubre automáticamente los
módulos en `api/_lib/extraction/templates/` que tengan los atributos
`NAME` y `PROMPT` y los expone via `get_template(name)`.

Para agregar un template nuevo:
  1. Crear `api/_lib/extraction/templates/<nombre>.py` con al menos
     `NAME = "<nombre>"` y `PROMPT = "..."`.
  2. Agregarlo a `api/_lib/extraction/templates/__init__.py`:
       `from . import <nombre>`
  3. Listo. La primera llamada a `get_template` o `list_templates` lo
     descubre y cachea.

API pública:
  - `get_template(name)`     → módulo del template, o ValueError.
  - `list_templates()`       → lista de dicts {name, description, model}.
  - `register_template(mod)` → registra programáticamente (útil en tests).
  - `reset_registry()`       → limpia el cache (útil en tests).
"""

from typing import Any, Dict, List, Optional


# Cache lazy. Se construye la primera vez que se solicita.
_REGISTRY: Optional[Dict[str, Any]] = None


def _build_registry() -> Dict[str, Any]:
    """
    Construye el registry iterando sobre los atributos del paquete
    `templates`. Considera template válido cualquier atributo con
    `NAME` y `PROMPT` no vacíos.

    Lanza RuntimeError si:
      - No se encuentra ningún template (paquete vacío o mal armado).
      - Dos templates declaran el mismo NAME (colisión).
    """
    # Import local del paquete templates para evitar resolver al cargar.
    from . import templates  # noqa: F401

    registry: Dict[str, Any] = {}

    for attr_name in dir(templates):
        if attr_name.startswith("_"):
            continue
        candidate = getattr(templates, attr_name)
        # Solo nos interesan módulos que expongan NAME + PROMPT.
        name = getattr(candidate, "NAME", None)
        prompt = getattr(candidate, "PROMPT", None)
        if not name or not prompt:
            continue
        if name in registry:
            raise RuntimeError(
                f"Template duplicado: '{name}' está declarado en "
                f"'{registry[name].__name__}' y en '{candidate.__name__}'."
            )
        registry[name] = candidate

    if not registry:
        raise RuntimeError(
            "No se encontraron templates en api/_lib/extraction/templates/. "
            "Asegurate de que cada módulo declare NAME y PROMPT, y que esté "
            "importado en templates/__init__.py."
        )

    return registry


def _get_or_build() -> Dict[str, Any]:
    """Devuelve el registry, construyéndolo lazy en la primera llamada."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_template(name: str) -> Any:
    """
    Devuelve el módulo del template con el `NAME` indicado.

    Raises:
        ValueError si el nombre no está registrado. El mensaje incluye
        la lista de templates disponibles para que el caller pueda
        sugerirle al usuario qué nombres son válidos.
    """
    registry = _get_or_build()
    if name not in registry:
        disponibles = ", ".join(sorted(registry.keys())) or "(ninguno)"
        raise ValueError(
            f"Template '{name}' no encontrado. Disponibles: {disponibles}."
        )
    return registry[name]


def list_templates() -> List[Dict[str, Any]]:
    """
    Devuelve la lista de templates registrados, cada uno como dict con
    `name`, `description` (opcional) y `model` (opcional). Útil para
    endpoints de discovery (ej. `GET /api/parse_file?action=list-templates`).
    """
    registry = _get_or_build()
    out: List[Dict[str, Any]] = []
    for name, mod in registry.items():
        out.append({
            "name":        name,
            "description": getattr(mod, "DESCRIPTION", ""),
            "model":       getattr(mod, "MODEL", "gpt-4o"),
        })
    # Orden alfabético para output estable.
    out.sort(key=lambda t: t["name"])
    return out


def register_template(template_module: Any) -> None:
    """
    Registra un módulo como template programáticamente.

    Útil en tests donde se quiere inyectar un template fake sin tener
    que crear un archivo en `templates/`. Valida que el módulo tenga
    `NAME` y `PROMPT`.

    Si ya hay un template con el mismo NAME, lo reemplaza.
    """
    name = getattr(template_module, "NAME", None)
    prompt = getattr(template_module, "PROMPT", None)
    if not name or not prompt:
        raise ValueError(
            "El módulo debe tener atributos NAME y PROMPT no vacíos."
        )
    registry = _get_or_build()
    registry[name] = template_module


def reset_registry() -> None:
    """
    Limpia el cache. Después de llamar a esto, la próxima invocación
    de `get_template` / `list_templates` re-construye el registry desde
    cero. Útil en tests que mutan el paquete `templates` en runtime.
    """
    global _REGISTRY
    _REGISTRY = None
