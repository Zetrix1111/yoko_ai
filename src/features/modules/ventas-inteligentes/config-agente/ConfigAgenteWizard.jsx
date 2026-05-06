import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Save, AlertCircle, Loader2, Check } from 'lucide-react';
import { SectionErrorBoundary } from '../sections';
import { useEmpresaConfig } from '../../../../shared/useEmpresaConfig';
import BarraProgreso from './componentes/BarraProgreso';
import PanelInformativo from './componentes/PanelInformativo';
import PantallaInicial from './PantallaInicial';
import Paso1Voz from './pasos/Paso1Voz';
import Paso2Politica from './pasos/Paso2Politica';
import Paso3Cliente from './pasos/Paso3Cliente';
import Paso4Marca from './pasos/Paso4Marca';
import Paso5Limites from './pasos/Paso5Limites';
import { mergeWithDefault, projectToV2, isEqualConfig, CAPA_KEYS, contarActivosEnCapa } from './helpers';
import { DEFAULT_VENTAS_CONFIG_V2 } from './defaults';

const AUTOSAVE_DEBOUNCE_MS = 1500;

// Reducer para mutaciones del config (más predecible que setState directo).
function configReducer(state, action) {
  switch (action.type) {
    case 'reset':
      return action.config;
    case 'setCampo':
      return { ...state, [action.key]: { ...state[action.key], ...action.partial } };
    case 'setSubvalor':
      return {
        ...state,
        [action.key]: {
          ...state[action.key],
          valor: { ...state[action.key]?.valor, [action.subkey]: action.valor },
        },
      };
    default:
      return state;
  }
}

