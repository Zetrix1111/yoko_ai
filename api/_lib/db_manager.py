"""
api/_lib/db_manager.py

Gestor de base de datos SQLite para almacenamiento temporal de facturas.

Los datos se guardan en /tmp/facturas.db (Vercel serverless, Linux).
Cada registro contiene una factura serializada en JSON.
Los registros se limpian automáticamente después de 24 horas.

IMPORTANTE: En Vercel, /tmp es ephemero — se reinicia en cada cold start
y NO se comparte entre instancias del mismo function pool. Esta DB es
"best-effort cache" para la sesión activa de un usuario que cae en la
misma instancia. localStorage del frontend es el backup principal.

Funciones:
- init_db(): Crea la tabla y los índices si no existen
- save_proceso(): Guarda todas las facturas de un proceso
- get_proceso(): Recupera todas las facturas de un proceso
- update_factura(): Actualiza una factura específica
- delete_factura(): Elimina una factura específica
- delete_proceso(): Elimina un proceso completo
- cleanup_old_records(): Limpia registros antiguos (>24h)
- get_db_stats(): Stats para debugging/monitoreo
"""

import json
import os
import sqlite3
import sys
import time
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────────────

DB_PATH = "/tmp/facturas.db"
RETENTION_HOURS = 24  # Mantener datos por 24 horas


# ─────────────────────────────────────────────────────────────────────────
# Inicialización y schema
# ─────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Crea la tabla y los índices si no existen. Idempotente — seguro de
    llamar al inicio de cada request. También dispara cleanup_old_records
    para mantener /tmp acotado.

    Schema:
      - id            INTEGER PK auto-increment
      - proceso_id    TEXT  identificador del proceso
      - empresa_id    TEXT  multi-tenant (del JWT)
      - factura_id    TEXT  UUID único de la factura
      - factura_json  TEXT  objeto completo serializado en JSON
      - created_at    REAL  Unix epoch de creación
      - updated_at    REAL  Unix epoch de última modificación
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procesos_facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proceso_id TEXT NOT NULL,
                empresa_id TEXT NOT NULL,
                factura_id TEXT NOT NULL,
                factura_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(proceso_id, factura_id)
            )
        """)

        # Índice para búsquedas por (proceso_id, empresa_id) — query principal.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_proceso_empresa
            ON procesos_facturas(proceso_id, empresa_id)
        """)

        # Índice para limpieza automática.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at
            ON procesos_facturas(created_at)
        """)

        conn.commit()
        conn.close()

        cleanup_old_records()

    except Exception as e:
        print(f"[db_manager] Error inicializando DB: {e}", file=sys.stderr)
        # No lanzar excepción — degradar gracefully.


def cleanup_old_records() -> None:
    """Elimina registros con más de RETENTION_HOURS horas de antigüedad."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cutoff_time = time.time() - (RETENTION_HOURS * 3600)
        cursor.execute(
            "DELETE FROM procesos_facturas WHERE created_at < ?",
            (cutoff_time,),
        )

        deleted = cursor.rowcount
        if deleted > 0:
            print(
                f"[db_manager] Limpieza automática: {deleted} registros eliminados",
                file=sys.stderr,
            )

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[db_manager] Error en cleanup: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────
# CRUD: Crear
# ─────────────────────────────────────────────────────────────────────────

def save_proceso(proceso_id: str, empresa_id: str, facturas: List[Dict]) -> None:
    """
    Guarda todas las facturas de un proceso. Si una factura con el mismo
    (proceso_id, factura_id) ya existe, se reemplaza (INSERT OR REPLACE).

    Lanza excepción si hay error de DB; el caller decide cómo manejarlo.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        timestamp = time.time()

        for factura in facturas:
            factura_id = factura.get("id")
            if not factura_id:
                print(
                    f"[db_manager] Factura sin ID, saltando: {factura.get('archivo_nombre')}",
                    file=sys.stderr,
                )
                continue

            factura_json = json.dumps(factura, ensure_ascii=False)

            cursor.execute(
                """
                INSERT OR REPLACE INTO procesos_facturas
                (proceso_id, empresa_id, factura_id, factura_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (proceso_id, empresa_id, factura_id, factura_json, timestamp, timestamp),
            )

        conn.commit()
        conn.close()

        print(
            f"[db_manager] Guardadas {len(facturas)} facturas para proceso {proceso_id}",
            file=sys.stderr,
        )

    except Exception as e:
        print(f"[db_manager] Error guardando proceso: {e}", file=sys.stderr)
        raise


