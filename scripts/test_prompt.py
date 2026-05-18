"""
Test del prompt builder de ventas (`api/_ventas/_lib/prompt.py`).

Ejecuta 6 escenarios in-memory (NO toca Airtable ni OpenAI) y reporta el
estado de cada aserción. Cubre:

  1. Tenant vacío → solo capas 1, 3 (default neutro), 4, 9 (universales).
  2. Tenant completo → todas las 9 capas, en orden, con headers correctos.
  3. Tenant parcial (solo capa 3 voz) → capas 1, 3, 4, 9. Resto ausentes.
  4. Promociones vencidas → se filtran del prompt.
  5. Prohibiciones universales → SIEMPRE presentes (aunque el campo esté off).
  6. Sin headers anidados → cada header de capa aparece exactamente 1 vez.

Uso:
    python scripts/test_prompt.py

Sale con código 0 si todo pasa, 1 si algo falla.
"""

import os
import sys
from datetime import date, timedelta

# UTF-8 en stdout para que corra en cmd/PowerShell de Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def _setup_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.abspath(os.path.join(here, "..", "api"))
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)


def _ctx_minimo() -> dict:
    return {"productos": [], "sender": {"nombre": "Juan", "phone": "+51999"}}


def _config_vacio() -> dict:
    return {
        "empresa": {"razon_social": "Demo SAC", "ruc": "12345678901"},
        "ventas": {},
    }


def _config_solo_voz() -> dict:
    """Solo capa 3 (un sub-campo) activa. Resto apagado."""
    return {
        "empresa": {"razon_social": "Demo SAC"},
        "ventas": {
            "tratamiento": {"activo": True, "valor": "tu"},
        },
    }


def _config_promo_vencida() -> dict:
    pasado = (date.today() - timedelta(days=10)).isoformat()
    futuro = (date.today() + timedelta(days=30)).isoformat()
    return {
        "empresa": {"razon_social": "Demo SAC"},
        "ventas": {
            "promociones_activas": {"activo": True, "valor": [
                {"titulo": "PROMO_VENCIDA", "respuesta": "no debe aparecer", "vigencia_fin": pasado},
                {"titulo": "PROMO_VIGENTE", "respuesta": "debe aparecer",    "vigencia_fin": futuro},
            ]},
        },
    }