export default function ConfigAgenteWizard({ user }) {
  const { data: backendData, loading, saving, error, save, reload } = useEmpresaConfig('ventas');
  const empresaId = user?.empresa?.id || '';

  const [pasoActual, setPasoActual] = useState(0);  // 0 = pantalla inicial, 1..5 = pasos
  const [config, dispatch] = useReducer(configReducer, DEFAULT_VENTAS_CONFIG_V2);
  const [savedSnapshot, setSavedSnapshot] = useState(DEFAULT_VENTAS_CONFIG_V2);
  const [saveError, setSaveError] = useState('');

  const handleSave = useCallback(async () => {
    setSaveError('');
    const proyectado = projectToV2(config);
    const ok = await save(proyectado);
    if (ok) {
      setSavedSnapshot(proyectado);
    }
    // Si falló, el hook ya setea `error`; no hacemos nada extra acá.
  }, [config, save]);

  // Cargar config inicial desde backend cuando llega. Es seguro setear
  // ambos estados acá porque sucede una sola vez (cargadoRef gate).
  const cargadoRef = useRef(false);
  useEffect(() => {
    if (loading || cargadoRef.current) return;
    if (backendData) {
      const merged = mergeWithDefault(backendData);
      dispatch({ type: 'reset', config: merged });
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSavedSnapshot(merged);
    }
    cargadoRef.current = true;
  }, [backendData, loading]);

  const dirty = useMemo(() => !isEqualConfig(config, savedSnapshot), [config, savedSnapshot]);

  // Autosave debounced cuando hay cambios.
  useEffect(() => {
    if (!dirty || pasoActual === 0) return;
    const t = setTimeout(() => { handleSave(); }, AUTOSAVE_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [dirty, pasoActual, handleSave]);

  const setCampo = (key, partial) => dispatch({ type: 'setCampo', key, partial });
  const setSubvalor = (key, subkey, valor) => dispatch({ type: 'setSubvalor', key, subkey, valor });

  // Pasos completados = capas con al menos 1 campo activo.
  const pasosCompletados = useMemo(() => {
    const set = new Set();
    if (contarActivosEnCapa(config, CAPA_KEYS.voz)      > 0) set.add(1);
    if (contarActivosEnCapa(config, CAPA_KEYS.politica) > 0) set.add(2);
    if (contarActivosEnCapa(config, CAPA_KEYS.cliente)  > 0) set.add(3);
    if (contarActivosEnCapa(config, CAPA_KEYS.marca)    > 0) set.add(4);
    if (contarActivosEnCapa(config, CAPA_KEYS.limites)  > 0) set.add(5);
    return set;
  }, [config]);

  const elegirPlantilla = (plantilla) => {
    dispatch({ type: 'reset', config: mergeWithDefault(plantilla.config) });
    setPasoActual(1);
  };

  if (loading) {
    return (
      <div className="via-wizard-loading">
        <Loader2 size={20} className="spin" /> Cargando configuración...
      </div>
    );
  }

  return (
    <div className="via-wizard-container">
      <header className="via-wizard-header">
        <div className="via-wizard-header-titulos">
          <h1 className="via-wizard-titulo">Configuración del agente IA</h1>
          <span className="via-wizard-tag">Nuevo</span>
        </div>
        <div className="via-wizard-header-status">
          {saving && <span className="via-wizard-status saving"><Loader2 size={14} className="spin" /> Guardando...</span>}
          {!saving && dirty && pasoActual !== 0 && <span className="via-wizard-status dirty">Cambios sin guardar</span>}
          {!saving && !dirty && pasoActual !== 0 && <span className="via-wizard-status saved"><Check size={14} /> Todo guardado</span>}
        </div>
      </header>

      {(error || saveError) && (
        <div className="via-wizard-error">
          <AlertCircle size={16} />
          <div>
            <div><strong>No se pudo guardar.</strong> {saveError || String(error)}</div>
          </div>
          <button type="button" className="vom-btn vom-btn-ghost" onClick={() => { setSaveError(''); reload(); }}>
            Reintentar
          </button>
        </div>
      )}

      {pasoActual !== 0 && (
        <BarraProgreso
          pasoActual={pasoActual}
          pasosCompletados={pasosCompletados}
          onPasoClick={(n) => setPasoActual(n)}
        />
      )}

      <main className="via-wizard-content">
        <SectionErrorBoundary>
          {pasoActual === 0 && (
            <PantallaInicial onElegirPlantilla={elegirPlantilla} />
          )}
          {pasoActual === 1 && (
            <Paso1Voz config={config} setCampo={setCampo} setSubvalor={setSubvalor} />
          )}
          {pasoActual === 2 && (
            <Paso2Politica config={config} setCampo={setCampo} setSubvalor={setSubvalor} />
          )}
          {pasoActual === 3 && (
            <Paso3Cliente config={config} setCampo={setCampo} setSubvalor={setSubvalor} />
          )}
          {pasoActual === 4 && (
            <Paso4Marca config={config} setCampo={setCampo} />
          )}
          {pasoActual === 5 && (
            <Paso5Limites config={config} setCampo={setCampo} empresaId={empresaId} />
          )}
        </SectionErrorBoundary>
      </main>

      {pasoActual !== 0 && (
        <footer className="via-wizard-footer">
          <button
            type="button"
            className="vom-btn vom-btn-ghost"
            onClick={() => setPasoActual(Math.max(1, pasoActual - 1))}
            disabled={pasoActual <= 1}
          >
            <ArrowLeft size={14} /> Anterior
          </button>

          <div className="via-wizard-footer-spacer" />

          <button
            type="button"
            className="vom-btn vom-btn-ghost"
            onClick={handleSave}
            disabled={saving || !dirty}
            title="Guardar este paso (también se autoguarda)"
          >
            <Save size={14} /> Guardar paso
          </button>

          {pasoActual < 5 ? (
            <button
              type="button"
              className="vom-btn vom-btn-primary"
              onClick={() => setPasoActual(pasoActual + 1)}
            >
              Siguiente <ArrowRight size={14} />
            </button>
          ) : (
            <button
              type="button"
              className="vom-btn vom-btn-primary"
              onClick={handleSave}
              disabled={saving}
            >
              <Save size={14} /> Guardar configuración
            </button>
          )}
        </footer>
      )}

      {pasoActual === 0 && (
        <PanelInformativo>
          También podés saltar directo al wizard sin elegir plantilla — empezarás
          con todos los campos en sus defaults universales.
          <div style={{ marginTop: '0.75rem' }}>
            <button
              type="button"
              className="vom-btn vom-btn-ghost"
              onClick={() => setPasoActual(1)}
            >
              Saltar al wizard sin plantilla
            </button>
          </div>
        </PanelInformativo>
      )}
    </div>
  );
}
