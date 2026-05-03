"""
Loader de configuración multi-tenant en 2 capas:

  • Estática  → src/tenants/<TENANT_ID>/config.json   (identidad, módulos, branding)
  • Dinámica  → tablas Config_* en Airtable           (reglas de negocio editables)

`load_full_config()` combina ambas en el dict final que consumirá el
`prompt_builder` y demás módulos del backend.

Cache: en memoria, TTL 300s. El cold start lo resetea (esperado en serverless).
"""

import json
import os
import sys
import time

from . import airtable_client
from .airtable_client import AirtableError


# ─────────────────────────────────────────────────────────────────────────
# Resolución de rutas
# ─────────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))                # api/_lib
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))     # repo root
_TENANTS_DIR = os.path.join(_REPO_ROOT, "src", "tenants")

_FALLBACK_TENANT = "cmejia"


# ─────────────────────────────────────────────────────────────────────────
# Cache de la config dinámica
# ─────────────────────────────────────────────────────────────────────────
_cache = {"data": None, "expires_at": 0.0}
_CACHE_TTL_SECONDS = 300


def _get_tenant_id() -> str:
    """Lee TENANT_ID del entorno; si falta, usa el fallback con warning."""
    tenant_id = os.environ.get("TENANT_ID")
    if not tenant_id:
        print(
            f"[config_loader] TENANT_ID no seteado. Usando fallback '{_FALLBACK_TENANT}'.",
            file=sys.stderr,
        )
        return _FALLBACK_TENANT
    return tenant_id


# ─────────────────────────────────────────────────────────────────────────
# Capa 1-2: estática (identidad / capacidades)
# ─────────────────────────────────────────────────────────────────────────
def load_static_config() -> dict:
    """
    Lee y devuelve src/tenants/<TENANT_ID>/config.json.
    Si el archivo del tenant no existe, cae al fallback.
    """
    tenant_id = _get_tenant_id()
    path = os.path.join(_TENANTS_DIR, tenant_id, "config.json")

    if not os.path.exists(path):
        print(
            f"[config_loader] No existe {path}. Usando fallback '{_FALLBACK_TENANT}'.",
            file=sys.stderr,
        )
        path = os.path.join(_TENANTS_DIR, _FALLBACK_TENANT, "config.json")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────
# Capa 4: dinámica (reglas de negocio en Airtable)
# ─────────────────────────────────────────────────────────────────────────
def _cast(valor, tipo: str | None):
    """
    Castea el valor (que viene como string) según el `tipo` declarado en
    Config_Procesos. Tipos soportados: int, float, bool, str (default).
    Si el cast falla, devuelve el valor original como string.
    """
    if valor is None:
        return None
    tipo = (tipo or "str").strip().lower()
    raw = str(valor).strip()
    if tipo == "int":
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None
    if tipo == "float":
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None
    if tipo == "bool":
        return raw.lower() in ("true", "1", "yes", "sí", "si", "on")
    return raw


def _safe_list(table: str, filter_formula: str) -> list[dict]:
    """
    Wrapper que intenta listar una tabla y, si falla (404 porque no existe
    aún, o error de red), devuelve [] con un warning a stderr. El skeleton
    debe poder correr aunque las tablas no estén creadas todavía.
    """
    try:
        return airtable_client.list_records(table, filter_formula=filter_formula)
    except AirtableError as e:
        print(
            f"[config_loader] No se pudo leer la tabla '{table}' "
            f"(status={e.status}). Usando lista vacía. Detalle: {e}",
            file=sys.stderr,
        )
        return []


