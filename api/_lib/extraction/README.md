# `_lib/extraction/` — motor de extracción de datos por templates

Motor genérico que toma un archivo (PDF, imagen, Excel, Word) y extrae
campos estructurados usando OpenAI (Vision o texto plano), siguiendo
el prompt + post-procesamiento que define el **template** elegido.

## Arquitectura

```
_lib/extraction/
├── __init__.py              ← API pública del paquete (re-exports)
├── engine.py                ← funciones de bajo nivel + ruteo por extensión
├── registry.py              ← descubrimiento lazy de templates
├── README.md                ← este archivo
└── templates/
    ├── __init__.py          ← importa los módulos para que registry los descubra
    ├── factura.py           ← template factura/boleta/NC/ND/RH/BA/TK
    └── caja_chica.py        ← template solicitud de caja chica
```

### `engine.py`

Reúne las funciones de bajo nivel que hablan con OpenAI y los lectores
de archivo (PDF, Excel, Word). Expone dos APIs:

- **`extract_from_file(file_bytes, filename, prompt, api_key, **kwargs)`**
  Ruteo por extensión. Devuelve `(campos, raw_text)`. Es la función
  útil cuando ya tenés el prompt en mano y solo querés extraer.

- **`extract_with_template(file_bytes, filename, template_name, api_key)`**
  Alto nivel: resuelve el template via registry, aplica `enrich()`
  opcional, y devuelve un dict normalizado con `campos`, `raw_text`
  y `template`. Es lo que usa el endpoint HTTP.

### `registry.py`

Descubre templates iterando sobre los atributos del paquete `templates`.
Cualquier módulo con `NAME` y `PROMPT` no vacíos se considera un template
válido. La construcción es **lazy**: no se hace hasta la primera llamada
a `get_template()` o `list_templates()`.

### `templates/<nombre>.py`

Un archivo por tipo de documento. Cada template debe declarar:

```python
NAME = "<nombre_unico>"            # obligatorio
PROMPT = """..."""                 # obligatorio
DESCRIPTION = "..."                # opcional, recomendado
MODEL = "gpt-4o"                   # opcional, default "gpt-4o"
MAX_TOKENS_VISION = 1000           # opcional
MAX_TOKENS_TEXT = 800              # opcional

def enrich(campos: dict) -> dict:  # opcional
    """Post-procesamiento de los campos extraídos."""
    return {...}
```

## Cómo agregar un template nuevo

Ejemplo: agregar un template para `orden_requerimiento` (caso futuro).

1. Crear `templates/orden_requerimiento.py`:

   ```python
   NAME = "orden_requerimiento"
   DESCRIPTION = "Orden de requerimiento interno con ítems y aprobador."
   PROMPT = """Eres un asistente que extrae...
   ...formato JSON: {numero_or, fecha, area, items, total}..."""

   def enrich(campos):
       # Normalizar fecha, calcular subtotales, etc.
       return campos
   ```

2. Agregarlo a `templates/__init__.py`:

   ```python
   from . import factura
   from . import caja_chica
   from . import orden_requerimiento   # ← NUEVO

   __all__ = ["factura", "caja_chica", "orden_requerimiento"]
   ```

3. Listo. La próxima llamada a `list_templates()` lo incluye, y
   `extract_with_template(file_bytes, fname, "orden_requerimiento", key)`
   funciona automáticamente.

## Reglas de diseño

- **Un template = un dominio**. No mezclar prompts de varios tipos en
  un mismo módulo. Si dos dominios comparten lógica (ej. fechas
  peruanas, RUC), extraer helpers a `engine.py` o a un módulo aparte.
- **Prompts en español**. Los proveedores hablan español; los prompts
  siempre van en español neutro.
- **`enrich()` debe ser determinístico**. Sin llamadas HTTP, sin estado
  global. Es post-procesamiento puro: dict in → dict out.
- **No reescribir prompts en producción sin medir**. Cualquier cambio
  de wording puede alterar la extracción. Si vas a iterar el prompt,
  hacelo con un set de archivos de muestra y comparar resultados antes
  de mergear.

## Compatibilidad legacy

`api/parse_file.py` re-exporta 7 símbolos del motor (`_extract_via_vision`,
`_extract_pdf_pages`, `_extract_from_excel`, `_extract_from_docx`,
`_text_to_campos`, `_enrich_factura_data`, `_EXTRACTION_PROMPT_FACTURA`)
para que `api/_lib/facturas_processor.py` siga funcionando sin tocarlo.

Esos re-exports son **temporales**. La idea futura es:

1. Migrar `facturas_processor.py` a usar `extract_with_template` directo.
2. Eliminar los re-exports de `parse_file.py`.
3. Quedar con `parse_file.py` como handler 100% delgado.

Hasta que ese paso ocurra, **no agregar más código que dependa de los
símbolos privados de `engine.py` por path directo**. El consumo nuevo
debe ir contra `_lib.extraction.extract_with_template`.

## Roadmap futuro (NO implementado)

- **Validación contra `SCHEMA`**: cada template podría declarar un
  JSON Schema y el motor validaría la respuesta del LLM antes de
  hacer enrich. Hoy si el LLM devuelve un campo de más o de menos,
  pasa silenciosamente.
- **Multi-modelo**: soportar Claude / Gemini además de OpenAI. Ya hay
  un parámetro `MODEL` en cada template, falta el adapter.
- **Tests con golden files**: snapshot por template, comparar
  resultados contra ejemplos reales de cada tipo de documento.
- **Métricas por template**: cuántas veces se invoca, latencia, ratio
  de confianza alta/media/baja, tasa de error.

## Endpoints HTTP relacionados

```
POST /api/parse_file?template=<nombre>      → extrae con ese template
POST /api/parse_file?tipo=<nombre>          → alias legacy
POST /api/parse_file                        → default "caja_chica"
GET  /api/parse_file?action=list-templates  → discovery
```

Ver [api/parse_file.py](../../parse_file.py) para los detalles del handler.
