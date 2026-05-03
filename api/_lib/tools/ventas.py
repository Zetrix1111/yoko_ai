"""
Tools de ventas — usadas SOLO por /api/sales_chat (el cerebro del bot-baileys).

NO se registran en `tool_registry.TOOLS` (el registry global de Yoko) para no
contaminar las herramientas que ve el chat normal de Yoko (caja chica, etc).
En su lugar, exponemos:

  • Funciones puras `consultar_productos(args, context)`, `consultar_stock(...)`.
  • `VENTAS_TOOLS_OPENAI`: lista en formato OpenAI para pasar a `tools=` en
    `client.chat.completions.create`.
  • `execute_ventas_tool(name, args, context)`: dispatcher.

Las tablas de productos viven en la base ORIGINAL (`AIRTABLE_BASE_ID`,
"Tablas CMEJIA SAC"). Las tablas de mensajes/conversaciones viven en la
base de ventas (`AIRTABLE_VENTAS_BASE_ID`). Estas tools solo leen productos.
"""

import os
from .. import airtable_client
from ..airtable_client import AirtableError


_TABLA_PRODUCTOS = "productos"


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _get_field(fields: dict, name: str, default=None):
    """
    Lee un campo de Airtable tolerando espacios accidentales en el nombre.
    Ejemplo: en la tabla productos el campo se llama " precio " (con
    espacios), aceptamos tanto 'precio' como ' precio '.
    """
    if name in fields:
        return fields[name]
    for k, v in fields.items():
        if isinstance(k, str) and k.strip() == name:
            return v
    return default


def _normalize_producto(rec: dict) -> dict:
    """Aplana un record de productos al shape que consumirá el LLM."""
    f = rec.get("fields", {})
    foto_field = _get_field(f, "foto")
    foto_url = None
    if isinstance(foto_field, list) and foto_field:
        foto_url = foto_field[0].get("url")
    elif isinstance(foto_field, str):
        foto_url = foto_field

    stock = _get_field(f, "stock")
    stock_minimo = _get_field(f, "stock_minimo")

    # Estado del stock (mismas reglas que el frontend)
    if stock is None or stock == "":
        estado = "servicio"
    elif stock == 0:
        estado = "sin_stock"
    elif stock_minimo is not None and stock <= stock_minimo:
        estado = "bajo_stock"
    else:
        estado = "disponible"

    return {
        "id":             rec.get("id"),
        "nombre":         _get_field(f, "nombre", ""),
        "descripcion":    _get_field(f, "descripcion", ""),
        "precio":         _get_field(f, "precio", 0) or 0,
        "stock":          stock,
        "estado_stock":   estado,
        "categoria":      _get_field(f, "categoria"),
        "foto":           foto_url,
        "keywords":       _get_field(f, "keywords", ""),
    }


def _filter_match_query(producto: dict, query: str) -> bool:
    """Match case-insensitive en nombre, descripción, keywords y categoría."""
    if not query:
        return True
    q = query.lower().strip()
    haystack = " ".join([
        str(producto.get("nombre", "")),
        str(producto.get("descripcion", "")),
        str(producto.get("keywords", "")),
        str(producto.get("categoria", "")),
    ]).lower()
    # Match si cualquier palabra del query aparece en el haystack
    for word in q.split():
        if word in haystack:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────
# Tool: consultar_productos
# ─────────────────────────────────────────────────────────────────────────

def consultar_productos(args: dict, context: dict) -> dict:
    """
    Lista productos del catálogo del tenant. Filtros opcionales:
      • query: busca en nombre/descripcion/keywords/categoria
      • solo_disponibles: si True, excluye 'sin_stock' (servicios siguen)
      • categoria: filtra por categoría exacta

    El context debe incluir 'empresa_id' (lo inyecta /api/sales_chat).
    """
    empresa_id = (context or {}).get("empresa_id")
    if not empresa_id:
        return {"error": "validacion", "detail": "Falta empresa_id en el context."}

    query = (args or {}).get("query")
    solo_disponibles = bool((args or {}).get("solo_disponibles"))
    categoria = (args or {}).get("categoria")

    try:
        # Lee de la base ORIGINAL (productos vive ahí)
        formula = f"AND({{empresa_id}}='{empresa_id}', {{activo}}=TRUE())"
        if categoria:
            formula = f"AND({formula[4:-1]}, {{categoria}}='{categoria}')"
        records = airtable_client.list_records(
            _TABLA_PRODUCTOS,
            filter_formula=formula,
            max_records=100,
            # Sin base_id explícito → usa AIRTABLE_BASE_ID
        )
    except AirtableError as e:
        return {"error": "interno", "detail": f"No se pudo leer productos: {e}"}

    productos = [_normalize_producto(r) for r in records]

    # Filtro por query (en memoria, Airtable formula no soporta búsquedas
    # multi-campo trivialmente)
    if query:
        productos = [p for p in productos if _filter_match_query(p, query)]

    # Filtro solo_disponibles
    if solo_disponibles:
        productos = [p for p in productos if p["estado_stock"] != "sin_stock"]

    return {
        "productos":    productos,
        "total":        len(productos),
        "filtros":      {"query": query, "solo_disponibles": solo_disponibles, "categoria": categoria},
    }