def load_dynamic_config() -> dict:
    """
    Lee las tablas Config_* desde Airtable filtradas por empresa_id == TENANT_ID.

    Devuelve un dict por proceso con la forma:
        {
          "caja_chica": {
            "<clave>": <valor casteado>,
            ...
            "aprobadores": [{...fields}],
          }
        }

    Cache TTL 300s. Llamadas siguientes dentro del TTL no tocan Airtable.
    """
    now = time.time()
    if _cache["data"] is not None and _cache["expires_at"] > now:
        return _cache["data"]

    tenant_id = _get_tenant_id()
    formula = f"{{empresa_id}}='{tenant_id}'"

    # 1) Config_Procesos: rows escalares (clave/valor/tipo) por proceso
    config_rows = _safe_list("Config_Procesos", formula)

    procesos: dict[str, dict] = {}
    for row in config_rows:
        f = row.get("fields", {})
        proceso = f.get("proceso")
        clave = f.get("clave")
        if not proceso or not clave:
            continue
        valor_casteado = _cast(f.get("valor"), f.get("tipo"))
        procesos.setdefault(proceso, {})[clave] = valor_casteado

    # 2) Aprobadores: agrupados por proceso
    aprobadores_rows = _safe_list("Aprobadores", formula)
    for row in aprobadores_rows:
        f = row.get("fields", {})
        proceso = f.get("proceso")
        if not proceso:
            continue
        procesos.setdefault(proceso, {}).setdefault("aprobadores", []).append(f)

    # Aseguramos que caja_chica exista aunque Config_Procesos esté vacío:
    procesos.setdefault("caja_chica", {})

    # 3) Empleados con rol de aprobador (leídos de la tabla Empleados)
    # Filtramos donde APROBADORES no esté vacío
    empleados_rows = _safe_list("Empleados", "NOT({APROBADORES} = '')")
    aprobador_1 = []
    aprobador_2 = []
    for row in empleados_rows:
        f = row.get("fields", {})
        roles = f.get("APROBADORES")
        if not roles:
            continue
        if isinstance(roles, str):
            roles = [roles]
        
        info = {
            "id": row.get("id"),
            "nombre": f.get("NOMBRE CORTO", "Desconocido")
        }
        
        if "APROBADOR_1" in roles:
            aprobador_1.append(info)
        if "APROBADOR_2" in roles:
            aprobador_2.append(info)

    procesos["caja_chica"]["lista_aprobador_1"] = aprobador_1
    procesos["caja_chica"]["lista_aprobador_2"] = aprobador_2

    for proceso_dict in procesos.values():
        proceso_dict.setdefault("aprobadores", [])

    _cache["data"] = procesos
    _cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return procesos


# ─────────────────────────────────────────────────────────────────────────
# Empresa.info_extendida — defaults y deep merge
# ─────────────────────────────────────────────────────────────────────────

# Schema fijo. Cada campo: {activo: bool, valor: <tipo>}. Los toggles arrancan
# en false → el prompt no los menciona (compat backward total con tenants
# existentes que no definen este bloque).
_INFO_EXTENDIDA_SCHEMA = {
    "rubro":            "",
    "descripcion":      "",
    "direccion":        "",
    "email_contacto":   "",
    "horario_atencion": "",
    "redes_sociales":   [],  # array de {red, url}
}


def _default_empresa_info_extendida() -> dict:
    """Devuelve el shape default con todos los toggles en false."""
    return {
        key: {"activo": False, "valor": _clone_default(default_valor)}
        for key, default_valor in _INFO_EXTENDIDA_SCHEMA.items()
    }


def _clone_default(v):
    """Copia profunda de los defaults primitivos del schema."""
    if isinstance(v, list):
        return list(v)
    if isinstance(v, dict):
        return dict(v)
    return v


def _merge_info_extendida(provided: dict | None) -> dict:
    """
    Deep merge entre los defaults y lo que venga del tenant. Lo que provee
    el tenant gana; campos faltantes quedan default. Campos extra que NO
    están en el schema se ignoran silenciosamente (no fallar).
    """
    merged = _default_empresa_info_extendida()
    if not isinstance(provided, dict):
        return merged
    for key in _INFO_EXTENDIDA_SCHEMA:
        if key not in provided:
            continue
        incoming = provided[key]
        if not isinstance(incoming, dict):
            continue  # malformado, dejamos default
        # Merge campo por campo dentro de cada toggle
        if "activo" in incoming:
            merged[key]["activo"] = bool(incoming["activo"])
        if "valor" in incoming:
            merged[key]["valor"] = incoming["valor"]
    return merged


# ─────────────────────────────────────────────────────────────────────────
# Ventas — defaults, deep merge y carga dinámica
# ─────────────────────────────────────────────────────────────────────────

