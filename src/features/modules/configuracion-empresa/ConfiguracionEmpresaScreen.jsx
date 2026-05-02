import { useEffect, useState } from 'react';
import { Check, CheckCircle2, Building2, Briefcase, Loader2, AlertCircle, ChevronDown } from 'lucide-react';
import ModuleLayout from '../ModuleLayout';
import { tenantConfig } from '../../../tenants';
import { API, getJson } from '../../../shared/api';
import './ConfiguracionEmpresa.css';

const SISTEMAS_CONTABLES = [
  { id: 'concar',   name: 'CONCAR',   description: 'Sistema contable peruano más usado en pymes y constructoras.' },
  { id: 'siscont',  name: 'SISCONT',  description: 'Software contable empresarial multi-empresa.' },
  { id: 'starsoft', name: 'STARSOFT', description: 'ERP integral con módulo contable.' },
  { id: 'siigo',    name: 'SIIGO',    description: 'Software contable cloud para Latinoamérica.' },
];

function Toggle({ checked, onChange, ariaLabel }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      className={`ce-toggle ${checked ? 'on' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span className="ce-toggle-thumb" />
    </button>
  );
}

export default function ConfiguracionEmpresaScreen({ user, onOpenModules, onLogout }) {
  // Datos de la empresa (default desde el tenant config)
  const [ruc, setRuc] = useState(tenantConfig.ruc || '');
  const [razonSocial, setRazonSocial] = useState(tenantConfig.razonSocial || '');

  // Sistema contable — default CONCAR
  const [sistemaContable, setSistemaContable] = useState('concar');

  const [savedHint, setSavedHint] = useState(false);

  // ── Centros de costo ──
  const [centrosEnabled, setCentrosEnabled] = useState(true);
  const [centros, setCentros] = useState([]);
  const [centrosLoading, setCentrosLoading] = useState(false);
  const [centrosError, setCentrosError] = useState(null);
  const [centrosFetched, setCentrosFetched] = useState(false);
  const [centrosExpanded, setCentrosExpanded] = useState(false);

  useEffect(() => {
    if (!centrosEnabled || centrosFetched) return;

    let cancelled = false;
    setCentrosLoading(true);
    setCentrosError(null);

    getJson(API.CENTROS_COSTO)
      .then((data) => {
        if (cancelled) return;
        setCentros(Array.isArray(data?.centros) ? data.centros : []);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('[centros_costo]', err);
        setCentrosError('No se pudieron cargar los centros de costo.');
      })
      .finally(() => {
        if (cancelled) return;
        setCentrosLoading(false);
        setCentrosFetched(true);
      });

    return () => { cancelled = true; };
  }, [centrosEnabled, centrosFetched]);

  const reintentarCentros = () => {
    setCentrosFetched(false);
    setCentrosError(null);
  };

  const flashSaved = () => {
    setSavedHint(true);
    setTimeout(() => setSavedHint(false), 2000);
  };

  const handleSistemaChange = (id) => {
    setSistemaContable(id);
    flashSaved();
  };

  // RUC peruano: solo dígitos, máximo 11
  const onRucChange = (e) => {
    const onlyDigits = e.target.value.replace(/\D/g, '').slice(0, 11);
    setRuc(onlyDigits);
  };

  return (
    <ModuleLayout
      title="Configuración"
      onOpenModules={onOpenModules}
      onLogout={onLogout}
    >
      <div className="ce-screen">
        <div className="ce-header">
          <h1>Configuración de empresa</h1>
          <p>Ajustes generales que aplican a todos los procesos de tu empresa.</p>
        </div>

        {/* ── Datos de la empresa ── */}
        <div className="ce-card">
          <div className="ce-card-header">
            <div className="ce-card-title-row">
              <div className="ce-card-icon">
                <Building2 size={18} />
              </div>
              <div>
                <h3>Datos de la empresa</h3>
                <p>Información base que aparece en todos los documentos contables generados.</p>
              </div>
            </div>
          </div>

          <div className="ce-form-grid">
            <div className="ce-field">
              <label htmlFor="ruc">RUC</label>
              <input
                id="ruc"
                className="ce-input"
                inputMode="numeric"
                placeholder="20XXXXXXXXX"
                value={ruc}
                onChange={onRucChange}
                maxLength={11}
              />
              <span className="ce-field-hint">11 dígitos · sin espacios ni guiones</span>
            </div>
            <div className="ce-field full">
              <label htmlFor="razon-social">Razón social</label>
              <input
                id="razon-social"
                className="ce-input"
                placeholder="Nombre legal completo"
                value={razonSocial}
                onChange={(e) => setRazonSocial(e.target.value.toUpperCase())}
              />
              <span className="ce-field-hint">Tal como aparece en SUNAT</span>
            </div>
          </div>
        </div>

        {/* ── Sistema contable ── */}
        <div className="ce-card">
          <div className="ce-card-header">
            <h3>Sistema contable</h3>
            <p>
              Selecciona el sistema que usa tu empresa. Los procesos exportarán
              asientos y reportes en el formato compatible con el sistema elegido.
            </p>
          </div>

          <div className="ce-radio-grid">
            {SISTEMAS_CONTABLES.map((s) => {
              const selected = sistemaContable === s.id;
              return (
                <label
                  key={s.id}
                  className={`ce-radio-option ${selected ? 'selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="sistema-contable"
                    value={s.id}
                    checked={selected}
                    onChange={() => handleSistemaChange(s.id)}
                  />
                  <div className="ce-radio-content">
                    <div className="ce-radio-name">{s.name}</div>
                    <div className="ce-radio-desc">{s.description}</div>
                  </div>
                  {selected && (
                    <div className="ce-radio-check" aria-hidden>
                      <Check size={14} strokeWidth={3} />
                    </div>
                  )}
                </label>
              );
            })}
          </div>

          {savedHint && (
            <div className="ce-saved-hint">
              <CheckCircle2 size={14} />
              Cambios guardados
            </div>
          )}
        </div>

        {/* ── Centros de costo ── */}
        <div className={`ce-card ce-config-card ${centrosEnabled ? 'is-on' : ''}`}>
          <div className="ce-config-header">
            <div className="ce-card-title-row">
              <div className="ce-card-icon">
                <Briefcase size={18} />
              </div>
              <div>
                <h3>Centros de costo</h3>
                <p>
                  Activa los centros de costo para asignarlos en solicitudes,
                  facturas, rendiciones y demás procesos. La lista se sincroniza
                  desde la tabla <strong>obras</strong> de Airtable.
                </p>
              </div>
            </div>
            <div className="ce-config-controls">
              <span className="ce-config-summary">
                {centrosEnabled
                  ? (centrosLoading
                      ? 'Cargando…'
                      : `${centros.length} centro${centros.length === 1 ? '' : 's'}`)
                  : 'Desactivado'}
              </span>
              <Toggle
                checked={centrosEnabled}
                onChange={setCentrosEnabled}
                ariaLabel="Activar centros de costo"
              />
            </div>
          </div>

          {centrosEnabled && (
            <div className="ce-config-body">
              {centrosLoading && (
                <div className="ce-list-status">
                  <Loader2 size={16} className="ce-spin" />
                  Cargando centros de costo desde Airtable…
                </div>
              )}

              {centrosError && !centrosLoading && (
                <div className="ce-list-status error">
                  <AlertCircle size={16} />
                  <span>{centrosError}</span>
                  <button type="button" className="ce-link-btn" onClick={reintentarCentros}>
                    Reintentar
                  </button>
                </div>
              )}

              {!centrosLoading && !centrosError && centros.length === 0 && (
                <div className="ce-list-status">
                  No hay centros de costo registrados en la tabla <strong>obras</strong>.
                </div>
              )}

              {!centrosLoading && !centrosError && centros.length > 0 && (
                <>
                  <ul className="ce-cc-list">
                    {(centrosExpanded ? centros : centros.slice(0, 7)).map((c) => (
                      <li key={c.id} className="ce-cc-row">
                        <span className="ce-cc-id">{c.id}</span>
                        <span className="ce-cc-name">{c.obra}</span>
                      </li>
                    ))}
                  </ul>
                  {centros.length > 7 && (
                    <button
                      type="button"
                      className={`ce-cc-toggle ${centrosExpanded ? 'is-open' : ''}`}
                      onClick={() => setCentrosExpanded((v) => !v)}
                    >
                      <ChevronDown size={16} />
                      {centrosExpanded
                        ? 'Ver menos'
                        : `Ver todas las obras (${centros.length})`}
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </ModuleLayout>
  );
}
