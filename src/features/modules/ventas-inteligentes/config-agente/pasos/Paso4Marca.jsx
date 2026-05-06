import { CampoToggle } from '../../sections';
import EditorListaSimple from '../componentes/EditorListaSimple';
import EditorListaCompleja from '../componentes/EditorListaCompleja';
import PanelInformativo from '../componentes/PanelInformativo';
import {
  SUGERENCIAS_DIFERENCIADORES, SUGERENCIAS_PRUEBA_SOCIAL, SUGERENCIAS_AUTORIDAD,
} from '../defaults';

/**
 * Paso 4 del wizard: Conocimiento de marca (capa 7).
 * Sub-bloques: propuesta, diferenciadores, prueba social, autoridad,
 * FAQs, promociones.
 */
export default function Paso4Marca({ config, setCampo }) {
  const f = (key) => config[key] || { activo: false, valor: '' };
  const setActivo = (key) => (a) => setCampo(key, { activo: a });
  const setValor  = (key) => (v) => setCampo(key, { valor: v });

  const propuesta = f('propuesta_valor').valor || '';
  const propuestaCount = propuesta.length;

  return (
    <div className="via-paso">
      <header className="via-paso-header">
        <h2 className="via-paso-titulo">4. Conocimiento de la marca</h2>
        <p className="via-paso-subtitulo">
          Lo que hace distinta a tu empresa. El agente lo usa para responder
          mejor, sin recitar como folleto.
        </p>
      </header>

      <section className="via-paso-section">
        <CampoToggle
          campo="propuesta_valor"
          label="Propuesta de valor (1 frase)"
          helpText={`${propuestaCount} / 200 caracteres`}
          activo={f('propuesta_valor').activo}
          onActivoChange={setActivo('propuesta_valor')}
        >
          <textarea
            id="via-propuesta"
            className="vom-textarea"
            rows={2}
            maxLength={200}
            placeholder="Ej: Stock inmediato y asesoría técnica en EPP."
            value={propuesta}
            disabled={!f('propuesta_valor').activo}
            onChange={(e) => setValor('propuesta_valor')(e.target.value)}
          />
        </CampoToggle>

        <CampoToggle
          campo="diferenciadores"
          label="Diferenciadores"
          helpText="Lo que te distingue de la competencia. Frases cortas."
          activo={f('diferenciadores').activo}
          onActivoChange={setActivo('diferenciadores')}
        >
          <EditorListaSimple
            items={f('diferenciadores').valor || []}
            onChange={setValor('diferenciadores')}
            placeholder="Ej: Stock inmediato 24h"
            maxItems={6}
            sugerencias={SUGERENCIAS_DIFERENCIADORES}
            disabled={!f('diferenciadores').activo}
            ariaLabel="Diferenciadores"
          />
        </CampoToggle>

        <CampoToggle
          campo="prueba_social"
          label="Prueba social"
          helpText="Hechos verificables. El agente los menciona naturalmente cuando aplica, no los recita."
          activo={f('prueba_social').activo}
          onActivoChange={setActivo('prueba_social')}
        >
          <EditorListaSimple
            items={f('prueba_social').valor || []}
            onChange={setValor('prueba_social')}
            placeholder="Ej: Más de 200 obras atendidas en 2025"
            maxItems={6}
            sugerencias={SUGERENCIAS_PRUEBA_SOCIAL}
            disabled={!f('prueba_social').activo}
            ariaLabel="Prueba social"
          />
        </CampoToggle>

        <CampoToggle
          campo="autoridad_tecnica"
          label="Autoridad técnica"
          helpText="Credenciales y experiencia que respaldan a la empresa."
          activo={f('autoridad_tecnica').activo}
          onActivoChange={setActivo('autoridad_tecnica')}
        >
          <EditorListaSimple
            items={f('autoridad_tecnica').valor || []}
            onChange={setValor('autoridad_tecnica')}
            placeholder="Ej: 10 años en el rubro"
            maxItems={6}
            sugerencias={SUGERENCIAS_AUTORIDAD}
            disabled={!f('autoridad_tecnica').activo}
            ariaLabel="Autoridad técnica"
          />
        </CampoToggle>

        <CampoToggle
          campo="faq"
          label="Preguntas frecuentes (FAQ)"
          activo={f('faq').activo}
          onActivoChange={setActivo('faq')}
        >
          <EditorListaCompleja
            items={f('faq').valor || []}
            onChange={setValor('faq')}
            schema={[
              { key: 'titulo',    label: 'Título', type: 'text',     placeholder: '¿Aceptan facturas a 30 días?' },
              { key: 'respuesta', label: 'Respuesta', type: 'textarea', rows: 2, placeholder: 'Solo para clientes con línea aprobada.' },
              { key: 'vigencia_inicio', label: 'Inicio', type: 'date', optional: true },
              { key: 'vigencia_fin',    label: 'Fin',    type: 'date', optional: true },
            ]}
            maxItems={30}
            itemLabel="FAQ"
            disabled={!f('faq').activo}
          />
        </CampoToggle>

        <CampoToggle
          campo="promociones_activas"
          label="Promociones activas"
          activo={f('promociones_activas').activo}
          onActivoChange={setActivo('promociones_activas')}
        >
          <PanelInformativo>
            Las promociones con vigencia vencida se filtran automáticamente
            del prompt.
          </PanelInformativo>
          <EditorListaCompleja
            items={f('promociones_activas').valor || []}
            onChange={setValor('promociones_activas')}
            schema={[
              { key: 'titulo',    label: 'Título', type: 'text',     placeholder: '10% off en taladros DeWalt' },
              { key: 'respuesta', label: 'Detalle', type: 'textarea', rows: 2, placeholder: 'Hasta fin de mes.' },
              { key: 'vigencia_inicio', label: 'Inicio', type: 'date', optional: true },
              { key: 'vigencia_fin',    label: 'Fin (recomendado)', type: 'date', optional: true },
            ]}
            maxItems={20}
            itemLabel="Promoción"
            disabled={!f('promociones_activas').activo}
          />
        </CampoToggle>
      </section>
    </div>
  );
}
