"""
api/_lib/registro_contable/templates/

Importa todos los templates del paquete para que el registry los descubra
automáticamente. Para agregar un sistema contable nuevo:

  1. Crear `<nombre>.py` con NAME, DEFAULTS, EXCEL_HEADERS, factura_a_filas,
     build_xlsx (mismo shape que concar.py).
  2. Agregar la línea correspondiente acá:
       from . import <nombre>
"""

from . import concar

__all__ = ["concar"]
