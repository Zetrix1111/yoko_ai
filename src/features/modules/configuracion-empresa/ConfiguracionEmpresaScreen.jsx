import { useState } from 'react';
import { Check, CheckCircle2, Building2 } from 'lucide-react';
import ModuleLayout from '../ModuleLayout';
import { tenantConfig } from '../../../tenants';
import './ConfiguracionEmpresa.css';

const SISTEMAS_CONTABLES = [
  { id: 'concar',   name: 'CONCAR',   description: 'Sistema contable peruano más usado en pymes y constructoras.' },
  { id: 'siscont',  name: 'SISCONT',  description: 'Software contable empresarial multi-empresa.' },
  { id: 'starsoft', name: 'STARSOFT', description: 'ERP integral con módulo contable.' },
  { id: 'siigo',    name: 'SIIGO',    description: 'Software contable cloud para Latinoamérica.' },
];

export default function ConfiguracionEmpresaScreen({ user, onOpenModules, onLogout }) {
  // Datos de la empresa (default desde el tenant config)
  const [ruc, setRuc] = useState(tenantConfig.ruc || '');
  const [razonSocial, setRazonSocial] = useState(tenantConfig.razonSocial || '');

  // Sistema contable — default CONCAR
  const [sistemaContable, setSistemaContable] = useState('concar');

  const [savedHint, setSavedHint] = useState(false);

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
      </div>
    </ModuleLayout>
  );
}
