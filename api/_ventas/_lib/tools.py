"""
Tools de ventas — usadas SOLO por /api/sales_chat (cerebro del bot-baileys).

Aisladas del registry global de Yoko (caja chica) para no contaminar la
lista de tools que ve el chat normal. Exponemos:

  • Funciones puras `consultar_productos(args, context)`, `consultar_stock(...)`.
  • `TOOLS_OPENAI`: lista en formato OpenAI para pasar a `tools=` en
    `client.chat.completions.create`.
  • `execute(name, args, context)`: dispatcher.

Todas las tablas (productos, conversaciones, mensajes, wa_sessions, outbox)
viven en la base default `AIRTABLE_BASE_ID`. Multi-tenant via la columna
`empresa_id`. Estas tools solo leen productos.

⚠️ CAMBIO IMPORTANTE (v2):
Las tools NO devuelven el stock NUMÉRICO al LLM. Solo devuelven:
  - `estado_stock`: disponible / bajo_stock / sin_stock / servicio
  - `hay_disponibilidad`: boolean
  - `instruccion_agente`: recordatorio explícito de no mencionar cantidades
Esto evita que el agente diga "tenemos 50 unidades" sin verificación humana.
"""

from _lib import airtable_client
from _lib.airtable_client import AirtableError


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


def _calcular_estado_stock(stock, stock_minimo) -> str:
    """Calcula el estado del stock con las mismas reglas que el frontend."""
    if stock is None or stock == "":
        return "servicio"
    if stock == 0:
        return "sin_stock"
    if stock_minimo is not None and stock <= stock_minimo:
        return "bajo_stock"
    return "disponible"


def _normalize_producto(rec: dict) -> dict:
    """
    Aplana un record de productos al shape que consumirá el LLM.

    ⚠️ NO incluye el campo `stock` (numérico) intencionalmente. El LLM
    solo recibe `estado_stock` (disponible/bajo_stock/sin_stock/servicio)
    para evitar que mencione cantidades sin verificación humana.
    El stock numérico real se sigue leyendo de Airtable pero NO se expone.
    """
    f = rec.get("fields", {})
    foto_field = _get_field(f, "foto")
    foto_url = None
    if isinstance(foto_field, list) and foto_field:
        foto_url = foto_field[0].get("url")
    elif isinstance(foto_field, str):
        foto_url = foto_field

    stock = _get_field(f, "stock")
    stock_minimo = _get_field(f, "stock_minimo")
    estado = _calcular_estado_stock(stock, stock_minimo)

    return {
        "id":             rec.get("id"),
        "nombre":         _get_field(f, "nombre", ""),
        "descripcion":    _get_field(f, "descripcion", ""),
        "precio":         _get_field(f, "precio", 0) or 0,
        # ❌ NO exponer stock numérico al LLM: "stock": stock,
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

_INSTRUCCION_NO_MENCIONAR_STOCK = (
    "IMPORTANTE: NO menciones cantidades de stock al cliente. "
    "Si estado_stock='disponible' o 'bajo_stock', di solo: 'tenemos disponibilidad'. "
    "Si estado_stock='sin_stock', di: 'ese producto está agotado' y ofrece alternativa. "
    "Si estado_stock='servicio', es un servicio (no aplica stock). "
    "La cantidad exacta SIEMPRE la confirma el asesor humano."
)


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
        "productos":          productos,
        "total":              len(productos),
        "filtros":            {"query": query, "solo_disponibles": solo_disponibles, "categoria": categoria},
        "instruccion_agente": _INSTRUCCION_NO_MENCIONAR_STOCK,
    }


# ─────────────────────────────────────────────────────────────────────────
# Tool: consultar_stock
# ─────────────────────────────────────────────────────────────────────────

