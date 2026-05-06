import { CampoToggle } from '../../sections';
import ChipsSelector from '../componentes/ChipsSelector';
import EditorListaSimple from '../componentes/EditorListaSimple';
import {
  TRATAMIENTO_OPCIONES, VOCABULARIO_OPCIONES, CALIDEZ_OPCIONES,
  REGION_OPCIONES, LONGITUD_OPCIONES, USO_LISTAS_OPCIONES, EMOJIS_OPCIONES,
} from '../defaults';

/**
 * Paso 1 del wizard: Voz y personalidad (capa 3 del prompt).
 * Sub-secciones: Identidad, Cómo habla, Cómo escribe.
 */
export default function Paso1Voz({ config, setCampo, setSubvalor }) {
  const f = (key) => config[key] || { activo: false, valor: '' };
  const setActivo = (key) => (a) => setCampo(key, { activo: a });
  const setValor  = (key) => (v) => setCampo(key, { valor: v });

  // Preview de tratamiento (renderiza al lado del select)
  const tratamientoSel = TRATAMIENTO_OPCIONES.find((o) => o.id === f('tratamiento').valor);

  return (
    <div className="via-paso">
      <header className="via-paso-header">
        <h2 className="via-paso-titulo">1. Voz y personalidad</h2>
        <p className="via-paso-subtitulo">
          Cómo habla y escribe el agente. Si no tildas nada, usa un tono cordial neutro.
        </p>
      </header>

      {/* a) Identidad del vendedor */}
      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Identidad del vendedor</h3>

        <CampoToggle
          campo="nombre_vendedor"
          label="Nombre del vendedor"
          helpText="Si lo dejas vacío, el agente no menciona un nombre propio. Default activo: sin nombre."
          activo={f('nombre_vendedor').activo}
          onActivoChange={setActivo('nombre_vendedor')}
        >
          <input
            id="via-nombre_vendedor"
            type="text"
            className="vom-input"
            placeholder="Ej: Carlos"
            value={f('nombre_vendedor').valor || ''}
            disabled={!f('nombre_vendedor').activo}
            onChange={(e) => setValor('nombre_vendedor')(e.target.value)}
            maxLength={40}
          />
        </CampoToggle>
      </section>

      {/* b) Cómo habla */}
      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Cómo habla</h3>

        <CampoToggle
          campo="tratamiento"
          label="Tratamiento al cliente"
          helpText={tratamientoSel ? `Preview: "${tratamientoSel.preview}"` : 'Default activo: tú.'}
          activo={f('tratamiento').activo}
          onActivoChange={setActivo('tratamiento')}
        >
          <ChipsSelector
            options={TRATAMIENTO_OPCIONES}
            value={f('tratamiento').valor}
            onChange={setValor('tratamiento')}
            mode="single"
            disabled={!f('tratamiento').activo}
            ariaLabel="Tratamiento"
          />
        </CampoToggle>

        <CampoToggle
          campo="vocabulario"
          label="Vocabulario"
          helpText="Default activo: neutro."
          activo={f('vocabulario').activo}
          onActivoChange={setActivo('vocabulario')}
        >
          <ChipsSelector
            options={VOCABULARIO_OPCIONES}
            value={f('vocabulario').valor}
            onChange={setValor('vocabulario')}
            mode="single"
            disabled={!f('vocabulario').activo}
            ariaLabel="Vocabulario"
          />
        </CampoToggle>

        <CampoToggle
          campo="calidez"
          label="Calidez del tono"
          helpText="Default activo: cordial."
          activo={f('calidez').activo}
          onActivoChange={setActivo('calidez')}
        >
          <ChipsSelector
            options={CALIDEZ_OPCIONES}
            value={f('calidez').valor}
            onChange={setValor('calidez')}
            mode="single"
            disabled={!f('calidez').activo}
            ariaLabel="Calidez"
          />
        </CampoToggle>
      </section>

      {/* c) Cómo escribe */}
      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Cómo escribe</h3>

        <CampoToggle
          campo="formato_mensaje"
          label="Formato de los mensajes"
          helpText="Cuán largos, cuántas preguntas por turno, si usa listas y signos enfáticos."
          activo={f('formato_mensaje').activo}
          onActivoChange={setActivo('formato_mensaje')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field">
              <label>Longitud preferida</label>
              <ChipsSelector
                options={LONGITUD_OPCIONES}
                value={f('formato_mensaje').valor?.longitud_preferida}
                onChange={(v) => setSubvalor('formato_mensaje', 'longitud_preferida', v)}
                mode="single"
                disabled={!f('formato_mensaje').activo}
              />
            </div>

            <div className="via-paso-field">
              <label htmlFor="via-preguntas-turno">Preguntas por turno</label>
              <input
                id="via-preguntas-turno"
                type="number"
                className="vom-input via-paso-input-numeric"
                min={1}
                max={3}
                value={f('formato_mensaje').valor?.preguntas_por_turno ?? 1}
                disabled={!f('formato_mensaje').activo}
                onChange={(e) => {
                  const n = Math.max(1, Math.min(3, Number(e.target.value) || 1));
                  setSubvalor('formato_mensaje', 'preguntas_por_turno', n);
                }}
              />
            </div>

            <div className="via-paso-field">
              <label>Uso de listas</label>
              <ChipsSelector
                options={USO_LISTAS_OPCIONES}
                value={f('formato_mensaje').valor?.uso_listas}
                onChange={(v) => setSubvalor('formato_mensaje', 'uso_listas', v)}
                mode="single"
                disabled={!f('formato_mensaje').activo}
              />
            </div>

            <div className="via-paso-field via-paso-field-inline">
              <label>
                <input
                  type="checkbox"
                  checked={!!f('formato_mensaje').valor?.puntuacion_enfatica}
                  disabled={!f('formato_mensaje').activo}
                  onChange={(e) => setSubvalor('formato_mensaje', 'puntuacion_enfatica', e.target.checked)}
                />
                {' Permitir signos enfáticos (¡! mayúsculas)'}
              </label>
            </div>
          </div>
        </CampoToggle>

        <CampoToggle
          campo="uso_emojis"
          label="Uso de emojis"
          helpText="Default activo: nunca."
          activo={f('uso_emojis').activo}
          onActivoChange={setActivo('uso_emojis')}
        >
          <ChipsSelector
            options={EMOJIS_OPCIONES}
            value={f('uso_emojis').valor}
            onChange={setValor('uso_emojis')}
            mode="single"
            disabled={!f('uso_emojis').activo}
            ariaLabel="Uso de emojis"
          />
        </CampoToggle>

        <CampoToggle
          campo="localizacion_cultural"
          label="Región y modismos"
          helpText="Cómo habla el agente: español de Perú, neutro, México, etc."
          activo={f('localizacion_cultural').activo}
          onActivoChange={setActivo('localizacion_cultural')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field">
              <label htmlFor="via-region">Región</label>
              <select
                id="via-region"
                className="vom-input"
                value={f('localizacion_cultural').valor?.region || 'neutro_latam'}
                disabled={!f('localizacion_cultural').activo}
                onChange={(e) => setSubvalor('localizacion_cultural', 'region', e.target.value)}
              >
                {REGION_OPCIONES.map((o) => (
                  <option key={o.id} value={o.id}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="via-paso-field">
              <label>Modismos permitidos (opcional)</label>
              <EditorListaSimple
                items={f('localizacion_cultural').valor?.modismos_permitidos || []}
                onChange={(next) => setSubvalor('localizacion_cultural', 'modismos_permitidos', next)}
                placeholder="bacán, chévere, al toque..."
                maxItems={10}
                disabled={!f('localizacion_cultural').activo}
                ariaLabel="Modismos permitidos"
              />
            </div>
          </div>
        </CampoToggle>
      </section>
    </div>
  );
}
