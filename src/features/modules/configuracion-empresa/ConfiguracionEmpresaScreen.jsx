import { useEffect, useState } from 'react';
import {
  Check, CheckCircle2, Building2, Briefcase, Loader2, AlertCircle, ChevronDown,
  Plus, Trash2, Sparkles,
} from 'lucide-react';
import ModuleLayout from '../ModuleLayout';
import { API, getJsonAuth } from '../../../shared/api';
import { useEmpresaConfig } from '../../../shared/useEmpresaConfig';
import Toggle from '../../../shared/components/Toggle';
import './ConfiguracionEmpresa.css';

// ─────────────────────────────────────────────────────────────────────────
// info_extendida — schema y defaults (mismo shape que api/empresa_config.py)
// ─────────────────────────────────────────────────────────────────────────

const REDES_OPCIONES = [
  { id: 'instagram', label: 'Instagram' },
  { id: 'facebook',  label: 'Facebook' },
  { id: 'linkedin',  label: 'LinkedIn' },
  { id: 'tiktok',    label: 'TikTok' },
  { id: 'whatsapp',  label: 'WhatsApp' },
  { id: 'youtube',   label: 'YouTube' },
  { id: 'otro',      label: 'Otro' },
];

const DEFAULT_INFO_EXTENDIDA = {
  rubro:            { activo: false, valor: '' },
  descripcion:      { activo: false, valor: '' },
  direccion:        { activo: false, valor: '' },
  email_contacto:   { activo: false, valor: '' },
  horario_atencion: { activo: false, valor: '' },
  redes_sociales:   { activo: false, valor: [] },
};

const SISTEMAS_CONTABLES = [
  { id: 'concar',   name: 'CONCAR',   description: 'Sistema contable peruano más usado en pymes y constructoras.' },
  { id: 'siscont',  name: 'SISCONT',  description: 'Software contable empresarial multi-empresa.' },
  { id: 'starsoft', name: 'STARSOFT', description: 'ERP integral con módulo contable.' },
  { id: 'siigo',    name: 'SIIGO',    description: 'Software contable cloud para Latinoamérica.' },
];

// ─────────────────────────────────────────────────────────────────────────
// Helpers de campo para "Información extendida"
// ─────────────────────────────────────────────────────────────────────────

/**
 * Wrapper genérico de una fila de campo: toggle + label + children (input/textarea/etc).
 * El input se deshabilita visualmente cuando el toggle está off.
 */
function CampoRow({ campo, label, activo, onActivoChange, helpText, children }) {
  return (
    <div className={`ce-campo-row ${activo ? '' : 'disabled'}`}>
      <div className="ce-campo-header">
        <Toggle classPrefix="ce" checked={activo} onChange={onActivoChange} ariaLabel={label} />
        <label className="ce-campo-label" htmlFor={`ce-campo-${campo}`}>
          {label}
          <span className="ce-campo-optional"> (opcional)</span>
        </label>
      </div>
      <div className="ce-campo-input-wrap">
        {children}
      </div>
      <div className="ce-campo-help">{helpText}</div>
    </div>
  );
}

function CampoTexto({ campo, label, helpText, placeholder, type = 'text', activo, valor, onActivoChange, onValorChange }) {
  return (
    <CampoRow campo={campo} label={label} activo={activo} onActivoChange={onActivoChange} helpText={helpText}>
      <input
        id={`ce-campo-${campo}`}
        className="ce-input"
        type={type}
        placeholder={placeholder}
        value={valor}
        disabled={!activo}
        onChange={(e) => onValorChange(e.target.value)}
      />
    </CampoRow>
  );
}

function CampoTextarea({ campo, label, helpText, placeholder, maxLength = 300, activo, valor, onActivoChange, onValorChange }) {
  const len = (valor || '').length;
  return (
    <CampoRow campo={campo} label={label} activo={activo} onActivoChange={onActivoChange} helpText={helpText}>
      <textarea
        id={`ce-campo-${campo}`}
        className="ce-input ce-textarea"
        placeholder={placeholder}
        value={valor}
        disabled={!activo}
        maxLength={maxLength}
        rows={3}
        onChange={(e) => onValorChange(e.target.value)}
      />
      <div className="ce-textarea-counter">{len} / {maxLength}</div>
    </CampoRow>
  );
}

