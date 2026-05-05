import { useState, useRef, Fragment } from 'react';
import {
  Upload, X, Check, Clock, FileText, Download,
  ExternalLink, AlertCircle, Loader2, RotateCcw,
} from 'lucide-react';
import ModuleLayout from '../ModuleLayout';
import { API, postJsonAuth, postFormAuth } from '../../../shared/api';
import './FacturasInteligentes.css';

// Estados del proceso (mapean al stepper visual)
const STAGES = {
  UPLOAD:     1,  // Subir + procesar facturas
  VALIDATING: 2,  // Esperar revisión humana en Google Sheet
  CONFIRMING: 3,  // Generando archivo CONCAR
  DONE:       4,  // Listo para descargar
};

const STEPS = [
  { id: 1, label: 'Subir' },
  { id: 2, label: 'Validar' },
  { id: 3, label: 'Confirmar' },
  { id: 4, label: 'Generar' },
];

const STATUS_LABELS = [
  { id: 1, done: 'Facturas procesadas',     current: 'Procesando facturas',    pending: 'Procesar facturas' },
  { id: 2, done: 'Validación completada',   current: 'Pendiente de validación', pending: 'Validación' },
  { id: 3, done: 'Asientos generados',      current: 'Generando asientos',      pending: 'Generar asientos contables' },
  { id: 4, done: 'Archivo exportado',       current: 'Exportando',              pending: 'Exportar archivo CONCAR' },
];

const MES_LABELS = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

