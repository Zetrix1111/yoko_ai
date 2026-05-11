"""
Loader de configuración multi-tenant. Toda la config viene de Airtable;
no hay archivos JSON por tenant en el filesystem.

Tablas que lee:
  • Config_Empresa.data    (basicos + info_extendida + proceso.caja_chica)
  • Config_Ventas.data     (bloque ventas — 11 toggles del agente)
  • Config_Procesos        (legacy — claves dinámicas por proceso)
  • Aprobadores            (legacy — agrupados por proceso)
  • Empleados              (filtrados por APROBADORES → listas de aprobador_1/2)

Cache: TTL 60s POR EMPRESA. Cold start lo resetea (esperado en serverless).
Los POST de /api/config llaman a `invalidate_cache(empresa_id)` para que
la siguiente request del agente vea los cambios sin esperar el TTL.

Multi-tenant: todas las funciones públicas reciben `empresa_id` como
primer parámetro. El cache es un dict por empresa para no mezclar datos
entre clientes.
"""

import json
import sys
import time

from . import airtable_client
from .airtable_client import AirtableError


# ─────────────────────────────────────────────────────────────────────────
# Cache de la config dinámica — UN dict por empresa
# ─────────────────────────────────────────────────────────────────────────
# TTL bajo (60s) para que los cambios desde la UI se reflejen rápido sin
# saturar Airtable. Los POST de /api/config llaman invalidate_cache(empresa_id)
# para que el caso normal sea instantáneo.
_CACHE_TTL_SECONDS = 60

# {empresa_id: {"data": dict|None, "expires_at": float}}
_dynamic_cache: dict[str, dict] = {}
_full_cache:    dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────────────────
# Branding/identidad — único para todos los tenants. Si en el futuro se
# decide rebrand por cliente, mover a Airtable Config_Empresa.basicos.
# ─────────────────────────────────────────────────────────────────────────
_AGENT_DEFAULTS = {"name": "Yoko"}


# ─────────────────────────────────────────────────────────────────────────
# Capa dinámica (reglas de negocio en Airtable)
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
    Intenta listar una tabla y, si falla (404 porque no existe aún, o
    error de red), devuelve [] con un warning a stderr. El skeleton
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


def load_dynamic_config(empresa_id: str) -> dict:
    """
    Lee las tablas Config_* desde Airtable filtradas por empresa_id.

    Devuelve un dict por proceso con la forma:
        {
          "caja_chica": {
            "<clave>": <valor casteado>,
            ...,
            "aprobadores": [{...fields}],
            "lista_aprobador_1": [...],
            "lista_aprobador_2": [...],
          }
        }

    Cache TTL 60s POR EMPRESA. Llamadas siguientes dentro del TTL para
    la misma empresa no tocan Airtable.
    """
    now = time.time()
    entry = _dynamic_cache.get(empresa_id)
    if entry and entry.get("data") is not None and entry.get("expires_at", 0) > now:
        return entry["data"]

    formula = f"{{empresa_id}}='{empresa_id}'"

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

    # 3) Empleados con rol de aprobador (filtrados por empresa_id + tener APROBADORES)
    empleados_formula = (
        f"AND({{empresa_id}}='{empresa_id}', NOT({{APROBADORES}} = ''))"
    )
    empleados_rows = _safe_list("Empleados", empleados_formula)
    aprobador_1: list[dict] = []
    aprobador_2: list[dict] = []
    for row in empleados_rows:
        f = row.get("fields", {})
        roles = f.get("APROBADORES")
        if not roles:
            continue
        if isinstance(roles, str):
            roles = [roles]

        info = {
            "id":     row.get("id"),
            "nombre": f.get("NOMBRE CORTO", "Desconocido"),
        }

        if "APROBADOR_1" in roles:
            aprobador_1.append(info)
        if "APROBADOR_2" in roles:
            aprobador_2.append(info)

    procesos["caja_chica"]["lista_aprobador_1"] = aprobador_1
    procesos["caja_chica"]["lista_aprobador_2"] = aprobador_2

    for proceso_dict in procesos.values():
        proceso_dict.setdefault("aprobadores", [])

    _dynamic_cache[empresa_id] = {
        "data":       procesos,
        "expires_at": now + _CACHE_TTL_SECONDS,
    }
    return procesos


# ─────────────────────────────────────────────────────────────────────────
# Empresa.info_extendida — defaults y deep merge
# ─────────────────────────────────────────────────────────────────────────

# Schema fijo. Cada campo: {activo: bool, valor: <tipo>}. Los toggles arrancan
# en false → el prompt no los menciona.
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
            continue
        if "activo" in incoming:
            merged[key]["activo"] = bool(incoming["activo"])
        if "valor" in incoming:
            merged[key]["valor"] = incoming["valor"]
    return merged


