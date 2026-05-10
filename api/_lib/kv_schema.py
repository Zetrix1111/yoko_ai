"""
api/_lib/kv_schema.py

Centraliza el naming scheme de las keys que el cerebro Managed Agents
(Yoko) graba en Vercel KV. Antes los prefijos vivían hardcodeados en
3 stores distintos (yoko_session_store, yoko_task_store, yoko_cart_store)
y cualquier renombre requería tocar los tres a mano.

Convención:
  yoko:<dominio>[:<sub>][:<id>]...

Dominios definidos:
  yoko:task:<task_id>                       — task async del chat
  yoko:session:<empresa_id>:<user_id>       — session_id de Anthropic
  yoko:session_meta:<session_id>            — metadata de la session
  yoko:cart:<session_id>:index              — índice del carrito
  yoko:cart:<session_id>:file:<file_uuid>   — archivo individual

Reglas:
  - NO interpolar manualmente prefijos en otros módulos. Importar el
    factory que corresponde y delegarle el armado.
  - Si necesitás un dominio nuevo, agregalo acá Y al docstring de
    arriba (es la única documentación viva del schema completo).
  - Los argumentos no se sanitizan: el caller es responsable de pasar
    valores ya validados (slug, dni, uuid) — Upstash no impone
    restricciones de caracteres relevantes para nuestros casos.
"""

# Prefijos por dominio. Si renombrás un prefijo acá, cambia para todos
# los stores en simultáneo — es justamente el invariante que queremos.
_PREFIX_TASK            = "yoko:task"
_PREFIX_SESSION         = "yoko:session"
_PREFIX_SESSION_META    = "yoko:session_meta"
_PREFIX_CART            = "yoko:cart"


def task_key(task_id: str) -> str:
    """Key del task async (status pending/running/done/error)."""
    return f"{_PREFIX_TASK}:{task_id}"


def session_key(empresa_id: str, user_id: str) -> str:
    """Key de la session_id cacheada por (empresa_id, user_id)."""
    return f"{_PREFIX_SESSION}:{empresa_id}:{user_id}"


def session_metadata_key(session_id: str) -> str:
    """Key de la metadata de la session (lookup inverso desde session_id)."""
    return f"{_PREFIX_SESSION_META}:{session_id}"


def cart_index_key(session_id: str) -> str:
    """Key del índice del carrito de archivos (lista ordenada de uuids)."""
    return f"{_PREFIX_CART}:{session_id}:index"


def cart_file_key(session_id: str, file_uuid: str) -> str:
    """Key de un archivo individual del carrito (filename + content_b64)."""
    return f"{_PREFIX_CART}:{session_id}:file:{file_uuid}"
