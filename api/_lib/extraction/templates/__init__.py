"""
api/_lib/extraction/templates/__init__.py

Importa todos los templates del paquete para que el registry los
descubra automáticamente. Para agregar un template nuevo, crear
`<nombre>.py` con NAME + PROMPT y agregar la línea correspondiente acá.
"""

from . import factura
from . import caja_chica

__all__ = ["factura", "caja_chica"]
