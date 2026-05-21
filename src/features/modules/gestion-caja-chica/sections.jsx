import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Plus, X, Check, XCircle, CreditCard, Search,
  TrendingUp, Wallet, Clock, ShieldCheck, ArrowUpRight,
  Upload as UploadIcon, AlertCircle, CheckCircle2, Loader2,
} from 'lucide-react';
import {
  STATS, SOLICITUDES, PAGOS, RENDICIONES,
  REPORTE_AREAS, REPORTE_USUARIOS,
  AREAS, formatPEN, formatDate,
} from './mockData';
import { useEmpresaConfig } from '../../../shared/useEmpresaConfig';
import Toggle from '../../../shared/components/Toggle';
import useSolicitudes from './hooks/useSolicitudes';
import SolicitudDetalle from './components/SolicitudDetalle';

// ─────────────────────────────────────
// Helpers UI
// ─────────────────────────────────────

function Badge({ value }) {
  return <span className={`gcc-badge ${value}`}>{value}</span>;
}

function SectionHeader({ title, subtitle, action }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
      <div>
        <h1 className="gcc-section-title">{title}</h1>
        {subtitle && <p className="gcc-section-subtitle">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

function Modal({ title, onClose, children, footer }) {
  return (
    <div className="gcc-modal-overlay" onClick={onClose}>
      <div className="gcc-modal" onClick={(e) => e.stopPropagation()}>
        <div className="gcc-modal-header">
          <h2 className="gcc-modal-title">{title}</h2>
          <button className="gcc-modal-close" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>
        {children}
        {footer && <div className="gcc-modal-actions">{footer}</div>}
      </div>
    </div>
  );
}

function EmptyState({ message }) {
  return <div className="gcc-table-empty">{message}</div>;
}

// ─────────────────────────────────────
// 0 · INICIO (welcome dashboard)
// ─────────────────────────────────────

const STAT_CARDS = [
  {
    key: 'solicitado',
    label: 'Total solicitado',
    Icon: TrendingUp,
    variant: 'neutral',
    trend: '+12% vs mes anterior',
    trendVariant: 'success',
  },
  {
    key: 'aprobado',
    label: 'Total aprobado',
    Icon: ShieldCheck,
    variant: 'success',
    trend: '74% de las solicitudes',
    trendVariant: 'success',
  },
  {
    key: 'pagado',
    label: 'Total pagado',
    Icon: Wallet,
    variant: 'info',
    trend: 'S/ 3,500 desembolsado hoy',
    trendVariant: '',
  },
  {
    key: 'pendiente',
    label: 'Pendiente de rendir',
    Icon: Clock,
    variant: 'warning',
    trend: '4 usuarios con rendiciones abiertas',
    trendVariant: 'warning',
  },
];

// Mapea estado de solicitud → ícono + color del activity row
function activityIconFor(estado) {
  switch (estado) {
    case 'aprobada': return { Icon: ShieldCheck, variant: 'success' };
    case 'pagada':   return { Icon: CreditCard,  variant: 'info'    };
    case 'rechazada':return { Icon: XCircle,     variant: 'error'   };
    case 'pendiente':
    default:         return { Icon: Clock,       variant: 'warning' };
  }
}

export function InicioSection() {
  const [, setSearchParams] = useSearchParams();

  const statValueByKey = {
    solicitado: STATS.totalSolicitado,
    aprobado:   STATS.totalAprobado,
    pagado:     STATS.totalPagado,
    pendiente:  STATS.pendienteRendir,
  };

  const goToSolicitudes = (params = {}) => {
    setSearchParams({ section: 'solicitudes', ...params });
  };

  return (
    <>
      <SectionHeader
        title="Dashboard"
        subtitle="Control total del dinero de tu empresa, sin Excel ni desorden."
        action={
          <button className="gcc-btn gcc-btn-primary" onClick={() => goToSolicitudes({ new: '1' })}>
            <Plus size={16} /> Nueva Solicitud
          </button>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '1rem' }}>
        {STAT_CARDS.map(({ key, label, Icon, variant, trend, trendVariant }) => (
          <div key={key} className="gcc-card gcc-stat-card">
            <div className="gcc-stat-top">
              <span className="gcc-stat-label">{label}</span>
              <div className={`gcc-stat-icon-wrap ${variant}`}>
                <Icon size={18} />
              </div>
            </div>
            <div className="gcc-stat-value">{formatPEN(statValueByKey[key])}</div>
            <div className={`gcc-stat-trend ${trendVariant || ''}`}>
              {trendVariant === 'success' && <ArrowUpRight size={12} />}
              {trend}
            </div>
          </div>
        ))}
      </div>

      <div className="gcc-card">
        <div className="gcc-card-header">
          <h3 className="gcc-card-title">Actividad reciente</h3>
          <button className="gcc-link" onClick={() => goToSolicitudes()}>
            Ver todo →
          </button>
        </div>

        <div className="gcc-activity">
          {SOLICITUDES.slice(0, 5).map((s) => {
            const { Icon, variant } = activityIconFor(s.estado);
            return (
              <button
                key={s.id}
                type="button"
                className="gcc-activity-row"
                onClick={() => goToSolicitudes()}
              >
                <div className={`gcc-activity-icon ${variant}`}>
                  <Icon size={16} />
                </div>
                <div className="gcc-activity-text">
                  <div className="gcc-activity-title">
                    {s.solicitante} — {s.motivo}
                  </div>
                  <div className="gcc-activity-meta">
                    {s.area} · {formatDate(s.fecha)} · {s.tipo === 'caja-chica' ? 'Caja chica' : 'Entrega a rendir'}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', flexShrink: 0 }}>
                  <span className="gcc-activity-amount">{formatPEN(s.monto)}</span>
                  <Badge value={s.estado} />
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 1 · SOLICITUDES
// ─────────────────────────────────────
export function SolicitudesSection() {
  const { solicitudes, loading, error, refetch } = useSolicitudes();
  const [filter, setFilter] = useState('');
  const [selectedId, setSelectedId] = useState(null);

  const filtered = solicitudes.filter((s) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      (s.nombre || '').toLowerCase().includes(q) ||
      (s.motivo || '').toLowerCase().includes(q) ||
      (s.numero || '').toLowerCase().includes(q) ||
      (s.tipo || '').toLowerCase().includes(q)
    );
  });

  const handleCloseDetalle = () => {
    setSelectedId(null);
    // Refrescar el listado por si cambió TOTAL_GENERAL o items_count.
    refetch();
  };

  return (
    <>
      <SectionHeader
        title="Solicitudes"
        subtitle="Solicitudes de caja chica. Para crear una nueva, usá el chat con Yoko."
      />

      <div className="gcc-table-wrap">
        <div className="gcc-table-toolbar">
          <h3>
            {loading ? 'Cargando…' : `${filtered.length} solicitud${filtered.length === 1 ? '' : 'es'}`}
          </h3>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--md-on-surface-variant)' }} />
            <input
              className="gcc-input"
              style={{ paddingLeft: 32, fontSize: '0.85rem', padding: '0.45rem 0.75rem 0.45rem 2rem' }}
              placeholder="Buscar..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
        </div>

        {error && (
          <div style={{ padding: '1rem', color: 'var(--md-on-error-container)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
            <button className="gcc-btn gcc-btn-ghost" onClick={refetch}>Reintentar</button>
          </div>
        )}

        <table className="gcc-table">
          <thead>
            <tr>
              <th>Número</th>
              <th>Solicitante</th>
              <th>Tipo</th>
              <th>Motivo</th>
              <th className="num">Total</th>
              <th>Estado</th>
              <th className="num">Ítems</th>
            </tr>
          </thead>
          <tbody>
            {!loading && filtered.length === 0 ? (
              <tr><td colSpan="7"><EmptyState message={solicitudes.length === 0 ? 'Todavía no tenés solicitudes. Creá una desde el chat con Yoko.' : 'Sin resultados'} /></td></tr>
            ) : filtered.map((s) => (
              <tr
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                style={{ cursor: 'pointer' }}
              >
                <td style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--md-on-surface-variant)' }}>{s.numero || s.id}</td>
                <td style={{ fontWeight: 500 }}>{s.nombre || '—'}</td>
                <td>{s.tipo || '—'}</td>
                <td style={{ maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.motivo || '—'}
                </td>
                <td className="num">{s.moneda === 'PEN' || !s.moneda ? formatPEN(s.total_general) : `${s.moneda} ${(Number(s.total_general) || 0).toFixed(2)}`}</td>
                <td><Badge value={s.estado} /></td>
                <td className="num">{s.items_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <SolicitudDetalle solicitudId={selectedId} onClose={handleCloseDetalle} />
      )}
    </>
  );
}

// ─────────────────────────────────────
// 2 · APROBACIONES — externalizado
// ─────────────────────────────────────
// Las aprobaciones viven en https://aprobaciones.luna.com.pe/
// El submenú abre ese sistema en nueva pestaña. Esta pantalla solo
// se renderiza si alguien llega por deep-link a ?section=aprobaciones.
export function AprobacionesSection() {
  return (
    <div className="gcc-card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
      <p style={{ color: '#475569', marginBottom: '1rem' }}>
        Las aprobaciones se gestionan en un sistema externo.
      </p>
      <a
        className="gcc-btn gcc-btn-primary"
        href="https://aprobaciones.luna.com.pe/"
        target="_blank"
        rel="noopener noreferrer"
      >
        Abrir Aprobaciones ↗
      </a>
    </div>
  );
}

// ─────────────────────────────────────
// 3 · PAGOS
// ─────────────────────────────────────
export function PagosSection() {
  const [data, setData] = useState(PAGOS);

  const marcarPagado = (id) => {
    setData(data.map((p) => p.id === id ? { ...p, estado: 'pagado' } : p));
  };

  const medioLabel = (m) => ({
    'efectivo': 'Efectivo',
    'transferencia': 'Transferencia',
    'yape': 'Yape',
    'plin': 'Plin',
  }[m] || m);

  return (
    <>
      <SectionHeader
        title="Pagos"
        subtitle="Solicitudes aprobadas listas para desembolso."
      />

      <div className="gcc-table-wrap">
        <div className="gcc-table-toolbar">
          <h3>{data.filter((p) => p.estado === 'pendiente').length} por pagar</h3>
        </div>
        <table className="gcc-table">
          <thead>
            <tr>
              <th>Solicitud</th>
              <th className="num">Monto</th>
              <th>Medio</th>
              <th>Cuenta</th>
              <th>Estado</th>
              <th style={{ width: 180 }}>Acción</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.id}>
                <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{p.solicitudId}</td>
                <td className="num">{formatPEN(p.monto)}</td>
                <td>{medioLabel(p.medio)}</td>
                <td style={{ fontSize: '0.82rem' }}>{p.cuenta}</td>
                <td><Badge value={p.estado} /></td>
                <td>
                  {p.estado === 'pendiente' ? (
                    <button className="gcc-btn gcc-btn-primary" onClick={() => marcarPagado(p.id)}>
                      <CreditCard size={14} /> Marcar como pagado
                    </button>
                  ) : (
                    <span style={{ fontSize: '0.8rem', color: 'var(--md-on-surface-variant)' }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 4 · RENDICIONES
// ─────────────────────────────────────
export function RendicionesSection() {
  const [data] = useState(RENDICIONES);
  const [showModal, setShowModal] = useState(false);

  const submitRendicion = (e) => {
    e.preventDefault();
    setShowModal(false);
    // En real: append a la lista — aquí solo cierra el modal
  };

  return (
    <>
      <SectionHeader
        title="Rendiciones"
        subtitle="Comprobantes y diferencias de los fondos entregados."
        action={
          <button className="gcc-btn gcc-btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={16} /> Registrar rendición
          </button>
        }
      />

      <div className="gcc-table-wrap">
        <div className="gcc-table-toolbar">
          <h3>{data.length} rendiciones</h3>
        </div>
        <table className="gcc-table">
          <thead>
            <tr>
              <th>Usuario</th>
              <th className="num">Entregado</th>
              <th className="num">Rendido</th>
              <th className="num">Diferencia</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id}>
                <td style={{ fontWeight: 500 }}>{r.usuario}</td>
                <td className="num">{formatPEN(r.entregado)}</td>
                <td className="num">{formatPEN(r.rendido)}</td>
                <td className="num" style={{ color: r.diferencia > 0 ? 'var(--md-error)' : 'inherit' }}>
                  {formatPEN(r.diferencia)}
                </td>
                <td><Badge value={r.estado} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal title="Registrar rendición" onClose={() => setShowModal(false)}>
          <form onSubmit={submitRendicion}>
            <div className="gcc-form-grid">
              <div className="gcc-field">
                <label htmlFor="r-fecha">Fecha</label>
                <input id="r-fecha" type="date" className="gcc-input" required defaultValue={new Date().toISOString().slice(0, 10)} />
              </div>
              <div className="gcc-field">
                <label htmlFor="r-prov">Proveedor</label>
                <input id="r-prov" className="gcc-input" placeholder="Razón social / RUC" required />
              </div>
              <div className="gcc-field">
                <label htmlFor="r-monto">Monto (S/)</label>
                <input id="r-monto" type="number" min="0" step="0.01" className="gcc-input" required />
              </div>
              <div className="gcc-field full">
                <label htmlFor="r-comp">Subir comprobante</label>
                <input id="r-comp" type="file" accept="application/pdf,image/*" className="gcc-input" required />
              </div>
            </div>
            <div className="gcc-modal-actions">
              <button type="button" className="gcc-btn gcc-btn-ghost" onClick={() => setShowModal(false)}>Cancelar</button>
              <button type="submit" className="gcc-btn gcc-btn-primary">
                <UploadIcon size={16} /> Registrar
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

// ─────────────────────────────────────
// 5 · REPORTES
// ─────────────────────────────────────
export function ReportesSection() {
  const maxArea = Math.max(...REPORTE_AREAS.map((r) => r.monto));
  const maxUser = Math.max(...REPORTE_USUARIOS.map((r) => r.monto));

  return (
    <>
      <SectionHeader
        title="Reportes"
        subtitle="Visión general del consumo de fondos."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1rem' }}>
        <div className="gcc-card">
          <h3 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 600 }}>Gastos por área</h3>
          {REPORTE_AREAS.map((row) => (
            <div key={row.area} className="gcc-bar-row">
              <span className="gcc-bar-label">{row.area}</span>
              <div className="gcc-bar-track">
                <div className="gcc-bar-fill" style={{ width: `${(row.monto / maxArea) * 100}%` }} />
              </div>
              <span className="gcc-bar-value">{formatPEN(row.monto)}</span>
            </div>
          ))}
        </div>

        <div className="gcc-card">
          <h3 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 600 }}>Gastos por usuario</h3>
          {REPORTE_USUARIOS.map((row) => (
            <div key={row.usuario} className="gcc-bar-row alt">
              <span className="gcc-bar-label">{row.usuario}</span>
              <div className="gcc-bar-track">
                <div className="gcc-bar-fill" style={{ width: `${(row.monto / maxUser) * 100}%` }} />
              </div>
              <span className="gcc-bar-value">{formatPEN(row.monto)}</span>
            </div>
          ))}
        </div>

        <div className="gcc-card">
          <h3 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 600 }}>Pendientes de rendir</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
            <div className="gcc-donut" />
            <div className="gcc-donut-legend">
              <div className="gcc-donut-legend-item">
                <span className="dot" style={{ background: 'var(--md-primary)' }} />
                Vencidas (35%)
              </div>
              <div className="gcc-donut-legend-item">
                <span className="dot" style={{ background: '#FFA000' }} />
                Por vencer (25%)
              </div>
              <div className="gcc-donut-legend-item">
                <span className="dot" style={{ background: '#2B7CD3' }} />
                A tiempo (25%)
              </div>
              <div className="gcc-donut-legend-item">
                <span className="dot" style={{ background: 'var(--md-outline-variant)' }} />
                Sin movimiento (15%)
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// Helpers: Toggle + ConfigCard
// ─────────────────────────────────────

function ConfigCard({ title, titleBadge, description, summary, enabled, onToggle, children }) {
  return (
    <div className={`gcc-card gcc-config-card ${enabled ? 'is-on' : ''}`}>
      <div className="gcc-config-header">
        <div className="gcc-config-title-block">
          <h3 className="gcc-card-title">
            {title}
            {titleBadge && <span className="gcc-title-badge">{titleBadge}</span>}
          </h3>
          {description && <p className="gcc-config-description">{description}</p>}
        </div>
        <div className="gcc-config-controls">
          {summary && <span className="gcc-config-summary">{summary}</span>}
          <Toggle classPrefix="gcc" checked={enabled} onChange={onToggle} ariaLabel={typeof title === 'string' ? title : ''} />
        </div>
      </div>
      {enabled && children && <div className="gcc-config-body">{children}</div>}
    </div>
  );
}

// ─────────────────────────────────────
// 6 · CONFIGURACIÓN
// ─────────────────────────────────────
export function ConfiguracionSection() {
  // Estado inicial leído desde Airtable (Config_Empresa.data.proceso.caja_chica).
  // Esta pantalla no edita basicos ni info_extendida, pero al guardar los preserva.
  const { data, loading, saving, save } = useEmpresaConfig('empresa');

  const [aprobadoresEnabled,  setAprobadoresEnabled]  = useState(true);
  const [aprobadores,         setAprobadores]         = useState(2);
  const [maxMontoEnabled,     setMaxMontoEnabled]     = useState(false);
  const [maxMonto,            setMaxMonto]            = useState(0);
  const [aprobRendicionEnabled, setAprobRendicionEnabled] = useState(false);
  const [seguimientoIA,       setSeguimientoIA]       = useState(false);

  const [savedHint, setSavedHint] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Hidratar el form cuando llegan los datos de Airtable.
  useEffect(() => {
    if (!data) return;
    const cc = data.proceso?.caja_chica || {};
    setAprobadoresEnabled(cc.requiere_aprobacion ?? true);
    setAprobadores(cc.num_aprobadores ?? 2);
    setMaxMontoEnabled(cc.monto_maximo_activo ?? false);
    setMaxMonto(cc.monto_maximo ?? 0);
    setAprobRendicionEnabled(cc.aprobacion_rendicion ?? false);
    setSeguimientoIA(cc.seguimiento_ia ?? false);
  }, [data]);

  // Guardar SOLO el bloque proceso. basicos e info_extendida se preservan
  // intactos para no pisar lo que escribió Configuración Empresa.
  const handleSave = async () => {
    setSaveError(null);
    const payload = {
      basicos:        data?.basicos || {},
      info_extendida: data?.info_extendida || {},
      proceso: {
        ...(data?.proceso || {}),
        caja_chica: {
          requiere_aprobacion:  aprobadoresEnabled,
          num_aprobadores:      aprobadores,
          monto_maximo_activo:  maxMontoEnabled,
          monto_maximo:         maxMonto,
          aprobacion_rendicion: aprobRendicionEnabled,
          seguimiento_ia:       seguimientoIA,
        },
      },
    };
    const ok = await save(payload);
    if (ok) {
      setSavedHint(true);
      setTimeout(() => setSavedHint(false), 2500);
    } else {
      setSaveError('No se pudo guardar. Intentá de nuevo.');
    }
  };

  return (
    <>
      <SectionHeader
        title="Configuración"
        subtitle="Activa o desactiva las reglas de negocio que aplican a los procesos."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <ConfigCard
          title="Número de aprobadores"
          description="Cantidad de aprobadores que debe pasar cada solicitud antes de ser autorizada. Si está desactivado, las solicitudes pasan directo a Pagos."
          summary={
            aprobadoresEnabled
              ? `${aprobadores} ${aprobadores === 1 ? 'aprobador' : 'aprobadores'}`
              : 'Sin aprobaciones'
          }
          enabled={aprobadoresEnabled}
          onToggle={setAprobadoresEnabled}
        >
          <div className="gcc-number-input">
            <input
              type="number"
              min="1"
              max="10"
              value={aprobadores}
              onChange={(e) => setAprobadores(Math.max(1, Number(e.target.value) || 1))}
            />
            <span>aprobadores en cadena</span>
          </div>
        </ConfigCard>

        <ConfigCard
          title="Monto máximo por solicitud"
          description="Si está activo, ninguna solicitud puede exceder el monto configurado. Si está desactivado, no hay límite."
          summary={maxMontoEnabled ? formatPEN(maxMonto) : 'Sin límite'}
          enabled={maxMontoEnabled}
          onToggle={setMaxMontoEnabled}
        >
          <div className="gcc-number-input">
            <span>S/</span>
            <input
              type="number"
              min="0"
              step="50"
              value={maxMonto}
              className="wide"
              onChange={(e) => setMaxMonto(Math.max(0, Number(e.target.value) || 0))}
            />
          </div>
        </ConfigCard>

        <ConfigCard
          title="Aprobación de rendición"
          description="Si está activo, las rendiciones deben pasar por aprobación antes de quedar registradas como válidas. Si está desactivado, se aceptan automáticamente al ser registradas."
          summary={aprobRendicionEnabled ? 'Requiere aprobación' : 'Sin aprobación'}
          enabled={aprobRendicionEnabled}
          onToggle={setAprobRendicionEnabled}
        />

        <ConfigCard
          title="Seguimiento con IA"
          titleBadge="Consume tokens"
          description="Análisis automático de solicitudes y rendiciones con IA: detecta inconsistencias, recordatorios y sugerencias contables. El consumo de tokens se factura según el uso."
          summary={seguimientoIA ? 'Activo' : 'Desactivado'}
          enabled={seguimientoIA}
          onToggle={setSeguimientoIA}
        />

        <div className="gcc-config-actions">
          <button
            type="button"
            className="gcc-btn-primary"
            onClick={handleSave}
            disabled={saving || loading}
          >
            {saving ? (
              <><Loader2 size={14} className="ce-spin" /> Guardando...</>
            ) : (
              <>Guardar configuración</>
            )}
          </button>
          {savedHint && (
            <span className="gcc-saved-hint">
              <CheckCircle2 size={14} /> Guardado
            </span>
          )}
          {saveError && (
            <span className="gcc-save-error">
              <AlertCircle size={14} /> {saveError}
            </span>
          )}
        </div>
      </div>
    </>
  );
}