function CampoRedes({ campo, label, helpText, activo, valor, onActivoChange, onValorChange }) {
  const lista = Array.isArray(valor) ? valor : [];

  const updateItem = (idx, patch) => {
    const next = lista.map((item, i) => i === idx ? { ...item, ...patch } : item);
    onValorChange(next);
  };
  const removeItem = (idx) => {
    onValorChange(lista.filter((_, i) => i !== idx));
  };
  const addItem = () => {
    onValorChange([...lista, { red: 'instagram', url: '' }]);
  };

  return (
    <CampoRow campo={campo} label={label} activo={activo} onActivoChange={onActivoChange} helpText={helpText}>
      <div className="ce-redes-list">
        {lista.map((item, idx) => {
          const urlOk = !item.url || /^https?:\/\//i.test(item.url);
          return (
            <div key={idx} className="ce-redes-row">
              <select
                className="ce-redes-select"
                value={item.red || 'instagram'}
                disabled={!activo}
                onChange={(e) => updateItem(idx, { red: e.target.value })}
              >
                {REDES_OPCIONES.map((o) => (
                  <option key={o.id} value={o.id}>{o.label}</option>
                ))}
              </select>
              <input
                className={`ce-input ce-redes-url ${!urlOk ? 'warn' : ''}`}
                type="url"
                placeholder="https://..."
                value={item.url || ''}
                disabled={!activo}
                onChange={(e) => updateItem(idx, { url: e.target.value })}
              />
              <button
                type="button"
                className="ce-redes-remove"
                onClick={() => removeItem(idx)}
                disabled={!activo}
                aria-label="Eliminar red"
              >
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
        <button
          type="button"
          className="ce-redes-add"
          onClick={addItem}
          disabled={!activo}
        >
          <Plus size={14} /> Agregar red social
        </button>
      </div>
    </CampoRow>
  );
}

export default function ConfiguracionEmpresaScreen({ user, onOpenModules, onLogout }) {
  // Persistencia centralizada en Airtable (paso 6).
  // Esta pantalla lee y escribe la fila de Config_Empresa.data, que también
  // contiene `proceso` (lo edita Gestión Caja Chica). Al guardar hay que
  // preservar `proceso` para no pisarlo.
  const { data, loading: configLoading, saving: configSaving, save: saveConfig } = useEmpresaConfig('empresa');

  // Datos básicos
  const [name, setName] = useState('');
  const [ruc, setRuc] = useState('');
  const [razonSocial, setRazonSocial] = useState('');
  const [sistemaContable, setSistemaContable] = useState('concar');

  const [savedHint, setSavedHint] = useState(false);
  const [empresaSaveError, setEmpresaSaveError] = useState(null);

  // Información extendida
  const [infoExtendida, setInfoExtendida] = useState(DEFAULT_INFO_EXTENDIDA);
  const [infoSaving, setInfoSaving] = useState(false);
  const [infoSavedHint, setInfoSavedHint] = useState(false);
  const [infoSaveError, setInfoSaveError] = useState(null);
  const infoLoaded = !configLoading;

  // Hidratar el form cuando llegan los datos de Airtable.
  useEffect(() => {
    if (!data) return;
    const basicos = data.basicos || {};
    setName(basicos.name || '');
    setRuc(basicos.ruc || '');
    setRazonSocial(basicos.razon_social || '');
    setSistemaContable(basicos.sistema_contable || 'concar');

    if (data.info_extendida) {
      const merged = { ...DEFAULT_INFO_EXTENDIDA };
      for (const key of Object.keys(merged)) {
        if (data.info_extendida[key]) {
          merged[key] = {
            activo: !!data.info_extendida[key].activo,
            valor:  data.info_extendida[key].valor ?? merged[key].valor,
          };
        }
      }
      setInfoExtendida(merged);
    }
  }, [data]);

  const setActivo = (campo, activo) =>
    setInfoExtendida((prev) => ({ ...prev, [campo]: { ...prev[campo], activo } }));

  const setValor = (campo, valor) =>
    setInfoExtendida((prev) => ({ ...prev, [campo]: { ...prev[campo], valor } }));

  // Guardar info_extendida — preserva basicos, proceso y centros_costo.
  const handleSaveInfoExtendida = async () => {
    setInfoSaving(true);
    setInfoSaveError(null);
    try {
      const payload = {
        basicos: data?.basicos || { name, razon_social: razonSocial, ruc, sistema_contable: sistemaContable },
        info_extendida: infoExtendida,
        proceso: data?.proceso || {},
        centros_costo: data?.centros_costo || { activo: centrosEnabled },
      };
      const ok = await saveConfig(payload);
      if (ok) {
        setInfoSavedHint(true);
        setTimeout(() => setInfoSavedHint(false), 2500);
      } else {
        setInfoSaveError('No se pudo guardar. Intentá de nuevo.');
      }
    } finally {
      setInfoSaving(false);
    }
  };

  // ── Centros de costo ──
  // Estado del toggle persistido en Config_Empresa.data.centros_costo.activo.
  // Tenants sin la key arrancan en `true` (default histórico).
  const [centrosEnabled, setCentrosEnabled] = useState(true);
  const [centrosSaving, setCentrosSaving] = useState(false);
  const [centrosSaveError, setCentrosSaveError] = useState(null);
  const [centros, setCentros] = useState([]);
  const [centrosLoading, setCentrosLoading] = useState(false);
  const [centrosError, setCentrosError] = useState(null);
  const [centrosFetched, setCentrosFetched] = useState(false);
  const [centrosExpanded, setCentrosExpanded] = useState(false);

  // Hidratar el toggle desde el backend cuando llega la config. Es seguro
  // setear state acá porque sucede solo cuando cambia el valor persistido.
  useEffect(() => {
    const persisted = data?.centros_costo?.activo;
    if (typeof persisted === 'boolean') {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCentrosEnabled(persisted);
    }
  }, [data?.centros_costo?.activo]);

  useEffect(() => {
    if (!centrosEnabled || centrosFetched) return;

    let cancelled = false;
    setCentrosLoading(true);
    setCentrosError(null);

    getJsonAuth(API.CENTROS_COSTO)
      .then((res) => {
        if (cancelled) return;
        setCentros(Array.isArray(res?.centros) ? res.centros : []);
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

  // Persistir el toggle en Config_Empresa.data con optimistic update.
  // Si el save falla, revierte y muestra error.
  const handleToggleCentros = async (next) => {
    setCentrosEnabled(next);          // optimistic
    setCentrosSaveError(null);
    setCentrosSaving(true);

    const payload = {
      basicos:        data?.basicos || {
        name, razon_social: razonSocial, ruc, sistema_contable: sistemaContable,
      },
      info_extendida: data?.info_extendida || infoExtendida,
      proceso:        data?.proceso || {},
      centros_costo:  { activo: next },
    };
    const ok = await saveConfig(payload);
    if (!ok) {
      setCentrosEnabled(!next);       // revertir
      setCentrosSaveError('No se pudo guardar el cambio.');
    }
    setCentrosSaving(false);
  };

  // Persiste los datos básicos en Airtable (paso 6).
  // IMPORTANTE: incluye info_extendida, proceso y centros_costo intactos
  // para no pisarlos.
  const handleSaveEmpresa = async () => {
    setEmpresaSaveError(null);
    const payload = {
      basicos: {
        name:             name.trim(),
        razon_social:     razonSocial.trim(),
        ruc:              ruc.trim(),
        sistema_contable: sistemaContable,
      },
      info_extendida: data?.info_extendida || infoExtendida,
      proceso:        data?.proceso || {},
      centros_costo:  data?.centros_costo || { activo: centrosEnabled },
    };
    const ok = await saveConfig(payload);
    if (ok) {
      setSavedHint(true);
      setTimeout(() => setSavedHint(false), 2500);
    } else {
      setEmpresaSaveError('No se pudo guardar. Intentá de nuevo.');
    }
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
            <div className="ce-field">
              <label htmlFor="nombre-comercial">Nombre comercial</label>
              <input
                id="nombre-comercial"
                className="ce-input"
                placeholder="Ej: C. Mejía"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <span className="ce-field-hint">Cómo se conoce a la empresa coloquialmente</span>
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
                    onChange={() => setSistemaContable(s.id)}
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

          <div className="ce-section-actions">
            <button
              type="button"
              className="ce-btn-primary"
              onClick={handleSaveEmpresa}
              disabled={configSaving || configLoading}
            >
              {configSaving ? (
                <><Loader2 size={14} className="ce-spin" /> Guardando...</>
              ) : (
                <>Guardar datos de la empresa</>
              )}
            </button>
            {savedHint && (
              <span className="ce-saved-hint inline">
                <CheckCircle2 size={14} /> Guardado
              </span>
            )}
            {empresaSaveError && (
              <span className="ce-save-error">
                <AlertCircle size={14} /> {empresaSaveError}
              </span>
            )}
          </div>
        </div>

        {/* ── Información extendida (info_extendida) ── */}
        <div className="ce-card">
          <div className="ce-card-header">
            <div className="ce-card-title-row">
              <div className="ce-card-icon">
                <Sparkles size={18} />
              </div>
              <div>
                <h3>Información extendida</h3>
                <p>
                  Datos opcionales que enriquecen el contexto que tienen las IAs sobre tu empresa.
                  Activá solo los campos que quieras compartir; los apagados no se incluyen en el
                  comportamiento de las IAs.
                </p>
              </div>
            </div>
          </div>

          <div className="ce-campos-list">
            {!infoLoaded && (
              <div className="ce-list-status">
                <Loader2 size={14} className="ce-spin" />
                Cargando información...
              </div>
            )}

            <CampoTexto
              campo="rubro"
              label="Rubro / actividad principal"
              helpText="Texto corto que define a qué se dedica la empresa. Ej: 'Construcción civil y suministro de materiales para obras'."
              placeholder="Construcción civil y suministro de materiales..."
              activo={infoExtendida.rubro.activo}
              valor={infoExtendida.rubro.valor}
              onActivoChange={(v) => setActivo('rubro', v)}
              onValorChange={(v) => setValor('rubro', v)}
            />

            <CampoTextarea
              campo="descripcion"
              label="Descripción de la empresa"
              helpText="1-2 oraciones describiendo a la empresa. Aparece cuando el cliente pregunta '¿quiénes son ustedes?'."
              placeholder="Empresa peruana con 20 años de experiencia en proyectos eléctricos..."
              maxLength={300}
              activo={infoExtendida.descripcion.activo}
              valor={infoExtendida.descripcion.valor}
              onActivoChange={(v) => setActivo('descripcion', v)}
              onValorChange={(v) => setValor('descripcion', v)}
            />

            <CampoTexto
              campo="direccion"
              label="Dirección física"
              helpText="Dirección física principal (oficina o almacén). Incluí distrito y ciudad."
              placeholder="Av. Javier Prado 1234, San Isidro, Lima"
              activo={infoExtendida.direccion.activo}
              valor={infoExtendida.direccion.valor}
              onActivoChange={(v) => setActivo('direccion', v)}
              onValorChange={(v) => setValor('direccion', v)}
            />

            <CampoTexto
              campo="email_contacto"
              label="Email de contacto"
              helpText="Email de contacto general que el agente puede compartir con clientes."
              placeholder="contacto@empresa.com"
              type="email"
              activo={infoExtendida.email_contacto.activo}
              valor={infoExtendida.email_contacto.valor}
              onActivoChange={(v) => setActivo('email_contacto', v)}
              onValorChange={(v) => setValor('email_contacto', v)}
            />

            <CampoTexto
              campo="horario_atencion"
              label="Horario de atención"
              helpText="Horario en lenguaje natural. Ej: 'Lunes a viernes 8am-6pm, sábados 8am-1pm'."
              placeholder="Lunes a viernes 8am-6pm"
              activo={infoExtendida.horario_atencion.activo}
              valor={infoExtendida.horario_atencion.valor}
              onActivoChange={(v) => setActivo('horario_atencion', v)}
              onValorChange={(v) => setValor('horario_atencion', v)}
            />

            <CampoRedes
              campo="redes_sociales"
              label="Redes sociales"
              helpText="Redes sociales activas de la empresa. El agente puede mencionarlas si el cliente pide más info."
              activo={infoExtendida.redes_sociales.activo}
              valor={infoExtendida.redes_sociales.valor}
              onActivoChange={(v) => setActivo('redes_sociales', v)}
              onValorChange={(v) => setValor('redes_sociales', v)}
            />
          </div>

          <div className="ce-section-actions">
            <button
              type="button"
              className="ce-btn-primary"
              onClick={handleSaveInfoExtendida}
              disabled={infoSaving}
            >
              {infoSaving ? (
                <><Loader2 size={14} className="ce-spin" /> Guardando...</>
              ) : (
                <>Guardar</>
              )}
            </button>
            {infoSavedHint && (
              <span className="ce-saved-hint inline">
                <CheckCircle2 size={14} /> Guardado
              </span>
            )}
            {infoSaveError && (
              <span className="ce-save-error">
                <AlertCircle size={14} /> {infoSaveError}
              </span>
            )}
          </div>
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
                {centrosSaving
                  ? 'Guardando…'
                  : centrosEnabled
                    ? (centrosLoading
                        ? 'Cargando…'
                        : `${centros.length} centro${centros.length === 1 ? '' : 's'}`)
                    : 'Desactivado'}
              </span>
              <Toggle
                classPrefix="ce"
                checked={centrosEnabled}
                onChange={handleToggleCentros}
                ariaLabel="Activar centros de costo"
              />
            </div>
          </div>

          {centrosSaveError && (
            <div className="ce-list-status error">
              <AlertCircle size={16} />
              <span>{centrosSaveError}</span>
            </div>
          )}

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
