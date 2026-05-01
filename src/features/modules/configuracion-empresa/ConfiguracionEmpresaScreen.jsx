import { useState } from 'react';
import { Check, CheckCircle2 } from 'lucide-react';
import ModuleLayout from '../ModuleLayout';
import './ConfiguracionEmpresa.css';

const SISTEMAS_CONTABLES = [
  { id: 'concar',   name: 'CONCAR',   description: 'Sistema contable peruano más usado en pymes y constructoras.' },
  { id: 'siscont',  name: 'SISCONT',  description: 'Software contable empresarial multi-empresa.' },
  { id: 'starsoft', name: 'STARSOFT', description: 'ERP integral con módulo contable.' },
  { id: 'siigo',    name: 'SIIGO',    description: 'Software contable cloud para Latinoamérica.' },
];

export default function ConfiguracionEmpresaScreen({ user, onOpenModules, onLogout }) {
  // Default: CONCAR (configurable por tenant en el futuro)
  const [sistemaContable, setSistemaContable] = useState('concar');
  const [justChanged, setJustChanged] = useState(false);

  const handleChange = (id) => {
    setSistemaContable(id);
    setJustChanged(true);
    // Limpia la indicación de "Guardado" después de unos segundos
    setTimeout(() => setJustChanged(false), 2000);
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
                    onChange={() => handleChange(s.id)}
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

          {justChanged && (
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
