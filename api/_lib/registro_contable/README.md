# registro_contable/

Motor genérico para generar el Excel del registro de compras/ventas en el
formato del sistema contable de cada empresa.

Espejo del patrón `_lib/extraction/`. El sistema contable activo se elige
desde `Config_Empresa.basicos.sistema_contable` de cada empresa.

## API

```python
from _lib.registro_contable import engine

# Validación liviana (no genera bytes). Usado por el chat tool.
out = engine.validate(proceso_id, empresa_id)
# → {ok, sistema, num_facturas, num_filas_estimado}

# Generación completa. Usado por el endpoint de descarga (web UI).
out = engine.generate(proceso_id, empresa_id)
# → {filename, content_type, content: bytes, sistema, num_facturas, num_filas}
```

Ambas levantan `ValueError` con mensaje legible si:
- El proceso no existe o expiró.
- El proceso no tiene facturas.
- `sistema_contable` de la empresa no resuelve a un template registrado.

## Templates registrados

| name      | descripción                                                |
|-----------|------------------------------------------------------------|
| `concar`  | Registro de compras/ventas formato CONCAR (Perú).          |

## Cómo agregar un sistema contable nuevo

Ej: SISCONT.

1. Crear `templates/siscont.py` con el mismo shape que `concar.py`:
   ```python
   NAME = "siscont"
   DESCRIPTION = "Registro de compras/ventas formato SISCONT (Perú)"

   DEFAULTS: dict = { ... }            # plan de cuentas, sub_diarios, etc.
   EXCEL_HEADERS: dict = { ... }       # cabeceras del .xlsx

   def factura_a_filas(factura, contab, fecha_hoy) -> list[dict]: ...
   def build_xlsx(filas) -> bytes: ...
   ```

2. Registrarlo en `templates/__init__.py`:
   ```python
   from . import concar
   from . import siscont
   ```

3. Listo. Cualquier empresa con `Config_Empresa.basicos.sistema_contable
   = "siscont"` empieza a usarlo automáticamente. El registry lo descubre
   en la primera llamada (cache lazy).

## Dónde se invoca

- `api/facturas.py:_concar` (action `concar`) → `engine.generate()` → stream
  binario para que la web UI lo descargue.
- `api/facturas.py:_registro_contable_chat` (action `registro-contable-chat`)
  → `engine.validate()` → JSON con metadata para el agent.

## Garantías

- **No muta el state**. `validate` y `generate` son puras: leen del proceso
  cacheado en SQLite y de Airtable, no escriben.
- **Cross-tenant safe**. Toda lookup pasa `empresa_id` a `db_manager.get_proceso`,
  que valida que el proceso pertenece a la empresa.
- **Backwards-compat**. `_lib/contabilidad.py` re-exporta los símbolos
  legacy (`CONCAR_DEFAULTS`, `factura_a_filas_excel`) para no romper
  imports antiguos.