def consultar_stock(args: dict, context: dict) -> dict:
    """
    Devuelve el estado de disponibilidad de un producto (NO el número).
    Acepta `producto_id` (recId de Airtable) o `nombre` (match parcial).

    ⚠️ Esta tool NO devuelve la cantidad numérica de stock. Solo devuelve:
      - estado_stock: disponible / bajo_stock / sin_stock / servicio
      - hay_disponibilidad: boolean
      - instruccion_agente: recordatorio de no mencionar cantidades
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
                    "instruccion_agente": (
                        "Hay varios productos que coinciden. Pídele al cliente que "
                        "especifique cuál exactamente. NO menciones cantidades."
                    ),
                }
            producto = _normalize_producto(records[0])
    except AirtableError as e:
        return {"error": "interno", "detail": f"No se pudo leer producto: {e}"}

    estado = producto["estado_stock"]
    hay_disponibilidad = estado in ("disponible", "bajo_stock", "servicio")

    return {
        "encontrado":         True,
        "id":                 producto["id"],
        "nombre":             producto["nombre"],
        # ❌ ELIMINADO: "stock": producto["stock"],  (no exponer número)
        "estado_stock":       estado,
        "hay_disponibilidad": hay_disponibilidad,
        "precio":             producto["precio"],
        "instruccion_agente": _INSTRUCCION_NO_MENCIONAR_STOCK,
    }


# ─────────────────────────────────────────────────────────────────────────
# Tool: enviar_fotos_productos
# ─────────────────────────────────────────────────────────────────────────

# Cap de fotos por turno. WhatsApp permite mandar más, pero >6 fotos
# seguidas son spam para el cliente. Si el agent necesita mostrar más
# variedad, mejor pide contexto antes (color/marca) y manda otra tanda.
_MAX_FOTOS = 6


def enviar_fotos_productos(args: dict, context: dict) -> dict:
    """
    Manda hasta _MAX_FOTOS fotos de productos al cliente por WhatsApp.

    Mecánica:
      - Busca productos en Airtable (reusa `consultar_productos` para
        no duplicar la lógica de filtrado por query).
      - Filtra los que tengan `foto` no vacía.
      - Devuelve URLs en `_media_urls` (clave especial que captura el
        orquestador `openai_client.run_chat`). El handler de ventas
        las pasa en la response al bot-baileys, que las envía como
        imágenes nativas de WhatsApp.

    Args:
      query:        texto a buscar (nombre/desc/keywords/categoría).
      producto_ids: lista de recIds — si querés fotos específicas en
                    vez de una búsqueda libre.

    Sin `query` ni `producto_ids` → disponible:false (instrucción al
    agente para que llame con un query).
    """
    empresa_id = (context or {}).get("empresa_id")
    if not empresa_id:
        return {
            "disponible": False,
            "instruccion_agente": "Error interno: falta empresa_id en el context.",
        }

    query = (args or {}).get("query") or ""
    producto_ids = (args or {}).get("producto_ids") or []

    if not query and not producto_ids:
        return {
            "disponible": False,
            "instruccion_agente": (
                "Llamame de nuevo indicando qué fotos enviar. Pasame `query` "
                "(ej: 'cascos', 'guantes nitrilo') o `producto_ids` si ya "
                "tenés ids específicos."
            ),
        }

    # 1) Resolver lista de productos
    if query:
        result = consultar_productos(
            {"query": query, "solo_disponibles": True},
            context,
        )
        if "error" in result:
            return {
                "disponible": False,
                "instruccion_agente": (
                    f"No pude buscar productos en Airtable: "
                    f"{result.get('detail', 'error desconocido')}. "
                    "Decile al cliente que en un momento le mandás las opciones."
                ),
            }
        productos = result.get("productos", [])
    else:
        # Búsqueda por IDs explícitos. Cap defensivo de 20 IDs.
        productos = []
        for pid in (producto_ids or [])[:20]:
            try:
                rec = airtable_client.get_record(_TABLA_PRODUCTOS, pid)
            except AirtableError:
                continue
            if (rec.get("fields", {}) or {}).get("empresa_id") != empresa_id:
                continue  # cross-tenant guard
            productos.append(_normalize_producto(rec))

    # 2) Filtrar productos con foto
    con_foto = [p for p in productos if p.get("foto")]
    if not con_foto:
        return {
            "disponible": False,
            "instruccion_agente": (
                "No encontré productos con foto para ese pedido. "
                "Usá `consultar_productos` para listar opciones en texto."
            ),
        }

    # 3) Cap y armado de la respuesta
    seleccion = con_foto[:_MAX_FOTOS]

    return {
        "disponible":  True,
        "n_fotos":     len(seleccion),
        "fotos":       [
            {
                "nombre":  p.get("nombre"),
                "precio":  p.get("precio"),
                "url":     p.get("foto"),
            }
            for p in seleccion
        ],
        # Clave especial: el orquestador `openai_client.run_chat` la
        # captura y el handler la pasa al bot-baileys en `media_urls`
        # del response.
        "_media_urls": [p["foto"] for p in seleccion],
        "instruccion_agente": (
            f"Le estoy mandando {len(seleccion)} foto(s) al cliente por WhatsApp. "
            "Tu próximo mensaje debe ser BREVE — el cliente YA VE los nombres en "
            "las fotos. NO los listes uno por uno otra vez. En su lugar: invitá "
            "a elegir o pedí más contexto (color, marca, talla, certificación). "
            "Si mencionás precios, usá rango ('desde S/X'), no uno por uno."
        ),
    }


def enviar_catalogo(args: dict, context: dict) -> dict:
    """
    Devuelve el URL público del PDF del catálogo de la empresa para que el
    agent lo comparta con el cliente en su próximo mensaje. Lee la config
    `ventas.catalogo_pdf_url` (capa 7 — Conocimiento de marca) que ya
    viene en el `context` cargada por `sales_chat_post` — NO re-consultamos
    Airtable acá para evitar un round trip extra por turno.

    Patrón de respuesta:
      - Si hay URL configurado y activo:
          {"disponible": True, "url": "...", "instruccion_agente": "..."}
        El agent compone el mensaje natural con su voz y embebe el URL.
        WhatsApp genera preview automático del PDF.
      - Si no hay URL (activo:false o vacío):
          {"disponible": False, "instruccion_agente": "..."}
        El agent sigue con discovery normal (preguntas, consultar_productos).

    No postea al outbox directamente: el handler de ventas pone la `reply`
    final en el outbox como texto plano (incluyendo el URL).
    """
    ventas = (context or {}).get("ventas") or {}
    campo = ventas.get("catalogo_pdf_url") or {}
    activo = bool(campo.get("activo"))
    url = (campo.get("valor") or "").strip() if isinstance(campo.get("valor"), str) else ""

    if not activo or not url:
        return {
            "disponible": False,
            "instruccion_agente": (
                "La empresa no tiene un catálogo PDF cargado. NO inventes un URL. "
                "Seguí con discovery: preguntá qué tipo de producto busca, para qué lo "
                "necesita, o usá `consultar_productos` para listar opciones por categoría."
            ),
        }

    return {
        "disponible": True,
        "url": url,
        "instruccion_agente": (
            "Compartí este URL con el cliente en tu próximo mensaje, con tu tono natural "
            "de vendedor. Ejemplo: 'Acá te paso nuestro catálogo completo: <url>. "
            "Avísame si te interesa algo específico y vemos disponibilidad'. "
            "NO modifiques el URL. Después invitá al cliente a contarte qué le interesa."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# Definiciones para OpenAI function calling
# ─────────────────────────────────────────────────────────────────────────

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "consultar_productos",
            "description": (
                "Lista los productos del catálogo de la empresa. Úsala cuando el "
                "cliente pregunta '¿qué venden?', '¿tienen X?', 'cuánto cuesta…', "
                "'productos disponibles', etc. Devuelve nombre, precio, estado_stock "
                "(disponible/bajo_stock/sin_stock/servicio) y descripción. "
                "IMPORTANTE: NO devuelve cantidades numéricas — NO menciones stock "
                "específico al cliente, solo disponibilidad general."
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
                        "description": "Si True, excluye productos agotados.",
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
                "Devuelve la DISPONIBILIDAD (no la cantidad) de un producto específico. "
                "Úsala cuando el cliente pregunta '¿hay stock?', '¿está disponible?'. "
                "Acepta producto_id (recId interno) o nombre. Devuelve estado_stock "
                "y hay_disponibilidad (boolean). NUNCA devuelve el número de unidades."
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
    {
        "type": "function",
        "function": {
            "name": "enviar_fotos_productos",
            "description": (
                "Manda hasta 6 fotos de productos al cliente por WhatsApp (imágenes "
                "nativas, no URLs en texto). USALA cuando: (a) el cliente pregunta "
                "por una categoría general ('¿qué cascos tienen?', 'muéstrame guantes', "
                "'qué venden?'); (b) el cliente pide fotos explícitamente ('mándame "
                "fotos', 'imágenes', 'una foto del producto'). "
                "NO la uses si el cliente YA eligió un producto específico (ej: "
                "'quiero el casco MSA blanco' → confirmá con texto y avanzá a "
                "discovery, no spamees fotos). "
                "Después de invocarla tu mensaje de texto DEBE ser BREVE: el cliente "
                "YA ve los nombres en las fotos, no los repitas uno por uno."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Texto de búsqueda. Match parcial en nombre, descripción, "
                            "keywords y categoría. Ej: 'cascos', 'guantes nitrilo', 'lentes uv'."
                        ),
                    },
                    "producto_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Lista de recIds de Airtable si querés fotos de productos "
                            "específicos (por ejemplo, los IDs que devolvió "
                            "`consultar_productos` antes). Si pasás esto, ignorá `query`."
                        ),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_catalogo",
            "description": (
                "Comparte el PDF del catálogo de la empresa con el cliente. "
                "REGLA DURA: usá esta tool UNA SOLA VEZ por conversación. Si ya la "
                "invocaste antes en el historial, NO la vuelvas a invocar. "
                "REGLA DURA: NO la uses si el cliente ya mencionó un producto, marca o "
                "categoría específica — para eso usá `consultar_productos`. "
                "Ejemplos de cuándo NO usarla (usá `consultar_productos` en su lugar): "
                "'¿cuánto cuestan los cascos?', 'necesito guantes', '¿tienen botas de "
                "seguridad?', '¿precio del taladro DeWalt?'. "
                "Ejemplos de cuándo SÍ usarla: '¿qué venden?', 'mándame el catálogo', "
                "'mándame la lista', '¿qué tienen?' (sin mencionar producto), o después "
                "de 1-2 preguntas de discovery el cliente sigue sin poder describir qué "
                "necesita. "
                "Si la empresa no tiene catálogo cargado, la tool devuelve "
                "`disponible:false` — en ese caso NO menciones que ibas a mandarlo, "
                "seguí con discovery normal."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# Dispatcher (lo usa /api/sales_chat para ejecutar la tool que el LLM eligió)
_HANDLERS = {
    "consultar_productos":     consultar_productos,
    "consultar_stock":         consultar_stock,
    "enviar_fotos_productos":  enviar_fotos_productos,
    "enviar_catalogo":         enviar_catalogo,
}


def execute(name: str, args: dict, context: dict) -> dict:
    """Ejecuta una tool de ventas. Devuelve dict serializable a JSON."""
    handler = _HANDLERS.get(name)
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