import { CampoToggle } from '../../sections';
import ChipsSelector from '../componentes/ChipsSelector';
import EditorListaCompleja from '../componentes/EditorListaCompleja';
import PanelInformativo from '../componentes/PanelInformativo';
import {
  TIPO_CLIENTE_OPCIONES, DATOS_CIERRE_OPCIONES,
  CRITERIOS_DERIVACION_OPCIONES, HORARIO_IA_OPCIONES,
  SUGERENCIAS_DISCOVERY_POR_CLIENTE,
} from '../defaults';

/**
 * Paso 3 del wizard: Cliente y arco conversacional (capa 6).
 * Sub-secciones: Tipo de cliente, Discovery, Datos de cierre,
 * Cuándo derivar, Horario.
 */
export default function Paso3Cliente({ config, setCampo, setSubvalor }) {
  const f = (key) => config[key] || { activo: false, valor: '' };
  const setActivo = (key) => (a) => setCampo(key, { activo: a });
  const setValor  = (key) => (v) => setCampo(key, { valor: v });

  // Sugerencias de discovery según el tipo de cliente seleccionado.
  const tipo = f('tipo_cliente').activo ? f('tipo_cliente').valor : 'mixto';
  const sugerenciasDiscovery = (SUGERENCIAS_DISCOVERY_POR_CLIENTE[tipo] || [])
    .map((q) => ({ pregunta: q, obligatoria: false }));

  return (
    <div className="via-paso">
      <header className="via-paso-header">
        <h2 className="via-paso-titulo">3. Cliente y conversación</h2>
        <p className="via-paso-subtitulo">
          Quién compra, qué información levanta el agente antes de cerrar y cuándo
          escala al asesor humano.
        </p>
      </header>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Tipo de cliente</h3>

        <CampoToggle
          campo="tipo_cliente"
          label="A quién atendés principalmente"
          activo={f('tipo_cliente').activo}
          onActivoChange={setActivo('tipo_cliente')}
        >
          <ChipsSelector
            options={TIPO_CLIENTE_OPCIONES}
            value={f('tipo_cliente').valor}
            onChange={setValor('tipo_cliente')}
            mode="single"
            disabled={!f('tipo_cliente').activo}
            ariaLabel="Tipo de cliente"
          />
        </CampoToggle>
      </section>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Discovery (lo que el agente debe averiguar)</h3>

        <PanelInformativo>
          El agente hace estas preguntas naturalmente, una por turno —
          no como un formulario.
        </PanelInformativo>

        <CampoToggle
          campo="discovery_preguntas"
          label="Preguntas a resolver antes de cerrar"
          activo={f('discovery_preguntas').activo}
          onActivoChange={setActivo('discovery_preguntas')}
        >
          <EditorListaCompleja
            items={f('discovery_preguntas').valor || []}
            onChange={setValor('discovery_preguntas')}
            schema={[
              { key: 'pregunta',    label: 'Pregunta',          type: 'text',   placeholder: 'Ej: ¿Para qué centro de costo es?' },
              { key: 'obligatoria', label: 'Obligatoria',       type: 'switch' },
            ]}
            maxItems={8}
            itemLabel="Pregunta"
            plantillas={sugerenciasDiscovery}
            disabled={!f('discovery_preguntas').activo}
          />
        </CampoToggle>
      </section>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Datos para cerrar la venta</h3>

        <CampoToggle
          campo="datos_cierre_obligatorios"
          label="Datos a pedir al confirmar la compra"
          helpText="Se piden cuando el cliente confirma intención de compra, no antes."
          activo={f('datos_cierre_obligatorios').activo}
          onActivoChange={setActivo('datos_cierre_obligatorios')}
        >
          <ChipsSelector
            options={DATOS_CIERRE_OPCIONES}
            value={f('datos_cierre_obligatorios').valor || []}
            onChange={setValor('datos_cierre_obligatorios')}
            mode="multi"
            disabled={!f('datos_cierre_obligatorios').activo}
            ariaLabel="Datos de cierre"
          />
        </CampoToggle>
      </section>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Cuándo escalar a humano</h3>

        <CampoToggle
          campo="criterios_derivacion"
          label="Casos en los que el agente deriva al humano"
          activo={f('criterios_derivacion').activo}
          onActivoChange={setActivo('criterios_derivacion')}
        >
          <ChipsSelector
            options={CRITERIOS_DERIVACION_OPCIONES}
            value={f('criterios_derivacion').valor || []}
            onChange={setValor('criterios_derivacion')}
            mode="multi"
            disabled={!f('criterios_derivacion').activo}
            ariaLabel="Criterios de derivación"
          />
        </CampoToggle>

        <CampoToggle
          campo="umbral_derivacion_humano"
          label="Derivar pedidos sobre cierto monto"
          helpText="Si el pedido total supera este monto, el agente lo deriva al asesor humano."
          activo={f('umbral_derivacion_humano').activo}
          onActivoChange={setActivo('umbral_derivacion_humano')}
        >
          <input
            id="via-umbral-deriv"
            type="number"
            className="vom-input via-paso-input-numeric"
            min={0}
            placeholder="Ej: 5000"
            value={f('umbral_derivacion_humano').valor ?? ''}
            disabled={!f('umbral_derivacion_humano').activo}
            onChange={(e) => {
              const v = e.target.value === '' ? null : Number(e.target.value);
              setValor('umbral_derivacion_humano')(v);
            }}
          />
        </CampoToggle>

        <CampoToggle
          campo="asesor_humano"
          label="Asesor humano disponible"
          helpText="Nombre y teléfono del asesor al que el agente deriva."
          activo={f('asesor_humano').activo}
          onActivoChange={setActivo('asesor_humano')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field">
              <label htmlFor="via-asesor-nombre">Nombre</label>
              <input
                id="via-asesor-nombre"
                type="text"
                className="vom-input"
                placeholder="Ej: Pedro"
                value={f('asesor_humano').valor?.nombre || ''}
                disabled={!f('asesor_humano').activo}
                onChange={(e) => setSubvalor('asesor_humano', 'nombre', e.target.value)}
              />
            </div>
            <div className="via-paso-field">
              <label htmlFor="via-asesor-tel">Teléfono</label>
              <input
                id="via-asesor-tel"
                type="text"
                className="vom-input"
                placeholder="+51987654321"
                value={f('asesor_humano').valor?.telefono || ''}
                disabled={!f('asesor_humano').activo}
                onChange={(e) => setSubvalor('asesor_humano', 'telefono', e.target.value)}
              />
            </div>
          </div>
        </CampoToggle>
      </section>

      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Horario de la IA</h3>

        <CampoToggle
          campo="horario_ia"
          label="Cuándo responde el agente"
          helpText="Default activo: 24/7. Si elegís 'solo en horario', el agente avisa fuera de horario."
          activo={f('horario_ia').activo}
          onActivoChange={setActivo('horario_ia')}
        >
          <ChipsSelector
            options={HORARIO_IA_OPCIONES}
            value={f('horario_ia').valor}
            onChange={setValor('horario_ia')}
            mode="single"
            disabled={!f('horario_ia').activo}
            ariaLabel="Horario IA"
          />
        </CampoToggle>
      </section>
    </div>
  );
}
