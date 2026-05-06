import { CampoToggle } from '../../sections';
import EditorListaSimple from '../componentes/EditorListaSimple';
import EditorListaCompleja from '../componentes/EditorListaCompleja';
import PanelInformativo from '../componentes/PanelInformativo';
import PreviewPrompt from '../componentes/PreviewPrompt';
import {
  PLANTILLAS_OBJECIONES, PROHIBICIONES_UNIVERSALES_TEXTO,
} from '../defaults';
import { CAPA_KEYS, contarActivosEnCapa } from '../helpers';

/**
 * Paso 5 del wizard: Objeciones (capa 8) + Límites y prohibiciones (capa 9).
 * Incluye revisión final con resumen visual y preview del prompt.
 */
export default function Paso5Limites({ config, setCampo, empresaId }) {
  const f = (key) => config[key] || { activo: false, valor: '' };
  const setActivo = (key) => (a) => setCampo(key, { activo: a });
  const setValor  = (key) => (v) => setCampo(key, { valor: v });

  const alcance = f('alcance_responsabilidad').valor || '';
  const alcanceCount = alcance.length;

  // Resumen final: cuántos campos personalizados tiene cada capa.
  const resumenCapas = [
    { id: 'voz',      label: 'Voz del vendedor',      activos: contarActivosEnCapa(config, CAPA_KEYS.voz),      total: CAPA_KEYS.voz.length },
    { id: 'politica', label: 'Política comercial',    activos: contarActivosEnCapa(config, CAPA_KEYS.politica), total: CAPA_KEYS.politica.length },
    { id: 'cliente',  label: 'Cliente y conversación',activos: contarActivosEnCapa(config, CAPA_KEYS.cliente),  total: CAPA_KEYS.cliente.length },
    { id: 'marca',    label: 'Conocimiento de marca', activos: contarActivosEnCapa(config, CAPA_KEYS.marca),    total: CAPA_KEYS.marca.length },
    { id: 'limites',  label: 'Objeciones y límites',  activos: contarActivosEnCapa(config, CAPA_KEYS.limites),  total: CAPA_KEYS.limites.length },
  ];

  return (
    <div className="via-paso">
      <header className="via-paso-header">
        <h2 className="via-paso-titulo">5. Objeciones, límites y revisión</h2>
        <p className="via-paso-subtitulo">
          Cómo responder cuando el cliente objeta y qué cosas el agente no debe hacer.
        </p>
      </header>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Manejo de objeciones</h3>

        <CampoToggle
          campo="objeciones"
          label="Objeciones del cliente y cómo responderlas"
          helpText="La instrucción guía la respuesta del agente, NO es un script literal."
          activo={f('objeciones').activo}
          onActivoChange={setActivo('objeciones')}
        >
          <EditorListaCompleja
            items={f('objeciones').valor || []}
            onChange={setValor('objeciones')}
            schema={[
              { key: 'objecion',       label: 'Cuando el cliente diga...', type: 'text',     placeholder: 'Ej: Está caro' },
              { key: 'como_responder', label: 'Cómo responder',            type: 'textarea', rows: 3, placeholder: 'Ej: Reconocer, no defender. Preguntar con qué lo compara.' },
            ]}
            maxItems={10}
            itemLabel="Objeción"
            plantillas={PLANTILLAS_OBJECIONES}
            disabled={!f('objeciones').activo}
          />
        </CampoToggle>
      </section>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Límites del agente</h3>

        <PanelInformativo titulo="El agente ya tiene estas prohibiciones por defecto:">
          <ul className="via-panel-info-list">
            {PROHIBICIONES_UNIVERSALES_TEXTO.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
          Acá solo agregás prohibiciones específicas de tu negocio.
        </PanelInformativo>

        <CampoToggle
          campo="prohibiciones"
          label="Prohibiciones específicas de tu negocio"
          activo={f('prohibiciones').activo}
          onActivoChange={setActivo('prohibiciones')}
        >
          <EditorListaSimple
            items={f('prohibiciones').valor || []}
            onChange={setValor('prohibiciones')}
            placeholder="Ej: No hago evaluaciones técnicas que requieran un especialista"
            maxItems={10}
            disabled={!f('prohibiciones').activo}
            ariaLabel="Prohibiciones"
          />
        </CampoToggle>

        <CampoToggle
          campo="alcance_responsabilidad"
          label="Alcance de responsabilidad del agente"
          helpText={`${alcanceCount} / 300 caracteres`}
          activo={f('alcance_responsabilidad').activo}
          onActivoChange={setActivo('alcance_responsabilidad')}
        >
          <textarea
            id="via-alcance"
            className="vom-textarea"
            rows={3}
            maxLength={300}
            placeholder="Ej: Cotizo y tomo pedidos. NO emito facturas, NO proceso pagos."
            value={alcance}
            disabled={!f('alcance_responsabilidad').activo}
            onChange={(e) => setValor('alcance_responsabilidad')(e.target.value)}
          />
        </CampoToggle>
      </section>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Revisión final</h3>

        <div className="via-resumen-capas">
          {resumenCapas.map((c) => {
            const lleno = c.activos > 0;
            return (
              <div
                key={c.id}
                className={`via-resumen-capa ${lleno ? 'completa' : 'pendiente'}`}
              >
                <div className="via-resumen-capa-label">{c.label}</div>
                <div className="via-resumen-capa-badge">
                  {c.activos > 0 ? `${c.activos} de ${c.total}` : 'sin personalizar'}
                </div>
              </div>
            );
          })}
        </div>

        <PreviewPrompt empresaId={empresaId} />
      </section>
    </div>
  );
}