# ─────────────────────────────────────────────────────────────────────────
# CRUD: Leer
# ─────────────────────────────────────────────────────────────────────────

def get_proceso(proceso_id: str, empresa_id: str) -> Optional[Dict]:
    """
    Recupera todas las facturas de un proceso. Cross-tenant guard: si
    proceso_id existe pero empresa_id no coincide → retorna None.

    Returns:
        {"facturas": [...], "timestamp": float} o None si no existe.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT factura_json, created_at
            FROM procesos_facturas
            WHERE proceso_id = ? AND empresa_id = ?
            ORDER BY id ASC
            """,
            (proceso_id, empresa_id),
        )

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        facturas = [json.loads(row[0]) for row in rows]
        timestamp = rows[0][1]  # todas se insertan con el mismo created_at

        return {"facturas": facturas, "timestamp": timestamp}

    except Exception as e:
        print(f"[db_manager] Error recuperando proceso: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────────────
# CRUD: Actualizar
# ─────────────────────────────────────────────────────────────────────────

def update_factura(proceso_id: str, empresa_id: str, factura: Dict) -> bool:
    """
    Actualiza una factura específica. Devuelve True si se modificó alguna
    fila, False si no se encontró match (proceso_id + empresa_id + factura_id).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        factura_id = factura.get("id")
        if not factura_id:
            print("[db_manager] update_factura: factura sin ID", file=sys.stderr)
            return False

        factura_json = json.dumps(factura, ensure_ascii=False)
        timestamp = time.time()

        cursor.execute(
            """
            UPDATE procesos_facturas
            SET factura_json = ?, updated_at = ?
            WHERE proceso_id = ? AND empresa_id = ? AND factura_id = ?
            """,
            (factura_json, timestamp, proceso_id, empresa_id, factura_id),
        )

        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if updated:
            print(
                f"[db_manager] Actualizada factura {factura_id} en proceso {proceso_id}",
                file=sys.stderr,
            )
        return updated

    except Exception as e:
        print(f"[db_manager] Error actualizando factura: {e}", file=sys.stderr)
        return False


# ─────────────────────────────────────────────────────────────────────────
# CRUD: Eliminar
# ─────────────────────────────────────────────────────────────────────────

def delete_factura(proceso_id: str, empresa_id: str, factura_id: str) -> bool:
    """Elimina una factura del proceso. True si borró 1 fila, False si no encontró."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM procesos_facturas
            WHERE proceso_id = ? AND empresa_id = ? AND factura_id = ?
            """,
            (proceso_id, empresa_id, factura_id),
        )

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            print(
                f"[db_manager] Eliminada factura {factura_id} de proceso {proceso_id}",
                file=sys.stderr,
            )
        return deleted

    except Exception as e:
        print(f"[db_manager] Error eliminando factura: {e}", file=sys.stderr)
        return False


def delete_proceso(proceso_id: str, empresa_id: str) -> int:
    """
    Elimina un proceso completo con todas sus facturas. Devuelve cantidad
    de facturas eliminadas (0 si no existía o no era del tenant).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM procesos_facturas
            WHERE proceso_id = ? AND empresa_id = ?
            """,
            (proceso_id, empresa_id),
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            print(
                f"[db_manager] Eliminado proceso {proceso_id}: {deleted} facturas",
                file=sys.stderr,
            )
        return deleted

    except Exception as e:
        print(f"[db_manager] Error eliminando proceso: {e}", file=sys.stderr)
        return 0


# ─────────────────────────────────────────────────────────────────────────
# Funciones auxiliares — debugging / monitoreo
# ─────────────────────────────────────────────────────────────────────────

def get_db_stats() -> Dict:
    """
    Stats de la DB: cantidad de registros, procesos únicos, empresas únicas,
    tamaño en bytes, timestamp del registro más antiguo.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM procesos_facturas")
        total_records = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT proceso_id) FROM procesos_facturas")
        total_procesos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT empresa_id) FROM procesos_facturas")
        total_empresas = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(created_at) FROM procesos_facturas")
        oldest = cursor.fetchone()[0]

        conn.close()

        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

        return {
            "total_records":  total_records,
            "total_procesos": total_procesos,
            "total_empresas": total_empresas,
            "db_size_bytes":  db_size,
            "oldest_record":  oldest,
        }

    except Exception as e:
        print(f"[db_manager] Error obteniendo stats: {e}", file=sys.stderr)
        return {
            "total_records":  0,
            "total_procesos": 0,
            "total_empresas": 0,
            "db_size_bytes":  0,
            "oldest_record":  None,
        }