function currentMonthValue() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function monthLabelFromValue(value) {
  const [y, m] = value.split('-');
  return `${MES_LABELS[Number(m) - 1]} ${y}`;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ─────────────────────────────────────
// Sub-componentes
// ─────────────────────────────────────

function Stepper({ stage }) {
  return (
    <div className="fact-stepper">
      {STEPS.map((s, idx) => {
        const isDone = stage > s.id;
        const isActive = stage === s.id;
        return (
          <Fragment key={s.id}>
            <div className={`fact-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}>
              <div className="fact-step-circle">
                {isDone ? <Check size={16} /> : s.id}
              </div>
              <div className="fact-step-label">{s.label}</div>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`fact-step-line ${stage > s.id ? 'done' : ''}`} />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}

function StatusList({ stage }) {
  const allDone = stage === STAGES.DONE;
  return (
    <div className="fact-status-list">
      {STATUS_LABELS.map((it) => {
        const isDone = allDone || stage > it.id;
        const isCurrent = !allDone && stage === it.id;
        const label = isDone ? it.done : isCurrent ? it.current : it.pending;
        return (
          <div
            key={it.id}
            className={`fact-status-item ${isDone ? 'done' : ''} ${isCurrent ? 'current' : ''}`}
          >
            <div className="fact-status-icon">
              {isDone ? <Check size={14} /> : isCurrent ? <Clock size={14} /> : null}
            </div>
            <span>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function ErrorBanner({ message }) {
  return (
    <div className="fact-banner fact-banner-error">
      <AlertCircle size={20} className="fact-banner-icon" />
      <div>
        <div className="fact-banner-title">Algo salió mal</div>
        <div>{message}</div>
      </div>
    </div>
  );
}

function MetaPanel({ proceso }) {
  if (!proceso) return null;
  return (
    <div className="fact-meta">
      <div className="fact-meta-row">
        <span className="fact-meta-label">ID del proceso</span>
        <span className="fact-meta-value">{proceso.proceso_id}</span>
      </div>
      <div className="fact-meta-row">
        <span className="fact-meta-label">Empresa</span>
        <span className="fact-meta-value">{proceso.empresa_id}</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────
// Stage 1 — Upload
// ─────────────────────────────────────
function UploadCard({ tipo, setTipo, mes, setMes, files, setFiles, isLoading, onSubmit }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const onPick = (e) => {
    const list = Array.from(e.target.files || []);
    setFiles((prev) => [...prev, ...list]);
    if (inputRef.current) inputRef.current.value = '';
  };

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const list = Array.from(e.dataTransfer.files || []);
    if (list.length) setFiles((prev) => [...prev, ...list]);
  };

  return (
    <div className="fact-card">
      <div className="fact-card-header">
        <h2>Cargar facturas</h2>
        <p>Selecciona el tipo y periodo, adjunta los comprobantes y deja que la IA extraiga los datos.</p>
      </div>

      <div className="fact-form-row">
        <div className="fact-field">
          <label htmlFor="fact-tipo">Tipo</label>
          <select
            id="fact-tipo"
            className="fact-select"
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            disabled={isLoading}
          >
            <option value="compra">Compras</option>
            <option value="venta">Ventas</option>
          </select>
        </div>
        <div className="fact-field">
          <label htmlFor="fact-mes">Mes</label>
          <input
            id="fact-mes"
            type="month"
            className="fact-input"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            disabled={isLoading}
          />
        </div>
      </div>

      <div
        className={`fact-dropzone ${isDragging ? 'dragging' : ''}`}
        onClick={() => !isLoading && inputRef.current?.click()}
        onDragEnter={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
      >
        <div className="fact-dropzone-icon"><Upload size={22} /></div>
        <div className="fact-dropzone-title">
          Arrastra archivos aquí o haz click para seleccionar
        </div>
        <div className="fact-dropzone-hint">PDF, XML o imágenes — múltiples archivos permitidos</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept="application/pdf,application/xml,text/xml,image/*"
          onChange={onPick}
        />
      </div>

      {files.length > 0 && (
        <div className="fact-file-list">
          {files.map((f, idx) => (
            <div key={`${f.name}-${idx}`} className="fact-file-item">
              <FileText size={18} color="var(--md-on-surface-variant)" />
              <span className="fact-file-name">{f.name}</span>
              <span className="fact-file-size">{formatBytes(f.size)}</span>
              <button
                type="button"
                className="fact-file-remove"
                onClick={() => removeFile(idx)}
                disabled={isLoading}
                aria-label="Quitar archivo"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        className="fact-btn fact-btn-primary"
        onClick={onSubmit}
        disabled={isLoading || files.length === 0}
      >
        {isLoading ? <Loader2 size={18} className="spin" /> : <Upload size={18} />}
        {isLoading ? 'Procesando facturas...' : `Procesar ${files.length || ''} factura${files.length === 1 ? '' : 's'}`.trim()}
      </button>
    </div>
  );
}

// ─────────────────────────────────────
// Stage 2 — Validation
// ─────────────────────────────────────
function ValidationCard({ proceso, isLoading, onConfirm, onReset }) {
  return (
    <div className="fact-card">
      <div className="fact-banner fact-banner-success">
        <Check size={20} className="fact-banner-icon" />
        <div>
          <div className="fact-banner-title">Facturas procesadas correctamente</div>
          <div>Revisa, corrige y completa la información contable en la hoja de validación. Cuando esté lista, confirma para generar el archivo CONCAR.</div>
        </div>
      </div>

      <StatusList stage={STAGES.VALIDATING} />

      <MetaPanel proceso={proceso} />

      <div className="fact-btn-row">
        <a
          className="fact-btn fact-btn-secondary"
          href={proceso?.sheet_url || '#'}
          target="_blank"
          rel="noopener noreferrer"
        >
          <ExternalLink size={18} />
          Abrir hoja de validación
        </a>
        <button
          type="button"
          className="fact-btn fact-btn-primary"
          onClick={onConfirm}
          disabled={isLoading}
        >
          {isLoading ? <Loader2 size={18} className="spin" /> : <Check size={18} />}
          Confirmar y generar archivo
        </button>
        <button
          type="button"
          className="fact-btn fact-btn-ghost"
          onClick={onReset}
          disabled={isLoading}
        >
          <RotateCcw size={16} />
          Cancelar
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────
// Stage 3 — Loading
// ─────────────────────────────────────
function LoadingCard({ title, subtitle }) {
  return (
    <div className="fact-card">
      <div className="fact-loading">
        <div className="fact-spinner" />
        <div>
          <div className="fact-loading-title">{title}</div>
          {subtitle && <div className="fact-loading-subtitle">{subtitle}</div>}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────
// Stage 4 — Done
// ─────────────────────────────────────
function DoneCard({ proceso, downloadUrl, onReset }) {
  return (
    <div className="fact-card">
      <div className="fact-banner fact-banner-success">
        <Check size={20} className="fact-banner-icon" />
        <div>
          <div className="fact-banner-title">Archivo contable generado correctamente</div>
          <div>Tu archivo CONCAR está listo para descargar.</div>
        </div>
      </div>

      <StatusList stage={STAGES.DONE} />

      <MetaPanel proceso={proceso} />

      <div className="fact-btn-row">
        <a
          className="fact-btn fact-btn-primary"
          href={downloadUrl || '#'}
          target="_blank"
          rel="noopener noreferrer"
          download
        >
          <Download size={18} />
          Descargar archivo CONCAR
        </a>
        <button type="button" className="fact-btn fact-btn-ghost" onClick={onReset}>
          <RotateCcw size={16} />
          Procesar otro lote
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────
// Main screen
// ─────────────────────────────────────
export default function FacturasInteligentesScreen({ user, onOpenModules, onLogout }) {
  const [stage, setStage] = useState(STAGES.UPLOAD);
  const [tipo, setTipo] = useState('compra');
  const [mes, setMes] = useState(currentMonthValue());
  const [files, setFiles] = useState([]);
  const [proceso, setProceso] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const reset = () => {
    setStage(STAGES.UPLOAD);
    setFiles([]);
    setProceso(null);
    setDownloadUrl('');
    setError('');
    setIsLoading(false);
  };

  const handleProcesar = async () => {
    if (files.length === 0) {
      setError('Adjunta al menos una factura.');
      return;
    }
    setError('');
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('tipo', tipo);
      formData.append('mes', mes);
      formData.append('mes_label', monthLabelFromValue(mes));
      formData.append('dni', user?.dni || '');
      // empresa_id NO se manda — el backend lo resuelve del JWT.
      files.forEach((f) => formData.append('files', f, f.name));

      const data = await postFormAuth(API.FACTURAS_PROCESAR, formData);

      setProceso({
        proceso_id: data.proceso_id || `proc-${Date.now()}`,
        sheet_url:  data.sheet_url  || '#',
        empresa_id: data.empresa_id || '',
      });
      setStage(STAGES.VALIDATING);
    } catch (e) {
      console.error('[facturas/procesar]', e);
      setError('Hubo un problema al procesar las facturas. Intenta de nuevo.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmar = async () => {
    if (!proceso) return;
    setError('');
    setIsLoading(true);
    setStage(STAGES.CONFIRMING);
    try {
      // empresa_id NO se manda — el backend lo resuelve del JWT.
      const data = await postJsonAuth(API.FACTURAS_CONCAR, {
        proceso_id: proceso.proceso_id,
        dni: user?.dni || '',
      });
      setDownloadUrl(data.download_url || data.url || '#');
      setStage(STAGES.DONE);
    } catch (e) {
      console.error('[facturas/concar]', e);
      setError('Hubo un problema al generar el archivo CONCAR. Intenta de nuevo.');
      setStage(STAGES.VALIDATING);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ModuleLayout
      title="Facturas Inteligentes"
      onOpenModules={onOpenModules}
      onLogout={onLogout}
    >
      <div className="fact-screen">
        <Stepper stage={stage} />

        {error && <ErrorBanner message={error} />}

        {stage === STAGES.UPLOAD && (
          <UploadCard
            tipo={tipo} setTipo={setTipo}
            mes={mes} setMes={setMes}
            files={files} setFiles={setFiles}
            isLoading={isLoading}
            onSubmit={handleProcesar}
          />
        )}

        {stage === STAGES.VALIDATING && (
          <ValidationCard
            proceso={proceso}
            isLoading={isLoading}
            onConfirm={handleConfirmar}
            onReset={reset}
          />
        )}

        {stage === STAGES.CONFIRMING && (
          <LoadingCard
            title="Generando asientos contables..."
            subtitle="Esto puede tomar unos segundos"
          />
        )}

        {stage === STAGES.DONE && (
          <DoneCard
            proceso={proceso}
            downloadUrl={downloadUrl}
            onReset={reset}
          />
        )}
      </div>
    </ModuleLayout>
  );
}
