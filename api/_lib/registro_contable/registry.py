"""
api/_lib/registro_contable/registry.py

Registro lazy de templates de salida (registros contables). Descubre
automáticamente los módulos en `api/_lib/registro_contable/templates/`
que tengan los atributos `NAME` + `factura_a_filas` + `build_xlsx`, y los
expone via `get_template(name)`.

Para agregar un sistema contable nuevo:
  1. Crear `templates/<nombre>.py` con `NAME`, `DEFAULTS`, `EXCEL_HEADERS`,
     `factura_a_filas(factura, contab, fecha_hoy)` y `build_xlsx(filas)`.
  2. Importarlo en `templates/__init__.py`:
       `from . import <nombre>`
  3. Listo. La empresa que tenga `Config_Empresa.basicos.sistema_contable
     = "<nombre>"` empieza a usarlo automáticamente.

API pública:
  - `get_template(name)`     → módulo del template, o ValueError.
  - `list_templates()`       → lista de dicts {name, description}.
  - `register_template(mod)` → registra programáticamente (útil en tests).
  - `reset_registry()`       → limpia el cache (útil en tests).
"""

from typing import Any, Dict, List, Optional


_REGISTRY: Optional[Dict[str, Any]] = None


def _build_registry() -> Dict[str, Any]:
    """
    Itera el paquete `templates` y registra los módulos que tienen el shape
    esperado: NAME + factura_a_filas + build_xlsx (no exigimos DEFAULTS ni
    EXCEL_HEADERS porque algún template podría no necesitarlos).

    Lanza RuntimeError si:
      - No se encuentra ningún template (paquete vacío o mal armado).
      - Dos templates declaran el mismo NAME (colisión).
    """
    from . import templates  # noqa: F401

    registry: Dict[str, Any] = {}

    for attr_name in dir(templates):
        if attr_name.startswith("_"):
            continue
        candidate = getattr(templates, attr_name)
        name = getattr(candidate, "NAME", None)
        factura_a_filas = getattr(candidate, "factura_a_filas", None)
        build_xlsx = getattr(candidate, "build_xlsx", None)
        if not name or not callable(factura_a_filas) or not callable(build_xlsx):
            continue
        if name in registry:
            raise RuntimeError(
                f"Template duplicado: '{name}' está declarado en "
                f"'{registry[name].__name__}' y en '{candidate.__name__}'."
            )
        registry[name] = candidate

    if not registry:
        raise RuntimeError(
            "No se encontraron templates en api/_lib/registro_contable/templates/. "
            "Asegurate de que cada módulo declare NAME, factura_a_filas y "
            "build_xlsx, y que esté importado en templates/__init__.py."
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
        la lista de templates disponibles para diagnóstico.
    """
    registry = _get_or_build()
    if name not in registry:
        disponibles = ", ".join(sorted(registry.keys())) or "(ninguno)"
        raise ValueError(
            f"Sistema contable '{name}' no soportado. Disponibles: {disponibles}."
        )
    return registry[name]


def list_templates() -> List[Dict[str, Any]]:
    """
    Devuelve la lista de templates registrados, cada uno como dict con
    `name` y `description` (opcional). Orden alfabético para output estable.
    """
    registry = _get_or_build()
    out: List[Dict[str, Any]] = []
    for name, mod in registry.items():
        out.append({
            "name":        name,
            "description": getattr(mod, "DESCRIPTION", ""),
        })
    out.sort(key=lambda t: t["name"])
    return out


def register_template(template_module: Any) -> None:
    """
    Registra un módulo como template programáticamente (útil en tests).
    Valida que tenga NAME + factura_a_filas + build_xlsx.
    """
    name = getattr(template_module, "NAME", None)
    fn1 = getattr(template_module, "factura_a_filas", None)
    fn2 = getattr(template_module, "build_xlsx", None)
    if not name or not callable(fn1) or not callable(fn2):
        raise ValueError(
            "El módulo debe tener atributos NAME (str), factura_a_filas "
            "(callable) y build_xlsx (callable)."
        )
    registry = _get_or_build()
    registry[name] = template_module


def reset_registry() -> None:
    """Limpia el cache. La próxima llamada lo reconstruye desde cero."""
    global _REGISTRY
    _REGISTRY = None