# ─────────────────────────────────────────────────────────────────────────
# Ventas — defaults, deep merge y carga dinámica (schema v2: 24 campos en 9 capas)
# ─────────────────────────────────────────────────────────────────────────

def _default_ventas_config() -> dict:
    """
    Shape default del bloque ventas (schema v2). Todos los toggles arrancan
    en false; cuando activo:false, el prompt builder usa sus defaults
    universales hardcodeados. Los campos legacy v1 (`estilo_vendedor`,
    `info_adicional`) ya no figuran acá: si una row vieja en Airtable los
    trae, `_merge_ventas_config` los descarta silenciosamente al cargar.
    """
    return {
        # CAPA 3 — Voz del vendedor
        "nombre_vendedor":       {"activo": False, "valor": ""},
        "tratamiento":           {"activo": False, "valor": "tu"},
        "vocabulario":           {"activo": False, "valor": "neutro"},
        "calidez":               {"activo": False, "valor": "cordial"},
        "localizacion_cultural": {"activo": False, "valor": {"region": "neutro_latam", "modismos_permitidos": []}},
        "formato_mensaje":       {"activo": False, "valor": {"longitud_preferida": "corto", "preguntas_por_turno": 1, "uso_listas": "solo_si_3_o_mas", "puntuacion_enfatica": False}},
        "uso_emojis":            {"activo": False, "valor": "nunca"},

        # CAPA 5 — Política comercial
        "zona_cobertura":        {"activo": False, "valor": ""},
        "tiempo_entrega":        {"activo": False, "valor": ""},
        "metodos_pago":          {"activo": False, "valor": []},
        "politica_precios":      {"activo": False, "valor": {"igv": "incluido", "comprobantes": "ambos"}},
        "moneda":                {"activo": False, "valor": "PEN"},
        "politica_envio":        {"activo": False, "valor": {"modelo": "fijo", "monto_envio_gratis_desde": None, "costo_fijo": None, "detalle_libre": ""}},
        "politica_devoluciones": {"activo": False, "valor": {"acepta_devolucion": True, "plazo_dias": 7, "condiciones": ""}},
        "garantia":              {"activo": False, "valor": ""},
        "pedido_minimo":         {"activo": False, "valor": {"monto": 0, "comentario": ""}},
        "descuento_volumen":     {"activo": False, "valor": {"umbral_aplica": 0, "instruccion": "derivar_humano"}},

        # CAPA 6 — Cliente y arco conversacional
        "tipo_cliente":               {"activo": False, "valor": "mixto"},
        "discovery_preguntas":        {"activo": False, "valor": []},
        "datos_cierre_obligatorios":  {"activo": False, "valor": ["nombre", "telefono"]},
        "umbral_derivacion_humano":   {"activo": False, "valor": None},
        "criterios_derivacion":       {"activo": False, "valor": []},
        "asesor_humano":              {"activo": False, "valor": {"nombre": "", "telefono": ""}},
        "horario_ia":                 {"activo": False, "valor": "24_7"},

        # CAPA 7 — Conocimiento de marca
        "propuesta_valor":     {"activo": False, "valor": ""},
        "diferenciadores":     {"activo": False, "valor": []},
        "prueba_social":       {"activo": False, "valor": []},
        "autoridad_tecnica":   {"activo": False, "valor": []},
        "faq":                 {"activo": False, "valor": []},
        "promociones_activas": {"activo": False, "valor": []},
        # URL público al PDF del catálogo. El agente lo comparte (tool
        # `enviar_catalogo`) cuando el cliente no tiene claro qué busca.
        # Si activo:false o valor vacío, la tool no se anuncia al LLM.
        "catalogo_pdf_url":    {"activo": False, "valor": ""},

        # CAPA 8 — Manejo de objeciones
        "objeciones": {"activo": False, "valor": []},

        # CAPA 9 — Límites y prohibiciones
        "prohibiciones":           {"activo": False, "valor": []},
        "alcance_responsabilidad": {"activo": False, "valor": ""},
    }