def _config_completo() -> dict:
    """Todos los toggles encendidos con valores válidos en cada capa."""
    futuro = (date.today() + timedelta(days=30)).isoformat()
    return {
        "empresa": {
            "razon_social": "Empresa Demo SAC",
            "ruc":          "20123456789",
            "info_extendida": {
                "rubro":             {"activo": True, "valor": "Ferretería"},
                "descripcion":       {"activo": True, "valor": "Distribuidor mayorista de herramientas"},
                "horario_atencion":  {"activo": True, "valor": "L-V 9:00-18:00"},
            },
        },
        "ventas": {
            # capa 3
            "nombre_vendedor":      {"activo": True, "valor": "Carlos"},
            "tratamiento":          {"activo": True, "valor": "tu"},
            "vocabulario":          {"activo": True, "valor": "neutro"},
            "calidez":              {"activo": True, "valor": "cordial"},
            "localizacion_cultural": {"activo": True, "valor": {
                "region": "peru", "modismos_permitidos": ["bacán", "al toque"],
            }},
            "formato_mensaje":      {"activo": True, "valor": {
                "longitud_preferida":  "corto",
                "preguntas_por_turno": 1,
                "uso_listas":          "solo_si_3_o_mas",
                "puntuacion_enfatica": False,
            }},
            "uso_emojis":           {"activo": True, "valor": "ocasional_solo_calidez"},

            # capa 5
            "zona_cobertura":       {"activo": True, "valor": "Lima Metropolitana"},
            "tiempo_entrega":       {"activo": True, "valor": "24-48 horas hábiles"},
            "metodos_pago":         {"activo": True, "valor": ["yape_plin", "transferencia"]},
            "politica_precios":     {"activo": True, "valor": {"igv": "incluido", "comprobantes": "ambos"}},
            "moneda":               {"activo": True, "valor": "PEN"},
            "politica_envio":       {"activo": True, "valor": {
                "modelo": "fijo", "costo_fijo": 15, "monto_envio_gratis_desde": 200, "detalle_libre": "",
            }},
            "politica_devoluciones": {"activo": True, "valor": {
                "acepta_devolucion": True, "plazo_dias": 7, "condiciones": "Producto sin uso",
            }},
            "garantia":             {"activo": True, "valor": "1 año del fabricante"},
            "pedido_minimo":        {"activo": True, "valor": {"monto": 50, "comentario": ""}},
            "descuento_volumen":    {"activo": True, "valor": {
                "umbral_aplica": 1000, "instruccion": "derivar_humano",
            }},

            # capa 6
            "tipo_cliente":             {"activo": True, "valor": "mixto"},
            "discovery_preguntas":      {"activo": True, "valor": [
                {"pregunta": "¿Para qué centro de costo es?",   "obligatoria": True},
                {"pregunta": "¿Cuándo lo necesitas?", "obligatoria": False},
            ]},
            "datos_cierre_obligatorios": {"activo": True, "valor": ["nombre", "telefono", "direccion"]},
            "umbral_derivacion_humano":  {"activo": True, "valor": 5000},
            "criterios_derivacion":      {"activo": True, "valor": ["queja_reclamo", "cotizacion_formal"]},
            "asesor_humano":             {"activo": True, "valor": {"nombre": "Pedro", "telefono": "+51987654321"}},
            "horario_ia":                {"activo": True, "valor": "solo_horario_atencion"},

            # capa 7
            "propuesta_valor":      {"activo": True, "valor": "Stock inmediato y asesoría técnica"},
            "diferenciadores":      {"activo": True, "valor": ["Stock 24h", "Asesoría especializada"]},
            "prueba_social":        {"activo": True, "valor": ["Más de 200 centros de costo atendidos en 2025"]},
            "autoridad_tecnica":    {"activo": True, "valor": ["10 años en el rubro"]},
            "faq":                  {"activo": True, "valor": [
                {"titulo": "Aceptan facturas a 30 días", "respuesta": "Solo para clientes con línea aprobada."},
            ]},
            "promociones_activas":  {"activo": True, "valor": [
                {"titulo": "10% off en taladros DeWalt", "respuesta": "Hasta fin de mes.", "vigencia_fin": futuro},
            ]},

            # capa 8
            "objeciones": {"activo": True, "valor": [
                {"objecion": "Está caro", "como_responder": "Reconocer, no defender. Preguntar con qué lo compara."},
            ]},

            # capa 9
            "prohibiciones":            {"activo": True, "valor": ["No menciones a la marca X"]},
            "alcance_responsabilidad":  {"activo": True, "valor": "Cotizo y tomo pedidos. NO emito facturas."},
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────

class _Reporter:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.total = 0

    def assert_(self, cond: bool, msg: str) -> None:
        self.total += 1
        if not cond:
            self.failures.append(msg)

    def report(self) -> int:
        passed = self.total - len(self.failures)
        print(f"\n{passed}/{self.total} aserciones pasaron.")
        if self.failures:
            print("\nFallaron:")
            for m in self.failures:
                print(f"  ✗ {m}")
            return 1
        print("✓ Todos los tests pasaron.")
        return 0


def main() -> int:
    _setup_path()
    from _ventas._lib.prompt import (
        build_prompt,
        PROHIBICIONES_UNIVERSALES,
        VOZ_DEFAULT_NEUTRO,
    )

    r = _Reporter()
    ctx = _ctx_minimo()

    # ── Test 1: tenant vacío ───────────────────────────────────────────────
    p1 = build_prompt(_config_vacio(), ctx)
    r.assert_("# CLIENTE ACTUAL"            in p1, "T1: capa 1 (CLIENTE ACTUAL) presente")
    r.assert_("# VOZ DEL VENDEDOR"          in p1, "T1: capa 3 (VOZ DEL VENDEDOR) presente")
    r.assert_(VOZ_DEFAULT_NEUTRO            in p1, "T1: VOZ_DEFAULT_NEUTRO emitido como fallback")
    r.assert_("# CATÁLOGO DISPONIBLE"       in p1, "T1: capa 4 (CATÁLOGO DISPONIBLE) presente")
    r.assert_("# LÍMITES Y PROHIBICIONES"   in p1, "T1: capa 9 (LÍMITES Y PROHIBICIONES) presente")
    r.assert_("# SOBRE LA EMPRESA"      not in p1, "T1: capa 2 ausente (info_extendida vacía)")
    r.assert_("# POLÍTICA COMERCIAL"    not in p1, "T1: capa 5 ausente")
    r.assert_("# CLIENTE Y ARCO CONVERSACIONAL" not in p1, "T1: capa 6 ausente")
    r.assert_("# CONOCIMIENTO DE MARCA" not in p1, "T1: capa 7 ausente")
    r.assert_("# MANEJO DE OBJECIONES"  not in p1, "T1: capa 8 ausente")

    # Estimación de tokens — el plan exige <800 tokens. Heurística: 1 token ≈ 4 chars.
    estimacion_tokens = len(p1) // 4
    r.assert_(estimacion_tokens < 800,
              f"T1: prompt vacío bajo 800 tokens (≈{estimacion_tokens})")

    # ── Test 2: tenant completo ───────────────────────────────────────────
    p2 = build_prompt(_config_completo(), ctx)
    headers_esperados = [
        "# CLIENTE ACTUAL",
        "# SOBRE LA EMPRESA",
        "# VOZ DEL VENDEDOR",
        "# CATÁLOGO DISPONIBLE",
        "# POLÍTICA COMERCIAL",
        "# CLIENTE Y ARCO CONVERSACIONAL",
        "# CONOCIMIENTO DE MARCA",
        "# MANEJO DE OBJECIONES",
        "# LÍMITES Y PROHIBICIONES",
    ]
    for h in headers_esperados:
        r.assert_(h in p2, f"T2: header esperado {h!r} presente")

    posiciones = [p2.find(h) for h in headers_esperados]
    en_orden = all(posiciones[i] < posiciones[i + 1] for i in range(len(posiciones) - 1))
    r.assert_(en_orden, "T2: capas en orden correcto")

    # Spot-check de contenido específico de cada nueva capa:
    r.assert_("Carlos" in p2, "T2: nombre del vendedor inyectado")
    r.assert_("Trata al cliente de tú" in p2, "T2: tratamiento aplicado")
    r.assert_("bacán" in p2, "T2: modismos peruanos presentes")
    r.assert_("Pedido mínimo" in p2 or "PEDIDO MÍNIMO" in p2, "T2: pedido mínimo en capa 5")
    r.assert_("Para qué centro de costo es?" in p2, "T2: discovery question presente")
    r.assert_("[obligatoria]" in p2, "T2: marca [obligatoria] en discovery")
    r.assert_("Stock inmediato y asesoría técnica" in p2, "T2: propuesta de valor presente")
    r.assert_("Está caro" in p2, "T2: objeción presente")
    r.assert_("No menciones a la marca X" in p2, "T2: prohibición específica del cliente añadida")
    r.assert_("Cotizo y tomo pedidos" in p2, "T2: alcance de responsabilidad presente")

    # ── Test 3: parcial — solo capa 3 ──────────────────────────────────────
    p3 = build_prompt(_config_solo_voz(), ctx)
    r.assert_("# CLIENTE ACTUAL"              in p3, "T3: capa 1 presente")
    r.assert_("# VOZ DEL VENDEDOR"            in p3, "T3: capa 3 presente")
    r.assert_("# CATÁLOGO DISPONIBLE"         in p3, "T3: capa 4 presente")
    r.assert_("# LÍMITES Y PROHIBICIONES"     in p3, "T3: capa 9 presente")
    r.assert_("# POLÍTICA COMERCIAL"      not in p3, "T3: capa 5 ausente")
    r.assert_("# CLIENTE Y ARCO CONVERSACIONAL" not in p3, "T3: capa 6 ausente")
    r.assert_("# CONOCIMIENTO DE MARCA"   not in p3, "T3: capa 7 ausente")
    r.assert_("# MANEJO DE OBJECIONES"    not in p3, "T3: capa 8 ausente")
    r.assert_(VOZ_DEFAULT_NEUTRO          not in p3, "T3: NO usa fallback default cuando hay un sub-campo activo")
    r.assert_("Trata al cliente de tú"        in p3, "T3: instrucción de tratamiento aplicada")

    # ── Test 4: promociones vencidas se filtran ──────────────────────────
    p4 = build_prompt(_config_promo_vencida(), ctx)
    r.assert_("PROMO_VENCIDA" not in p4, "T4: promo vencida se filtra")
    r.assert_("PROMO_VIGENTE"     in p4, "T4: promo vigente aparece")

    # ── Test 5: prohibiciones universales SIEMPRE ─────────────────────────
    for nombre_cfg, cfg in [
        ("vacío",     _config_vacio()),
        ("solo_voz",  _config_solo_voz()),
        ("completo",  _config_completo()),
    ]:
        prompt_cfg = build_prompt(cfg, ctx)
        for univ in PROHIBICIONES_UNIVERSALES:
            r.assert_(univ in prompt_cfg,
                      f"T5: universal en config '{nombre_cfg}': {univ[:50]}...")

    # ── Test 6: sin headers anidados — cada header de capa exactamente 1 vez ──
    top_headers = [
        "# CLIENTE ACTUAL",
        "# SOBRE LA EMPRESA",
        "# VOZ DEL VENDEDOR",
        "# CATÁLOGO DISPONIBLE",
        "# POLÍTICA COMERCIAL",
        "# CLIENTE Y ARCO CONVERSACIONAL",
        "# CONOCIMIENTO DE MARCA",
        "# MANEJO DE OBJECIONES",
        "# LÍMITES Y PROHIBICIONES",
    ]
    for h in top_headers:
        n = p2.count(h)
        r.assert_(n == 1, f"T6: header {h!r} aparece exactamente 1 vez (got {n})")

    # Y sub-headers internos no deben estar duplicados tampoco.
    sub_headers_internos = [
        "# IDENTIDAD DEL VENDEDOR",
        "# TRATAMIENTO",
        "# VOCABULARIO",
        "# COBERTURA",
        "# DEVOLUCIONES",
        "# PROHIBICIONES",
    ]
    for h in sub_headers_internos:
        n = p2.count(h)
        r.assert_(n == 0, f"T6: sub-header {h!r} ya stripeado en wrappers (got {n})")

    return r.report()


if __name__ == "__main__":
    sys.exit(main())
