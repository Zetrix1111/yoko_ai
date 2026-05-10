import { useCallback, useEffect, useState, useRef, Fragment } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Upload, X, Check, Clock, FileText, Download,
  AlertCircle, Loader2, RotateCcw,
  TrendingUp, Wallet, ClipboardList, FileSpreadsheet,
  MessageSquare, ArrowRight,
} from 'lucide-react';
import { API, apiFetch, postFormAuth, getAuthToken } from '../../../shared/api';
import FacturasTable from './components/FacturasTable';
import useRecuperarSesion from './hooks/useRecuperarSesion';

// ─────────────────────────────────────────────────────────────────────────
// Constantes compartidas (replicadas del legacy FacturasInteligentesScreen)
// ─────────────────────────────────────────────────────────────────────────

const STAGES = {
  UPLOAD:     1,
  VALIDATING: 2,
  CONFIRMING: 3,
  DONE:       4,
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

// ─────────────────────────────────────────────────────────────────────────
// Mapeo tipo_doc → sub_diario CONCAR. Espejo del backend
// (api/_lib/registro_contable/templates/concar.py:DEFAULTS["sub_diarios"]).
// Si tocás uno, tocá el otro.
// ─────────────────────────────────────────────────────────────────────────
const SUB_DIARIO_BY_TIPO_DOC = {
  FT: '11', NC: '11', ND: '11', BA: '11', TK: '11',
  BV: '13',
  RH: '15',
};

const SUB_DIARIO_LABELS = {
  '11': 'Facturas / Tickets / Notas',
  '13': 'Boletas',
  '15': 'Recibos por honorarios',
};

function computeSubDiariosPresentes(facturas) {
  const counts = {};
  for (const f of (facturas || [])) {
    const tipo = String(f?.tipo_doc_codigo || 'FT').toUpperCase();
    const sd = SUB_DIARIO_BY_TIPO_DOC[tipo] || '11';
    counts[sd] = (counts[sd] || 0) + 1;
  }
  return counts;
}

// ─────────────────────────────────────────────────────────────────────────
// Sub-componentes UI (movidos desde FacturasInteligentesScreen.jsx)
// ─────────────────────────────────────────────────────────────────────────

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
        <div className="fact-dropzone-hint">PDF o imágenes — múltiples archivos permitidos</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept="application/pdf,image/*"
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

// ─────────────────────────────────────────────────────────────────────────
// CorrelativosPanel: inputs para el correlativo inicial por sub_diario.
// Se renderiza arriba del botón "Conforme" y solo muestra los sub_diarios
// presentes en el lote (ej: si solo hay facturas, solo aparece sub 11).
// El cálculo del numero_comprobante (MM + zfill) vive en el backend
// (api/_lib/registro_contable/engine.py); acá solo recolectamos input.
// ─────────────────────────────────────────────────────────────────────────
function CorrelativosPanel({ facturas, correlativos, setCorrelativos }) {
  const counts = computeSubDiariosPresentes(facturas);
  const presentes = Object.keys(counts).sort();
  if (presentes.length === 0) return null;

  return (
    <div className="fact-correlativos">
      <h3 className="fact-correlativos-title">Correlativo inicial por tipo</h3>
      <p className="fact-correlativos-desc">
        Cada comprobante del Excel tendrá su número de comprobante con
        formato <code>MMNNNN</code> (mes + correlativo de 4 dígitos).
        Decide desde qué número arranca cada secuencia. Las secuencias
        son independientes por tipo.
      </p>
      {presentes.map((sd) => {
        const cantidad = counts[sd];
        const inicial = correlativos[sd] ?? '';
        const numInicial = parseInt(inicial, 10);
        const finalEstimado = Number.isFinite(numInicial)
          ? numInicial + cantidad - 1
          : null;
        const overflow = finalEstimado !== null && finalEstimado > 9999;

        return (
          <div key={sd} className="fact-correlativo-row">
            <label className="fact-correlativo-label">
              {SUB_DIARIO_LABELS[sd] || `Sub-diario ${sd}`}{' '}
              <span className="fact-correlativo-meta">
                ({cantidad} comprobante{cantidad !== 1 ? 's' : ''}, sub {sd})
              </span>
            </label>
            <input
              type="number"
              min="1"
              className="fact-input fact-correlativo-input"
              value={inicial}
              onChange={(e) => {
                const v = e.target.value;
                setCorrelativos((prev) => ({
                  ...prev,
                  [sd]: v === '' ? '' : Number(v),
                }));
              }}
              placeholder="Ej: 20"
            />
            {Number.isFinite(numInicial) && numInicial >= 1 && (
              <small className="fact-correlativo-hint">
                Va de {numInicial} a {finalEstimado} ({cantidad} comprobante{cantidad !== 1 ? 's' : ''}).
              </small>
            )}
            {overflow && (
              <small className="fact-correlativo-warn">
                ⚠️ {numInicial} + {cantidad} llega a {finalEstimado},
                sobrepasa los 4 dígitos del formato CONCAR. El archivo
                igual se descarga, pero CONCAR puede rechazarlo al importar.
              </small>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ValidationCard({
  proceso, facturas, setFacturas, errores, isLoading, onConfirm, onReset,
  correlativos, setCorrelativos,
  compact = false,
}) {
  const numExitosas = facturas?.length || 0;
  const numFallidas = errores?.length || 0;

  return (
    <div className="fact-card">
      <div className="fact-banner fact-banner-success">
        <Check size={20} className="fact-banner-icon" />
        <div>
          <div className="fact-banner-title">
            {numExitosas} factura{numExitosas !== 1 ? 's' : ''} procesada{numExitosas !== 1 ? 's' : ''}
          </div>
          <div>
            Revisa, corrige y completa la información en la tabla. Los cambios se
            guardan automáticamente. Cuando esté lista, confirma para generar el
            archivo y volver al chat.
          </div>
        </div>
      </div>

      {numFallidas > 0 && (
        <div className="fact-banner fact-banner-error">
          <AlertCircle size={20} className="fact-banner-icon" />
          <div>
            <div className="fact-banner-title">
              {numFallidas} archivo{numFallidas !== 1 ? 's' : ''} no se pudo procesar
            </div>
            <div>Revisá los nombres en la consola y subilos de nuevo si hace falta.</div>
          </div>
        </div>
      )}

      {!compact && <StatusList stage={STAGES.VALIDATING} />}

      <MetaPanel proceso={proceso} />

      <FacturasTable
        proceso={proceso}
        facturas={facturas}
        setFacturas={setFacturas}
      />

      <CorrelativosPanel
        facturas={facturas}
        correlativos={correlativos}
        setCorrelativos={setCorrelativos}
      />

      <div className="fact-btn-row">
        <button
          type="button"
          className="fact-btn fact-btn-primary"
          onClick={onConfirm}
          disabled={isLoading || numExitosas === 0}
        >
          {isLoading ? <Loader2 size={18} className="spin" /> : <Check size={18} />}
          {compact
            ? 'Conforme · descargar y volver al chat'
            : 'Confirmar y generar archivo'}
        </button>
        {!compact && (
          <button
            type="button"
            className="fact-btn fact-btn-ghost"
            onClick={onReset}
            disabled={isLoading}
          >
            <RotateCcw size={16} />
            Cancelar
          </button>
        )}
      </div>
    </div>
  );
}

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

function DoneCard({ proceso, onDownloadAgain, onReset }) {
  return (
    <div className="fact-card">
      <div className="fact-banner fact-banner-success">
        <Check size={20} className="fact-banner-icon" />
        <div>
          <div className="fact-banner-title">Archivo CONCAR descargado</div>
          <div>
            El archivo ya se descargó automáticamente. Si no lo encontrás,
            podés volver a generarlo con el botón de abajo.
          </div>
        </div>
      </div>

      <StatusList stage={STAGES.DONE} />

      <MetaPanel proceso={proceso} />

      <div className="fact-btn-row">
        <button
          type="button"
          className="fact-btn fact-btn-primary"
          onClick={onDownloadAgain}
        >
          <Download size={18} />
          Volver a descargar
        </button>
        <button type="button" className="fact-btn fact-btn-ghost" onClick={onReset}>
          <RotateCcw size={16} />
          Procesar otro lote
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Sub-pantalla 1 · Dashboard (placeholder)
// ─────────────────────────────────────────────────────────────────────────

const STAT_CARDS = [
  { id: 'procesos',     label: 'Procesos este mes',          value: '12', hint: 'mock', Icon: TrendingUp },
  { id: 'comprobantes', label: 'Comprobantes procesados',    value: '87', hint: 'mock', Icon: ClipboardList },
  { id: 'pendientes',   label: 'Pendientes de revisión',     value: '3',  hint: 'mock', Icon: Wallet },
  { id: 'excels',       label: 'Excel generados',            value: '9',  hint: 'mock', Icon: FileSpreadsheet },
];

export function DashboardSection() {
  return (
    <div className="fact-screen">
      <div style={{ marginBottom: '1.25rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>
          Facturas Inteligentes
        </h1>
        <p style={{ marginTop: '0.25rem', color: 'var(--md-on-surface-variant)' }}>
          Vista general del módulo. Las métricas son referenciales por ahora.
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gap: '1rem',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          marginBottom: '1.5rem',
        }}
      >
        {STAT_CARDS.map(({ id, label, value, hint, Icon }) => (
          <div
            key={id}
            className="fact-card"
            style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', padding: '1rem' }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 44, height: 44,
                borderRadius: 12,
                background: 'var(--md-primary-container, #e8def8)',
                color: 'var(--md-on-primary-container, #21005d)',
                flexShrink: 0,
              }}
            >
              <Icon size={20} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--md-on-surface-variant)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {label}
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
                <span style={{ fontSize: '1.65rem', fontWeight: 600, lineHeight: 1.1 }}>{value}</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--md-on-surface-variant)' }}>({hint})</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          display: 'grid',
          gap: '1rem',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        }}
      >
        <Link
          to="/chat"
          className="fact-card"
          style={{
            textDecoration: 'none',
            color: 'inherit',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
            padding: '1.1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: 'var(--md-primary, #6750a4)' }}>
            <MessageSquare size={20} />
            <strong style={{ fontSize: '1rem' }}>Procesar desde el chat</strong>
          </div>
          <p style={{ margin: 0, color: 'var(--md-on-surface-variant)', fontSize: '0.9rem' }}>
            Adjuntá los PDFs en el chat de Yoko. Te guía con el flujo de carrito y, al
            terminar, te trae directo a Revisión de extracción.
          </p>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 'auto', color: 'var(--md-primary, #6750a4)', fontWeight: 500 }}>
            Abrir chat <ArrowRight size={16} />
          </span>
        </Link>

        <Link
          to="/modulos/facturas-inteligentes?section=revision"
          className="fact-card"
          style={{
            textDecoration: 'none',
            color: 'inherit',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
            padding: '1.1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: 'var(--md-primary, #6750a4)' }}>
            <ClipboardList size={20} />
            <strong style={{ fontSize: '1rem' }}>Revisión de extracción</strong>
          </div>
          <p style={{ margin: 0, color: 'var(--md-on-surface-variant)', fontSize: '0.9rem' }}>
            Subí archivos directamente desde la web o continuá un proceso ya
            extraído. Tabla editable de 13 columnas, auto-save, descarga del
            registro contable.
          </p>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 'auto', color: 'var(--md-primary, #6750a4)', fontWeight: 500 }}>
            Ir a revisión <ArrowRight size={16} />
          </span>
        </Link>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Sub-pantalla 2 · Revisión de extracción (flujo completo del legacy)
// ─────────────────────────────────────────────────────────────────────────

export function RevisionSection({ user }) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Modo "from-chat": el usuario llegó acá clickeando el botón "Abrir
  // revisión" del chat. Tiene un proceso_id en la URL → ya viene cargado,
  // no hay que mostrar upload ni stepper. Al confirmar, redirige al chat.
  const procesoIdFromUrl = searchParams.get('proceso_id');
  const cameFromChat = Boolean(procesoIdFromUrl);

  const [stage, setStage] = useState(
    cameFromChat ? STAGES.VALIDATING : STAGES.UPLOAD,
  );
  const [tipo, setTipo] = useState('compra');
  const [mes, setMes] = useState(currentMonthValue());
  const [files, setFiles] = useState([]);
  const [proceso, setProceso] = useState(null);
  const [facturas, setFacturas] = useState([]);
  const [errores, setErrores] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  // Correlativo inicial por sub_diario presente en el lote. Shape:
  //   { "11": 20, "13": 1, "15": 5 } (claves = códigos sub_diario CONCAR).
  // Se manda al backend al apretar "Conforme · descargar".
  const [correlativos, setCorrelativos] = useState({});

  // Recuperación desde localStorage (sesión anterior).
  const handleRecover = useCallback((procesoRestaurado, facturasRestauradas) => {
    setProceso(procesoRestaurado);
    setFacturas(facturasRestauradas);
    setStage(STAGES.VALIDATING);
  }, []);
  useRecuperarSesion(handleRecover);

  // Hidratación desde URL: cuando el chat redirige con ?proceso_id=proc-xxx,
  // cargamos ese proceso del backend (sin confirmación).
  const hydratedRef = useRef(false);
  useEffect(() => {
    if (hydratedRef.current) return;
    if (!procesoIdFromUrl) return;
    if (proceso?.proceso_id === procesoIdFromUrl) return;
    hydratedRef.current = true;

    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch(
          `/api/facturas?action=recuperar&proceso_id=${encodeURIComponent(procesoIdFromUrl)}`,
          { method: 'GET' },
        );
        if (cancelled) return;
        setProceso({
          proceso_id: procesoIdFromUrl,
          empresa_id: data.empresa_id || '',
          timestamp:  data.timestamp,
        });
        setFacturas(data.facturas || []);
        setErrores([]);
        setStage(STAGES.VALIDATING);
      } catch (e) {
        if (cancelled) return;
        console.error('[facturas/revision/hydrate]', e);
        setError(
          `No se pudo cargar el proceso ${procesoIdFromUrl}. ` +
          'Puede que haya expirado en el servidor.'
        );
      }
    })();

    return () => { cancelled = true; };
  }, [procesoIdFromUrl, proceso?.proceso_id]);

  const reset = () => {
    if (proceso?.proceso_id) {
      try { localStorage.removeItem(`facturas_${proceso.proceso_id}`); } catch { /* ignore */ }
    }
    setStage(STAGES.UPLOAD);
    setFiles([]);
    setProceso(null);
    setFacturas([]);
    setErrores([]);
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
      files.forEach((f) => formData.append('files', f, f.name));

      const data = await postFormAuth(API.FACTURAS_PROCESAR, formData);

      setProceso({
        proceso_id: data.proceso_id || `proc-${Date.now()}`,
        empresa_id: data.empresa_id || '',
        timestamp:  data.timestamp,
      });
      setFacturas(data.facturas || []);
      setErrores(data.errores || []);
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
      const token = getAuthToken();

      // Sanitizar correlativos: dropear strings vacíos y convertir a int.
      // El backend rechaza values < 1, así que evitamos 0 y NaN acá.
      const correlativosLimpios = {};
      for (const [sd, val] of Object.entries(correlativos || {})) {
        const num = parseInt(val, 10);
        if (Number.isFinite(num) && num >= 1) {
          correlativosLimpios[sd] = num;
        }
      }

      const res = await fetch(API.FACTURAS_CONCAR, {
        method: 'POST',
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          proceso_id:   proceso.proceso_id,
          dni:          user?.dni || '',
          correlativos: correlativosLimpios,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const filename = `REGISTRO_${proceso.proceso_id}.xlsx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      // Modo from-chat: cerrar la pantalla de revisión y volver al chat,
      // pasando `facturas_done=proc-xxx` para que useChat inserte un
      // mensaje de cierre del bot con el botón de re-descarga listo.
      if (cameFromChat) {
        navigate(`/chat?facturas_done=${encodeURIComponent(proceso.proceso_id)}`);
        return;
      }

      setStage(STAGES.DONE);
    } catch (e) {
      console.error('[facturas/concar]', e);
      setError('Hubo un problema al generar el archivo. Intenta de nuevo.');
      setStage(STAGES.VALIDATING);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fact-screen">
      {/* En modo from-chat el usuario no necesita ver el stepper completo
          (subir/validar/confirmar/generar): viene directo a revisar.
          En modo legacy (subió desde la web) sí mostramos el stepper. */}
      {!cameFromChat && <Stepper stage={stage} />}

      {error && <ErrorBanner message={error} />}

      {stage === STAGES.UPLOAD && !cameFromChat && (
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
          facturas={facturas}
          setFacturas={setFacturas}
          errores={errores}
          isLoading={isLoading}
          onConfirm={handleConfirmar}
          onReset={reset}
          compact={cameFromChat}
          correlativos={correlativos}
          setCorrelativos={setCorrelativos}
        />
      )}

      {stage === STAGES.CONFIRMING && (
        <LoadingCard
          title="Generando asientos contables..."
          subtitle="Esto puede tomar unos segundos"
        />
      )}

      {stage === STAGES.DONE && !cameFromChat && (
        <DoneCard
          proceso={proceso}
          onDownloadAgain={handleConfirmar}
          onReset={reset}
        />
      )}
    </div>
  );
}