# ─────────────────────────────────────────────────────────────────────────
# Tool: consultar_stock
# ─────────────────────────────────────────────────────────────────────────

def consultar_stock(args: dict, context: dict) -> dict:
    """
    Devuelve el stock exacto de un producto. Acepta `producto_id` (recId
    de Airtable) o `nombre` (match exacto).
    """
    empresa_id = (context or {}).get("empresa_id")
    if not empresa_id:
        return {"error": "validacion", "detail": "Falta empresa_id en el context."}

    producto_id = (args or {}).get("producto_id")
    nombre = (args or {}).get("nombre")
    if not producto_id and not nombre:
        return {"error": "validacion", "detail": "Pasar 'producto_id' o 'nombre'."}

    try:
        if producto_id:
            rec = airtable_client.get_record(_TABLA_PRODUCTOS, producto_id)
            producto = _normalize_producto(rec)
            # Verifica que sea del tenant correcto
            f = rec.get("fields", {})
            if _get_field(f, "empresa_id") != empresa_id:
                return {"error": "validacion", "detail": "Producto no pertenece al tenant."}
        else:
            # Buscar por nombre (match parcial uppercase)
            formula = (
                f"AND({{empresa_id}}='{empresa_id}', "
                f"FIND(UPPER('{nombre}'), UPPER({{nombre}}))>0)"
            )
            records = airtable_client.list_records(
                _TABLA_PRODUCTOS, filter_formula=formula, max_records=5,
            )
            if not records:
                return {"encontrado": False, "motivo": f"No hay producto con nombre '{nombre}'."}
            if len(records) > 1:
                return {
                    "encontrado": True,
                    "ambiguo":    True,
                    "candidatos": [_normalize_producto(r) for r in records],
                }
            producto = _normalize_producto(records[0])
    except AirtableError as e:
        return {"error": "interno", "detail": f"No se pudo leer producto: {e}"}

    return {
        "encontrado":   True,
        "id":           producto["id"],
        "nombre":       producto["nombre"],
        "stock":        producto["stock"],
        "estado_stock": producto["estado_stock"],
        "precio":       producto["precio"],
    }


# ─────────────────────────────────────────────────────────────────────────
# Definiciones para OpenAI function calling
# ─────────────────────────────────────────────────────────────────────────

VENTAS_TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "consultar_productos",
            "description": (
                "Lista los productos del catálogo de la empresa. Úsala cuando el "
                "cliente pregunta '¿qué venden?', '¿tienen X?', 'cuánto cuesta…', "
                "'productos disponibles', etc. Devuelve nombre, precio, stock, "
                "estado_stock (disponible/bajo_stock/sin_stock/servicio) y descripción."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Texto de búsqueda. Match parcial en nombre, descripción, "
                            "keywords y categoría. Ej: 'taladro', 'soldadora 160'."
                        ),
                    },
                    "solo_disponibles": {
                        "type": "boolean",
                        "description": "Si True, excluye productos con stock=0.",
                    },
                    "categoria": {
                        "type": "string",
                        "description": "Filtra por categoría exacta.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_stock",
            "description": (
                "Devuelve el stock exacto de un producto específico. Úsala cuando "
                "el cliente pregunta '¿cuántos quedan?', '¿hay stock?'. Acepta "
                "producto_id (recId interno) o nombre."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "producto_id": {"type": "string", "description": "recId de Airtable."},
                    "nombre":      {"type": "string", "description": "Nombre o texto del nombre del producto."},
                },
            },
        },
    },
]


# Dispatcher (lo usa /api/sales_chat para ejecutar la tool que el LLM eligió)
_VENTAS_HANDLERS = {
    "consultar_productos": consultar_productos,
    "consultar_stock":     consultar_stock,
}


def execute_ventas_tool(name: str, args: dict, context: dict) -> dict:
    """Ejecuta una tool de ventas. Devuelve dict serializable a JSON."""
    handler = _VENTAS_HANDLERS.get(name)
    if handler is None:
        return {"error": "interno", "detail": f"Tool de ventas '{name}' no existe."}
    try:
        result = handler(args or {}, context or {})
        if not isinstance(result, dict):
            return {"error": "interno", "detail": f"Tool '{name}' devolvió {type(result).__name__}."}
        return result
    except Exception as e:
        import sys
        print(f"[ventas tool] Error en '{name}': {type(e).__name__}: {e}", file=sys.stderr)
        return {"error": "interno", "detail": f"{type(e).__name__}: {e}"}