def _merge_ventas_config(provided: dict | None) -> dict:
    """
    Deep merge defaults ← provided. Los campos del shape sobrescriben sus
    defaults con lo que venga; campos no definidos en el schema se ignoran.
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


def _load_data_blob(table: str, empresa_id: str) -> dict:
    """
    Lee el campo `data` (long text con JSON) de una tabla Config_*. Devuelve
    {} si la fila no existe, la tabla aún no se creó, o el JSON es inválido.
    """
    rows = _safe_list(table, f"{{empresa_id}}='{empresa_id}'")
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


def _load_config_empresa(empresa_id: str) -> dict:
    """Lee `Config_Empresa.data` (basicos + info_extendida + proceso) del tenant."""
    return _load_data_blob("Config_Empresa", empresa_id)


def _load_config_ventas(empresa_id: str) -> dict:
    """Lee `Config_Ventas.data` (bloque ventas) del tenant."""
    return _load_data_blob("Config_Ventas", empresa_id)


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

def invalidate_cache(empresa_id: str) -> None:
    """
    Resetea ambos caches (dinámico + full) PARA UNA EMPRESA. Llamado desde
    los endpoints POST de /api/config para que el siguiente request del
    agente vea los cambios sin esperar el TTL.
    """
    _dynamic_cache.pop(empresa_id, None)
    _full_cache.pop(empresa_id, None)


# ─────────────────────────────────────────────────────────────────────────
# Combinada (estática + dinámica)
# ─────────────────────────────────────────────────────────────────────────
def _merge_proceso(static_proceso: dict, dynamic_proceso: dict) -> dict:
    """
    Combina los procesos del config estático (defaults por tenant) con
    los del dinámico (Airtable). El dinámico sobreescribe clave a clave.
    """
    combined: dict[str, dict] = {}
    for proc_name, proc_data in (static_proceso or {}).items():
        combined[proc_name] = dict(proc_data) if isinstance(proc_data, dict) else {}
    for proc_name, proc_data in (dynamic_proceso or {}).items():
        if proc_name in combined and isinstance(proc_data, dict):
            combined[proc_name].update(proc_data)
        else:
            combined[proc_name] = proc_data
    return combined


def load_full_config(empresa_id: str) -> dict:
    """
    Devuelve la config completa para una empresa leyendo SOLO desde Airtable
    (sin filesystem). Combina:

      1. `Config_Empresa.data`: `basicos`, `info_extendida`, `proceso.caja_chica`.
      2. `Config_Ventas.data`: bloque ventas completo.
      3. Aprobadores derivados de la tabla `Empleados` (load_dynamic_config).
      4. `agent` viene de `_AGENT_DEFAULTS` (siempre "Yoko").
      5. `modules` queda vacío acá; el handler lo inyecta desde el JWT.

    Cache 60s POR EMPRESA. Los POST de /api/config llaman a
    `invalidate_cache(empresa_id)` para que la siguiente request vea los
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
    entry = _full_cache.get(empresa_id)
    if entry and entry.get("data") is not None and entry.get("expires_at", 0) > now:
        return entry["data"]

    dynamic = load_dynamic_config(empresa_id)

    cfg_empresa = _load_config_empresa(empresa_id)
    cfg_ventas = _load_config_ventas(empresa_id)

    basicos = cfg_empresa.get("basicos", {}) if isinstance(cfg_empresa, dict) else {}

    # info_extendida: defaults ← Config_Empresa.data.info_extendida
    info_extendida = _merge_info_extendida(cfg_empresa.get("info_extendida"))

    # proceso: defaults vacíos ← legacy Config_Procesos + Empleados →
    # ← Config_Empresa.data.proceso (gana sobre todo).
    proceso = _merge_proceso({}, dynamic or {})
    cfg_empresa_proceso = cfg_empresa.get("proceso") or {}
    if isinstance(cfg_empresa_proceso, dict):
        for proc_name, proc_data in cfg_empresa_proceso.items():
            if not isinstance(proc_data, dict):
                continue
            proceso.setdefault(proc_name, {}).update(proc_data)

    # ventas: defaults ← Config_Ventas.data
    ventas_block = _merge_ventas_config(cfg_ventas)

    # empresa.id y empresa.modules los inyecta el handler desde el JWT
    # antes de pasar el config al prompt builder. Acá quedan vacíos.
    empresa = {
        "id":               empresa_id,
        "name":             basicos.get("name", "") if isinstance(basicos, dict) else "",
        "razon_social":     basicos.get("razon_social", "") if isinstance(basicos, dict) else "",
        "ruc":              basicos.get("ruc", "") if isinstance(basicos, dict) else "",
        "sistema_contable": basicos.get("sistema_contable", "concar") if isinstance(basicos, dict) else "concar",
        "agent":            dict(_AGENT_DEFAULTS),
        "modules":          [],
        "info_extendida":   info_extendida,
    }

    result = {
        "empresa": empresa,
        "proceso": proceso,
        "ventas":  ventas_block,
    }

    _full_cache[empresa_id] = {
        "data":       result,
        "expires_at": now + _CACHE_TTL_SECONDS,
    }
    return result