# Enums permitidos para validación. Lo importan tanto el endpoint POST
# (api/ventas.py?resource=config) como tests de regression.
VENTAS_ENUMS = {
    "estilo_vendedor":      {"formal_profesional", "cercano_amigable", "tecnico_consultivo", "casual_directo"},
    "tipo_cliente":          {"b2b", "b2c", "mixto"},
    "metodos_pago":          {"efectivo", "yape_plin", "transferencia", "tarjeta_pos", "tarjeta_online", "credito_empresarial", "contra_entrega"},
    "politica_precios.igv":  {"incluido", "no_incluido", "referencial"},
    "politica_precios.comprobantes": {"boleta", "factura", "ambos"},
    "criterios_derivacion":  {"cotizacion_formal", "descuento_negociacion", "modificar_pedido", "queja_reclamo", "fuera_catalogo", "menciona_competencia", "intencion_compra", "conversacion_larga"},
    "horario_ia":            {"24_7", "solo_horario_atencion"},
    "info_adicional.categoria": {"faq", "promocion", "servicio_adicional", "info_importante", "politica"},
}

INFO_ADICIONAL_MAX = 20


def _default_ventas_config() -> dict:
    """Shape default del bloque ventas. Todos los toggles arrancan en false."""
    return {
        "estilo_vendedor":      {"activo": False, "valor": "formal_profesional"},
        "nombre_vendedor":      {"activo": False, "valor": ""},
        "tipo_cliente":         {"activo": False, "valor": "mixto"},
        "zona_cobertura":       {"activo": False, "valor": ""},
        "tiempo_entrega":       {"activo": False, "valor": ""},
        "metodos_pago":         {"activo": False, "valor": []},
        "politica_precios":     {"activo": False, "valor": {"igv": "incluido", "comprobantes": "ambos"}},
        "asesor_humano":        {"activo": False, "valor": {"nombre": "", "telefono": ""}},
        "criterios_derivacion": {"activo": False, "valor": []},
        "horario_ia":           {"activo": False, "valor": "24_7"},
        "info_adicional":       {"activo": False, "valor": []},
    }


def _merge_ventas_config(provided: dict | None) -> dict:
    """
    Deep merge defaults ← provided. Los campos del shape sobrescriben sus
    defaults con lo que venga; campos no definidos en el schema se ignoran.
    El sub-dict 'valor' se reemplaza completo (no merge campo-a-campo dentro
    del valor) para mantener el shape consistente.
    """
    merged = _default_ventas_config()
    if not isinstance(provided, dict):
        return merged
    for key, default_field in merged.items():
        incoming = provided.get(key)
        if not isinstance(incoming, dict):
            continue
        if "activo" in incoming:
            default_field["activo"] = bool(incoming["activo"])
        if "valor" in incoming:
            default_field["valor"] = incoming["valor"]
    return merged


def _load_ventas_dynamic(tenant_id: str) -> dict | None:
    """
    Lee el bloque ventas desde la tabla `Config_Ventas` (1 fila por tenant).
    Schema esperado: empresa_id (single line text) + data (long text JSON).
    Si la tabla aún no existe, devolvemos None sin error.
    """
    rows = _safe_list("Config_Ventas", f"{{empresa_id}}='{tenant_id}'")
    if not rows:
        return None
    row = rows[0].get("fields", {})
    raw = row.get("data") or row.get("ventas")
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, ValueError) as e:
        print(
            f"[config_loader] Config_Ventas.data tiene JSON inválido: {e}",
            file=sys.stderr,
        )
        return None


def _load_info_extendida_dynamic(tenant_id: str) -> dict | None:
    """
    Lee `info_extendida` desde Airtable si existe la tabla `Config_Empresa_Info`.
    Hoy esta tabla puede no existir aún; en ese caso devolvemos None (sin error).

    Schema esperado (1 fila por tenant):
      • empresa_id (single line text)
      • data       (long text con JSON serializado de info_extendida)

    TODO: si en el futuro se prefiere columnas individuales en lugar de un
    JSON blob, ajustar acá.
    """
    rows = _safe_list("Config_Empresa_Info", f"{{empresa_id}}='{tenant_id}'")
    if not rows:
        return None
    row = rows[0].get("fields", {})
    raw = row.get("data") or row.get("info_extendida")
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, ValueError) as e:
        print(
            f"[config_loader] Config_Empresa_Info.data tiene JSON inválido: {e}",
            file=sys.stderr,
        )
        return None


