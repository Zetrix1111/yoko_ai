"""
api/_lib/yoko_cart_store.py

Carrito de archivos persistente en Vercel KV (Upstash) por session_id.

Resuelve el bug de que los attachments del chat web vivían solo en la
request donde se subían: cuando el agent decidía invocar
`yoko_procesar_archivos` en un turno posterior, el orquestador ya no
tenía los archivos.

Layout en KV (una key por archivo + un índice — esquiva el límite de
~1MB/value de Upstash y permite cargar selectivamente):

  yoko:cart:{session_id}:index       → JSON ["uuid1", "uuid2", ...]
  yoko:cart:{session_id}:file:{uuid} → JSON {"filename": "...", "content_b64": "..."}

API pública:
  - `add_files(session_id, files) -> int`     → append, devuelve total
  - `get_files(session_id) -> list[dict]`     → array completo en orden
  - `clear_cart(session_id) -> int`           → borra todo, devuelve count
  - `cart_size(session_id) -> int`            → solo cuenta, no lee files

TTL: 4 hrs deslizante (mismo que yoko_session_store). Cada operación de
read/write renueva el TTL en TODAS las keys del carrito.
"""

import json
import sys
import uuid

from . import kv_client


SESSION_TTL_SECONDS = 4 * 60 * 60  # 4 horas

_INDEX_KEY_TPL = "yoko:cart:{session_id}:index"
_FILE_KEY_TPL  = "yoko:cart:{session_id}:file:{uuid}"


def _index_key(session_id: str) -> str:
    return _INDEX_KEY_TPL.format(session_id=session_id)


def _file_key(session_id: str, file_uuid: str) -> str:
    return _FILE_KEY_TPL.format(session_id=session_id, uuid=file_uuid)


def _read_index(session_id: str) -> list[str]:
    """Lee el array de uuids del índice. Devuelve [] si no existe o JSON inválido."""
    raw = kv_client.kv_get(_index_key(session_id))
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(u) for u in data]
    except json.JSONDecodeError:
        print(
            f"[yoko_cart_store] índice corrupto para {session_id}, reseteando",
            file=sys.stderr,
        )
    return []


def _write_index(session_id: str, uuids: list[str]) -> bool:
    return kv_client.kv_set(
        _index_key(session_id),
        json.dumps(uuids, ensure_ascii=False),
        ttl_seconds=SESSION_TTL_SECONDS,
    )


def _renew_all_ttls(session_id: str, uuids: list[str]) -> None:
    """Renueva el TTL del índice y de cada file. Ignora fallas silenciosamente."""
    try:
        kv_client.kv_expire(_index_key(session_id), SESSION_TTL_SECONDS)
        for u in uuids:
            kv_client.kv_expire(_file_key(session_id, u), SESSION_TTL_SECONDS)
    except kv_client.KVError as e:
        print(f"[yoko_cart_store] no se pudo renovar TTL: {e}", file=sys.stderr)


def add_files(session_id: str, files: list[dict]) -> int:
    """
    Append a la lista. Cada `file` debe tener al menos `filename` y
    `content_b64`. Genera un uuid por archivo.

    Devuelve el total acumulado (existentes + agregados) tras la operación.
    """
    if not session_id or not files:
        return cart_size(session_id) if session_id else 0

    index = _read_index(session_id)
    new_uuids: list[str] = []

    for f in files:
        if not isinstance(f, dict):
            continue
        filename = str(f.get("filename") or "").strip()
        content_b64 = str(f.get("content_b64") or "").strip()
        if not filename or not content_b64:
            continue
        u = uuid.uuid4().hex[:12]
        payload = json.dumps(
            {"filename": filename, "content_b64": content_b64},
            ensure_ascii=False,
        )
        if not kv_client.kv_set(
            _file_key(session_id, u), payload, ttl_seconds=SESSION_TTL_SECONDS
        ):
            print(
                f"[yoko_cart_store] kv_set falló para file {u} de {session_id}",
                file=sys.stderr,
            )
            continue
        new_uuids.append(u)

    if new_uuids:
        index.extend(new_uuids)
        _write_index(session_id, index)
    else:
        # Renovamos TTL aunque no agreguemos nada (mantiene vivo el carrito).
        _renew_all_ttls(session_id, index)

    return len(index)


def get_files(session_id: str, renew_ttl: bool = False) -> list[dict]:
    """
    Devuelve todos los archivos del carrito en orden de inserción.
    Cada elemento es `{filename, content_b64}`.

    Usa MGET (Redis pipelining) para leer N archivos en 1 round trip:
    25 archivos pasa de ~3s (N+1 GETs) a ~150ms.

    `renew_ttl` por defecto FALSE porque el caso de uso típico
    (worker que va a procesar y después llama clear_cart) no necesita
    extender la vida del carrito — se va a borrar enseguida. Pasar True
    cuando se quiere mantener el carrito vivo después de leer (ej:
    chequeos intermedios). Cada renew agrega ~100ms × N round trips,
    así que evitarlo en el path crítico es importante.
    """
    if not session_id:
        return []
    index = _read_index(session_id)
    if not index:
        return []

    file_keys = [_file_key(session_id, u) for u in index]
    try:
        raws = kv_client.kv_mget(file_keys)
    except kv_client.KVError as e:
        print(
            f"[yoko_cart_store] kv_mget falló para {session_id}: {e}",
            file=sys.stderr,
        )
        return []

    files: list[dict] = []
    surviving_uuids: list[str] = []
    for u, raw in zip(index, raws):
        if not raw:
            # File expiró individualmente (no debería pasar con TTLs sincronizados)
            # o no existe. Lo dropeamos del índice.
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("filename") and data.get("content_b64"):
                files.append({
                    "filename":    data["filename"],
                    "content_b64": data["content_b64"],
                })
                surviving_uuids.append(u)
        except json.JSONDecodeError:
            print(
                f"[yoko_cart_store] file corrupto {u} en {session_id}, dropeando",
                file=sys.stderr,
            )

    # Si dropeamos algún uuid, reescribimos el índice para que no se acumulen huérfanos.
    if len(surviving_uuids) != len(index):
        _write_index(session_id, surviving_uuids)
    elif renew_ttl:
        # Solo renovamos TTL si el caller lo pide explicitamente. Cada
        # EXPIRE es un round trip a Upstash; con 25 archivos son 26 calls
        # ≈ 2-3s, dominando el costo del get_files. El path típico
        # (worker → get_files → clear_cart) NO necesita esto.
        _renew_all_ttls(session_id, surviving_uuids)

    return files


def clear_cart(session_id: str) -> int:
    """
    Borra el índice y todos los archivos del carrito. Devuelve cuántos
    archivos había. Idempotente: si no hay carrito, devuelve 0.
    """
    if not session_id:
        return 0
    index = _read_index(session_id)
    count = len(index)
    for u in index:
        kv_client.kv_delete(_file_key(session_id, u))
    kv_client.kv_delete(_index_key(session_id))
    return count


def cart_size(session_id: str) -> int:
    """Cuenta liviana (solo lee el índice, no los archivos). Renueva TTL del índice."""
    if not session_id:
        return 0
    index = _read_index(session_id)
    if index:
        try:
            kv_client.kv_expire(_index_key(session_id), SESSION_TTL_SECONDS)
        except kv_client.KVError:
            pass
    return len(index)
