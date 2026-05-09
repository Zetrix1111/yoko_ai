"""
Test del motor de extracción (api/_lib/extraction/).

Ejecuta smoke tests in-memory que NO tocan OpenAI ni archivos reales.
Verifica:
  - Imports de la API pública (`extract_with_template`, `list_templates`,
    `get_template`, `register_template`, `reset_registry`).
  - Re-exports legacy desde `api/parse_file.py` que `facturas_processor.py`
    consume (los 7 símbolos privados).
  - Templates registrados (factura + caja_chica) y sus atributos.
  - `enrich()` de factura — casos típicos.
  - `register_template()` — duplicados, validación.
  - `list_templates()` — orden alfabético, shape del dict.
  - `get_template()` con nombre inexistente — error claro.

Uso:
    python scripts/test_extraction.py

Sale 0 si todo pasa, 1 si algo falla.
"""

import os
import sys

# UTF-8 en stdout para Windows (cp1252 rompe con caracteres acentuados).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def _setup_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.abspath(os.path.join(here, "..", "api"))
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)


# ─────────────────────────────────────────────────────────────────────────
# Reporter
# ─────────────────────────────────────────────────────────────────────────

class _Reporter:
    def __init__(self) -> None:
        self.failures: list = []
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

    from _lib.extraction import (
        extract_with_template,
        extract_from_file,
        get_template,
        list_templates,
        register_template,
        reset_registry,
    )
    import parse_file as _pf

    r = _Reporter()

    # ── T1: API pública del paquete ────────────────────────────────────
    r.assert_(callable(extract_with_template), "T1: extract_with_template es callable")
    r.assert_(callable(extract_from_file),     "T1: extract_from_file es callable")
    r.assert_(callable(get_template),          "T1: get_template es callable")
    r.assert_(callable(list_templates),        "T1: list_templates es callable")
    r.assert_(callable(register_template),     "T1: register_template es callable")
    r.assert_(callable(reset_registry),        "T1: reset_registry es callable")

    # ── T2: list_templates() devuelve los 2 esperados ──────────────────
    tmpls = list_templates()
    nombres = [t["name"] for t in tmpls]
    r.assert_("factura"    in nombres, "T2: 'factura' está registrado")
    r.assert_("caja_chica" in nombres, "T2: 'caja_chica' está registrado")
    r.assert_(nombres == sorted(nombres), "T2: list_templates devuelve orden alfabético")
    for t in tmpls:
        r.assert_(set(t.keys()) >= {"name", "description", "model"},
                  f"T2: template '{t.get('name')}' tiene name/description/model")

    # ── T3: get_template() / atributos ─────────────────────────────────
    fac = get_template("factura")
    r.assert_(fac.NAME == "factura",        "T3: factura.NAME == 'factura'")
    r.assert_(fac.MODEL == "gpt-4o",        "T3: factura.MODEL == 'gpt-4o'")
    r.assert_(callable(getattr(fac, "enrich", None)),
              "T3: factura.enrich es callable")
    r.assert_(hasattr(fac, "_TIPO_DOC_MAP"),
              "T3: factura tiene _TIPO_DOC_MAP")
    r.assert_(fac._TIPO_DOC_MAP["factura"] == "FT",
              "T3: TIPO_DOC_MAP['factura'] == 'FT'")
    r.assert_(fac._TIPO_DOC_MAP["recibo por honorarios"] == "RH",
              "T3: TIPO_DOC_MAP['recibo por honorarios'] == 'RH'")

    cc = get_template("caja_chica")
    r.assert_(cc.NAME == "caja_chica", "T3: caja_chica.NAME correcto")
    r.assert_(not hasattr(cc, "enrich"),
              "T3: caja_chica NO tiene enrich (sin post-procesamiento)")

    # ── T4: get_template() inexistente → ValueError con mensaje útil ──
    try:
        get_template("noexiste")
        r.assert_(False, "T4: get_template('noexiste') debería lanzar ValueError")
    except ValueError as e:
        msg = str(e)
        r.assert_("factura"    in msg, "T4: mensaje de error lista 'factura'")
        r.assert_("caja_chica" in msg, "T4: mensaje de error lista 'caja_chica'")

    # ── T5: enrich() de factura — casos típicos ────────────────────────
    out_alta = fac.enrich({"tipo_doc": "Boleta", "confianza": "alta"})
    r.assert_(out_alta["tipo_doc_codigo"] == "BV",
              "T5: enrich(Boleta) → tipo_doc_codigo='BV'")
    r.assert_(out_alta["confianza"] == 0.95,
              "T5: enrich(alta) → confianza=0.95")

    out_media = fac.enrich({"tipo_doc": "Factura", "confianza": "media"})
    r.assert_(out_media["tipo_doc_codigo"] == "FT",
              "T5: enrich(Factura) → 'FT'")
    r.assert_(out_media["confianza"] == 0.80,
              "T5: enrich(media) → 0.80")

    out_baja = fac.enrich({"tipo_doc": "Nota de Crédito", "confianza": "baja"})
    r.assert_(out_baja["tipo_doc_codigo"] == "NC",
              "T5: enrich(Nota de Crédito) → 'NC'")
    r.assert_(out_baja["confianza"] == 0.60,
              "T5: enrich(baja) → 0.60")

    out_default = fac.enrich({})
    r.assert_(out_default["tipo_doc_codigo"] == "FT",
              "T5: enrich({}) → default 'FT'")
    r.assert_(out_default["estado"] == "Por implementar validación",
              "T5: enrich agrega 'estado' placeholder")
    r.assert_(out_default["obra_area"] == "",
              "T5: enrich agrega 'obra_area' vacío")

    # ── T6: register_template() — validaciones ─────────────────────────
    try:
        register_template(type("Bad", (), {})())  # objeto sin NAME ni PROMPT
        r.assert_(False, "T6: register_template sin NAME/PROMPT debería fallar")
    except ValueError:
        r.assert_(True, "T6: register_template sin atributos lanza ValueError")

    # Registro programático válido + reset.
    fake_template = type("FakeTpl", (), {"NAME": "_test_tpl", "PROMPT": "x"})()
    register_template(fake_template)
    r.assert_(get_template("_test_tpl").NAME == "_test_tpl",
              "T6: register_template programático funciona")

    reset_registry()
    # Después de reset, el registry se reconstruye sin el fake.
    nombres_reset = [t["name"] for t in list_templates()]
    r.assert_("_test_tpl" not in nombres_reset,
              "T6: reset_registry limpia los registros programáticos")

    # ── T7: Re-exports legacy desde parse_file ─────────────────────────
    # Estos 7 símbolos los importa facturas_processor.py por path directo.
    legacy_symbols = [
        "_extract_via_vision",
        "_extract_pdf_pages",
        "_extract_from_excel",
        "_extract_from_docx",
        "_text_to_campos",
        "_enrich_factura_data",
        "_EXTRACTION_PROMPT_FACTURA",
    ]
    for sym in legacy_symbols:
        r.assert_(hasattr(_pf, sym),
                  f"T7: parse_file re-exporta '{sym}'")

    # PROMPT_FACTURA legacy es exactamente el mismo string que el del template.
    r.assert_(_pf._EXTRACTION_PROMPT_FACTURA == fac.PROMPT,
              "T7: _EXTRACTION_PROMPT_FACTURA legacy idéntico al template")
    r.assert_(len(_pf._EXTRACTION_PROMPT_FACTURA) > 1000,
              "T7: prompt legacy no quedó vacío (>1000 chars)")

    # _enrich_factura_data legacy === fac.enrich
    legacy_out = _pf._enrich_factura_data({"tipo_doc": "Boleta", "confianza": "alta"})
    r.assert_(legacy_out["tipo_doc_codigo"] == "BV" and legacy_out["confianza"] == 0.95,
              "T7: _enrich_factura_data legacy funciona igual que el nuevo")

    # ── T8: facturas_processor.py sigue importando sin problemas ───────
    import importlib
    fp = importlib.import_module("_lib.facturas_processor")
    r.assert_(hasattr(fp, "process_multiple_files"),
              "T8: facturas_processor.process_multiple_files existe")
    r.assert_(hasattr(fp, "process_single_file"),
              "T8: facturas_processor.process_single_file existe")

    return r.report()


if __name__ == "__main__":
    sys.exit(main())