# ─────────────────────────────────────────────────────────────────────────
# Cache management
# ─────────────────────────────────────────────────────────────────────────

def invalidate_cache() -> None:
    """Fuerza el reload del cache en la próxima llamada a load_dynamic_config()."""
    _cache["data"] = None
    _cache["expires_at"] = 0.0


# ─────────────────────────────────────────────────────────────────────────
# Combinada (estática + dinámica)
# ─────────────────────────────────────────────────────────────────────────
def _merge_proceso(static_proceso: dict, dynamic_proceso: dict) -> dict:
    """
    Combina los procesos del config estático (defaults por tenant) con
    los del dinámico (Airtable). El dinámico sobreescribe clave a clave.

    Cada `proceso` (ej. 'caja_chica') es un dict de claves individuales
    (flags, números, listas). Hacemos shallow merge: las claves del
    dinámico ganan sobre las del estático.
    """
    combined: dict[str, dict] = {}
    # Defaults estáticos
    for proc_name, proc_data in (static_proceso or {}).items():
        combined[proc_name] = dict(proc_data) if isinstance(proc_data, dict) else {}
    # Dinámico sobreescribe / agrega
    for proc_name, proc_data in (dynamic_proceso or {}).items():
        if proc_name in combined and isinstance(proc_data, dict):
            combined[proc_name].update(proc_data)
        else:
            combined[proc_name] = proc_data
    return combined


def load_full_config() -> dict:
    """
    Devuelve la config completa con la forma:

        {
          "empresa": {
            "id", "razon_social", "ruc", "sistema_contable",
            "agent": {...}, "modules": [...]
          },
          "proceso": {
            "caja_chica": {
              "<clave>": <valor>, ...,
              "aprobadores": [...]
            }
          }
        }

    `proceso` es un MERGE entre el config estático del tenant
    (`tenants/<id>/config.json` → `proceso.<nombre>`) y el dinámico
    (Airtable). Esto permite que el config estático provea defaults
    razonables mientras `Config_Procesos` no exista en Airtable, y
    cuando exista, sus valores ganan automáticamente.
    """
    static = load_static_config()
    dynamic = load_dynamic_config()

    # info_extendida: deep merge defaults ← static ← dynamic.
    # 1. Defaults (todos apagados)
    # 2. static.empresa.info_extendida del config.json
    # 3. Airtable (Config_Empresa_Info) si existe — gana sobre static.
    static_info = (static.get("empresa", {}) or {}).get("info_extendida") \
        or static.get("info_extendida")  # tolerar shape legacy en root
    info_extendida = _merge_info_extendida(static_info)
    dynamic_info = _load_info_extendida_dynamic(_get_tenant_id())
    if dynamic_info:
        info_extendida = _merge_info_extendida({**info_extendida, **dynamic_info})

    empresa = {
        "id": static.get("id"),
        # name/razon_social/ruc/sistema_contable salieron del config.json en el
        # paso 5; el frontend los inyecta vía body.empresa_context. Defaults
        # vacíos aquí mantienen compat con cualquier código que lea el shape.
        "name": static.get("name", ""),
        "razon_social": static.get("razonSocial", ""),
        "ruc": static.get("ruc", ""),
        "sistema_contable": static.get("sistemaContable", "concar"),
        "agent": static.get("agent", {}),
        "modules": static.get("modules", []),
        "info_extendida": info_extendida,
    }

    proceso = _merge_proceso(
        static.get("proceso", {}) or {},
        dynamic or {},
    )

    # ventas: deep merge defaults ← static (config.json) ← dynamic (Airtable).
    static_ventas = static.get("ventas")
    ventas_block = _merge_ventas_config(static_ventas)
    dynamic_ventas = _load_ventas_dynamic(_get_tenant_id())
    if dynamic_ventas:
        # mezclar lo dinámico encima de lo ya mergeado
        ventas_block = _merge_ventas_config({**ventas_block, **dynamic_ventas})

    return {
        "empresa": empresa,
        "proceso": proceso,
        "ventas":  ventas_block,
    }
