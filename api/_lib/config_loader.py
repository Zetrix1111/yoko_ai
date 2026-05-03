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
# TTL bajo (60s) para que los cambios desde la UI se reflejen rápido sin
# saturar Airtable. Los POST de /api/config llaman invalidate_cache()
# explícitamente, así que el caso normal es instantáneo.
_cache = {"data": None, "expires_at": 0.0}            # legacy (load_dynamic_config)
_full_cache = {"data": None, "expires_at": 0.0}       # paso 6 (load_full_config)
_CACHE_TTL_SECONDS = 60


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


def _load_data_blob(table: str, tenant_id: str) -> dict:
    """
    Lee el campo `data` (long text con JSON) de una tabla Config_*. Devuelve {}
    si la fila no existe, la tabla aún no se creó, o el JSON es inválido.
    Patrón usado por las dos tablas consolidadas del paso 6:
    Config_Empresa y Config_Ventas.
    """
    rows = _safe_list(table, f"{{empresa_id}}='{tenant_id}'")
    if not rows:
        return {}
    raw = rows[0].get("fields", {}).get("data")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError) as e:
        print(
            f"[config_loader] {table}.data tiene JSON inválido: {e}",
            file=sys.stderr,
        )
        return {}


def _load_config_empresa() -> dict:
    """Lee `Config_Empresa.data` (basicos + info_extendida + proceso) del tenant."""
    return _load_data_blob("Config_Empresa", _get_tenant_id())


def _load_config_ventas() -> dict:
    """Lee `Config_Ventas.data` (bloque ventas) del tenant."""
    return _load_data_blob("Config_Ventas", _get_tenant_id())


def _deep_merge(base: dict, override: dict | None) -> dict:
    """
    Merge recursivo. Las claves de `override` ganan; los dicts anidados se
    mergean campo a campo; las listas y primitivos del override reemplazan
    completos. No muta los inputs.
    """
    if not isinstance(override, dict) or not override:
        return base
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ─────────────────────────────────────────────────────────────────────────
# Cache management
# ─────────────────────────────────────────────────────────────────────────

def invalidate_cache() -> None:
    """
    Resetea ambos caches (legacy + full). Llamado desde los endpoints POST
    de /api/config para que el siguiente request del agente vea los cambios
    sin esperar el TTL.
    """
    _cache["data"] = None
    _cache["expires_at"] = 0.0
    _full_cache["data"] = None
    _full_cache["expires_at"] = 0.0


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
    Devuelve la config completa combinando:

      1. JSON estático del tenant: solo `id`, `modules`, `agent` (paso 5).
      2. `Config_Empresa.data` en Airtable: `basicos` (name/razon_social/ruc/
         sistema_contable), `info_extendida`, `proceso.caja_chica`.
      3. `Config_Ventas.data` en Airtable: bloque ventas completo (paso 3).
      4. Aprobadores derivados de la tabla `Empleados` (load_dynamic_config).

    Cache 60s a nivel del resultado completo. Los POST de /api/config llaman
    a `invalidate_cache()` para que el siguiente request del agente vea los
    cambios sin esperar el TTL.

    Forma del dict devuelto:

        {
          "empresa": {
            "id", "name", "razon_social", "ruc", "sistema_contable",
            "agent", "modules", "info_extendida"
          },
          "proceso": {
            "caja_chica": {
              "<clave>": <valor>, ...,
              "aprobadores": [...]
            }
          },
          "ventas": {... 11 toggles ...}
        }
    """
    now = time.time()
    if _full_cache["data"] is not None and _full_cache["expires_at"] > now:
        return _full_cache["data"]

    static = load_static_config()
    dynamic = load_dynamic_config()       # legacy Config_Procesos + Empleados→aprobadores

    cfg_empresa = _load_config_empresa()   # Airtable Config_Empresa.data
    cfg_ventas = _load_config_ventas()     # Airtable Config_Ventas.data

    basicos = cfg_empresa.get("basicos", {}) if isinstance(cfg_empresa, dict) else {}

    # info_extendida: defaults ← Config_Empresa.data.info_extendida
    info_extendida = _merge_info_extendida(cfg_empresa.get("info_extendida"))

    # proceso: defaults legacy (Empleados aprobadores) ← Config_Empresa.data.proceso
    proceso = _merge_proceso(static.get("proceso", {}) or {}, dynamic or {})
    cfg_empresa_proceso = cfg_empresa.get("proceso") or {}
    if isinstance(cfg_empresa_proceso, dict):
        for proc_name, proc_data in cfg_empresa_proceso.items():
            if not isinstance(proc_data, dict):
                continue
            proceso.setdefault(proc_name, {}).update(proc_data)

    # ventas: defaults ← Config_Ventas.data
    ventas_block = _merge_ventas_config(cfg_ventas)

    empresa = {
        "id":               static.get("id"),
        "name":             basicos.get("name", "") if isinstance(basicos, dict) else "",
        "razon_social":     basicos.get("razon_social", "") if isinstance(basicos, dict) else "",
        "ruc":              basicos.get("ruc", "") if isinstance(basicos, dict) else "",
        "sistema_contable": basicos.get("sistema_contable", "concar") if isinstance(basicos, dict) else "concar",
        "agent":            static.get("agent", {}),
        "modules":          static.get("modules", []),
        "info_extendida":   info_extendida,
    }

    result = {
        "empresa": empresa,
        "proceso": proceso,
        "ventas":  ventas_block,
    }

    _full_cache["data"] = result
    _full_cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return result
