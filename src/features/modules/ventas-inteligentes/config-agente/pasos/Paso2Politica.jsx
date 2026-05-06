import { CampoToggle } from '../../sections';
import ChipsSelector from '../componentes/ChipsSelector';
import {
  METODOS_PAGO_OPCIONES, IGV_OPCIONES, COMPROBANTES_OPCIONES,
  MONEDA_OPCIONES, MODELO_ENVIO_OPCIONES, DESCUENTO_VOLUMEN_OPCIONES,
} from '../defaults';

/**
 * Paso 2 del wizard: Política comercial (capa 5).
 * Sub-secciones: Cobertura/Entrega, Pagos/Precios, Reglas comerciales.
 */
export default function Paso2Politica({ config, setCampo, setSubvalor }) {
  const f = (key) => config[key] || { activo: false, valor: '' };
  const setActivo = (key) => (a) => setCampo(key, { activo: a });
  const setValor  = (key) => (v) => setCampo(key, { valor: v });

  return (
    <div className="via-paso">
      <header className="via-paso-header">
        <h2 className="via-paso-titulo">2. Política comercial</h2>
        <p className="via-paso-subtitulo">
          Reglas de cobertura, pagos y precios. El agente solo menciona lo que
          configuras acá; si dejas algo apagado, no inventa.
        </p>
      </header>

      {/* a) Cobertura y entrega */}
      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Cobertura y entrega</h3>

        <CampoToggle
          campo="zona_cobertura"
          label="Zona de cobertura"
          helpText="Si el cliente está fuera de esta zona, el agente lo deriva al humano."
          activo={f('zona_cobertura').activo}
          onActivoChange={setActivo('zona_cobertura')}
        >
          <textarea
            id="via-zona_cobertura"
            className="vom-textarea"
            rows={2}
            placeholder="Ej: Lima Metropolitana y Callao"
            value={f('zona_cobertura').valor || ''}
            disabled={!f('zona_cobertura').activo}
            onChange={(e) => setValor('zona_cobertura')(e.target.value)}
          />
        </CampoToggle>

        <CampoToggle
          campo="tiempo_entrega"
          label="Tiempos de entrega"
          activo={f('tiempo_entrega').activo}
          onActivoChange={setActivo('tiempo_entrega')}
        >
          <input
            id="via-tiempo_entrega"
            type="text"
            className="vom-input"
            placeholder="Ej: 24-48 horas hábiles"
            value={f('tiempo_entrega').valor || ''}
            disabled={!f('tiempo_entrega').activo}
            onChange={(e) => setValor('tiempo_entrega')(e.target.value)}
          />
        </CampoToggle>

        <CampoToggle
          campo="politica_envio"
          label="Política de envío"
          helpText="Cómo se cobra el envío y si hay umbral de envío gratis."
          activo={f('politica_envio').activo}
          onActivoChange={setActivo('politica_envio')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field">
              <label>Modelo de envío</label>
              <ChipsSelector
                options={MODELO_ENVIO_OPCIONES}
                value={f('politica_envio').valor?.modelo}
                onChange={(v) => setSubvalor('politica_envio', 'modelo', v)}
                mode="single"
                disabled={!f('politica_envio').activo}
              />
            </div>

            {f('politica_envio').valor?.modelo === 'fijo' && (
              <div className="via-paso-field">
                <label htmlFor="via-costo-fijo">Costo fijo</label>
                <input
                  id="via-costo-fijo"
                  type="number"
                  className="vom-input via-paso-input-numeric"
                  min={0}
                  value={f('politica_envio').valor?.costo_fijo ?? ''}
                  disabled={!f('politica_envio').activo}
                  onChange={(e) => {
                    const v = e.target.value === '' ? null : Number(e.target.value);
                    setSubvalor('politica_envio', 'costo_fijo', v);
                  }}
                />
              </div>
            )}

            <div className="via-paso-field">
              <label htmlFor="via-envio-gratis">Envío gratis desde (opcional)</label>
              <input
                id="via-envio-gratis"
                type="number"
                className="vom-input via-paso-input-numeric"
                min={0}
                placeholder="Ej: 200"
                value={f('politica_envio').valor?.monto_envio_gratis_desde ?? ''}
                disabled={!f('politica_envio').activo}
                onChange={(e) => {
                  const v = e.target.value === '' ? null : Number(e.target.value);
                  setSubvalor('politica_envio', 'monto_envio_gratis_desde', v);
                }}
              />
            </div>

            <div className="via-paso-field">
              <label htmlFor="via-envio-detalle">Detalle adicional (opcional)</label>
              <textarea
                id="via-envio-detalle"
                className="vom-textarea"
                rows={2}
                placeholder="Ej: Envío en 24h hábiles, gratis a partir de S/ 200"
                value={f('politica_envio').valor?.detalle_libre || ''}
                disabled={!f('politica_envio').activo}
                onChange={(e) => setSubvalor('politica_envio', 'detalle_libre', e.target.value)}
              />
            </div>
          </div>
        </CampoToggle>
      </section>

      {/* b) Pagos y precios */}
      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Pagos y precios</h3>

        <CampoToggle
          campo="metodos_pago"
          label="Métodos de pago aceptados"
          activo={f('metodos_pago').activo}
          onActivoChange={setActivo('metodos_pago')}
        >
          <ChipsSelector
            options={METODOS_PAGO_OPCIONES}
            value={f('metodos_pago').valor || []}
            onChange={setValor('metodos_pago')}
            mode="multi"
            disabled={!f('metodos_pago').activo}
            ariaLabel="Métodos de pago"
          />
        </CampoToggle>

        <CampoToggle
          campo="politica_precios"
          label="Política de precios y comprobantes"
          activo={f('politica_precios').activo}
          onActivoChange={setActivo('politica_precios')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field">
              <label htmlFor="via-igv">IGV</label>
              <select
                id="via-igv"
                className="vom-input"
                value={f('politica_precios').valor?.igv || 'incluido'}
                disabled={!f('politica_precios').activo}
                onChange={(e) => setSubvalor('politica_precios', 'igv', e.target.value)}
              >
                {IGV_OPCIONES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>
            <div className="via-paso-field">
              <label htmlFor="via-comprobantes">Comprobantes</label>
              <select
                id="via-comprobantes"
                className="vom-input"
                value={f('politica_precios').valor?.comprobantes || 'ambos'}
                disabled={!f('politica_precios').activo}
                onChange={(e) => setSubvalor('politica_precios', 'comprobantes', e.target.value)}
              >
                {COMPROBANTES_OPCIONES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>
          </div>
        </CampoToggle>

        <CampoToggle
          campo="moneda"
          label="Moneda principal"
          helpText="Default activo: PEN (Soles)."
          activo={f('moneda').activo}
          onActivoChange={setActivo('moneda')}
        >
          <select
            id="via-moneda"
            className="vom-input"
            value={f('moneda').valor || 'PEN'}
            disabled={!f('moneda').activo}
            onChange={(e) => setValor('moneda')(e.target.value)}
          >
            {MONEDA_OPCIONES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </CampoToggle>
      </section>

      {/* c) Reglas comerciales */}
      <section className="via-paso-section">
        <h3 className="via-paso-section-titulo">Reglas comerciales</h3>

        <CampoToggle
          campo="pedido_minimo"
          label="Pedido mínimo"
          activo={f('pedido_minimo').activo}
          onActivoChange={setActivo('pedido_minimo')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field">
              <label htmlFor="via-min-monto">Monto mínimo</label>
              <input
                id="via-min-monto"
                type="number"
                className="vom-input via-paso-input-numeric"
                min={0}
                value={f('pedido_minimo').valor?.monto ?? 0}
                disabled={!f('pedido_minimo').activo}
                onChange={(e) => setSubvalor('pedido_minimo', 'monto', Number(e.target.value) || 0)}
              />
            </div>
            <div className="via-paso-field">
              <label htmlFor="via-min-comentario">Comentario (opcional)</label>
              <textarea
                id="via-min-comentario"
                className="vom-textarea"
                rows={2}
                placeholder="Ej: Pedido mínimo S/ 50 para delivery"
                value={f('pedido_minimo').valor?.comentario || ''}
                disabled={!f('pedido_minimo').activo}
                onChange={(e) => setSubvalor('pedido_minimo', 'comentario', e.target.value)}
              />
            </div>
          </div>
        </CampoToggle>

        <CampoToggle
          campo="descuento_volumen"
          label="Descuento por volumen"
          helpText="Si el pedido supera cierto monto. NO calcula el descuento — deriva al humano."
          activo={f('descuento_volumen').activo}
          onActivoChange={setActivo('descuento_volumen')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field">
              <label htmlFor="via-dv-umbral">Umbral (monto)</label>
              <input
                id="via-dv-umbral"
                type="number"
                className="vom-input via-paso-input-numeric"
                min={0}
                value={f('descuento_volumen').valor?.umbral_aplica ?? 0}
                disabled={!f('descuento_volumen').activo}
                onChange={(e) => setSubvalor('descuento_volumen', 'umbral_aplica', Number(e.target.value) || 0)}
              />
            </div>
            <div className="via-paso-field">
              <label htmlFor="via-dv-instr">Instrucción</label>
              <select
                id="via-dv-instr"
                className="vom-input"
                value={f('descuento_volumen').valor?.instruccion || 'derivar_humano'}
                disabled={!f('descuento_volumen').activo}
                onChange={(e) => setSubvalor('descuento_volumen', 'instruccion', e.target.value)}
              >
                {DESCUENTO_VOLUMEN_OPCIONES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>
          </div>
        </CampoToggle>

        <CampoToggle
          campo="politica_devoluciones"
          label="Política de devoluciones"
          activo={f('politica_devoluciones').activo}
          onActivoChange={setActivo('politica_devoluciones')}
        >
          <div className="via-paso-subsection">
            <div className="via-paso-field via-paso-field-inline">
              <label>
                <input
                  type="checkbox"
                  checked={!!f('politica_devoluciones').valor?.acepta_devolucion}
                  disabled={!f('politica_devoluciones').activo}
                  onChange={(e) => setSubvalor('politica_devoluciones', 'acepta_devolucion', e.target.checked)}
                />
                {' Aceptamos devoluciones'}
              </label>
            </div>

            <div className="via-paso-field">
              <label htmlFor="via-dev-plazo">Plazo (días)</label>
              <input
                id="via-dev-plazo"
                type="number"
                className="vom-input via-paso-input-numeric"
                min={0}
                value={f('politica_devoluciones').valor?.plazo_dias ?? 7}
                disabled={!f('politica_devoluciones').activo || !f('politica_devoluciones').valor?.acepta_devolucion}
                onChange={(e) => setSubvalor('politica_devoluciones', 'plazo_dias', Number(e.target.value) || 0)}
              />
            </div>

            <div className="via-paso-field">
              <label htmlFor="via-dev-cond">Condiciones (opcional)</label>
              <textarea
                id="via-dev-cond"
                className="vom-textarea"
                rows={2}
                placeholder="Ej: Producto sin uso y en empaque original"
                value={f('politica_devoluciones').valor?.condiciones || ''}
                disabled={!f('politica_devoluciones').activo || !f('politica_devoluciones').valor?.acepta_devolucion}
                onChange={(e) => setSubvalor('politica_devoluciones', 'condiciones', e.target.value)}
              />
            </div>
          </div>
        </CampoToggle>

        <CampoToggle
          campo="garantia"
          label="Garantía"
          activo={f('garantia').activo}
          onActivoChange={setActivo('garantia')}
        >
          <textarea
            id="via-garantia"
            className="vom-textarea"
            rows={2}
            placeholder="Ej: 1 año del fabricante"
            value={f('garantia').valor || ''}
            disabled={!f('garantia').activo}
            onChange={(e) => setValor('garantia')(e.target.value)}
          />
        </CampoToggle>
      </section>
    </div>
  );
}
