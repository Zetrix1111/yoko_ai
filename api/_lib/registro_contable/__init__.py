"""
api/_lib/registro_contable/

Motor genérico para generar el archivo Excel del registro de compras/ventas
en el formato del sistema contable de cada empresa (CONCAR, SISCONT,
FOXCONT, etc.).

Espejo del patrón de `api/_lib/extraction/`:

    extraction/                       registro_contable/
    ├── registry.py                   ├── registry.py
    ├── engine.py                     ├── engine.py
    └── templates/                    └── templates/
        ├── factura.py                    ├── concar.py
        └── caja_chica.py                 └── (siscont.py futuro)

API pública:
    from _lib.registro_contable import engine, registry

    # Endpoint web (UI clásica, descarga binaria):
    out = engine.generate(proceso_id, empresa_id)
    # → {"filename", "content_type", "content": bytes, "sistema",
    #    "num_facturas", "num_filas"}

    # Endpoint chat (validación liviana, sin generar bytes):
    out = engine.validate(proceso_id, empresa_id)
    # → {"ok", "sistema", "num_facturas", "num_filas_estimado", "errors"}
"""

from . import engine, registry

__all__ = ["engine", "registry"]
