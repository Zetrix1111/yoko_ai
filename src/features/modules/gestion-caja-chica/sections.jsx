import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Plus, X, Check, XCircle, CreditCard, Search,
  TrendingUp, Wallet, Clock, ShieldCheck, ArrowUpRight,
  Upload as UploadIcon,
} from 'lucide-react';
import {
  STATS, SOLICITUDES, APROBACIONES, PAGOS, RENDICIONES,
  REPORTE_AREAS, REPORTE_USUARIOS, TIPOS_GASTO, CENTROS_COSTO,
  USUARIOS, ROLES, AREAS, formatPEN, formatDate,
} from './mockData';

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
  const [searchParams, setSearchParams] = useSearchParams();
  const autoOpen = searchParams.get('new') === '1';

  const [data, setData] = useState(SOLICITUDES);
  const [showModal, setShowModal] = useState(autoOpen);
  const [filter, setFilter] = useState('');

  // Si llegamos con ?new=1, limpiamos ese flag de la URL después de abrir
  // para que un refresh no vuelva a auto-abrir.
  if (autoOpen) {
    const next = new URLSearchParams(searchParams);
    next.delete('new');
    setSearchParams(next, { replace: true });
  }

  const filtered = data.filter((s) =>
    !filter || s.solicitante.toLowerCase().includes(filter.toLowerCase()) ||
    s.area.toLowerCase().includes(filter.toLowerCase())
  );

  const handleCreate = (e) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const nueva = {
      id: `SOL-${String(143 + data.length).padStart(4, '0')}`,
      solicitante: f.get('solicitante'),
      area: f.get('area'),
      monto: Number(f.get('monto')),
      tipo: f.get('tipo'),
      motivo: f.get('motivo'),
      fecha: f.get('fecha'),
      estado: 'pendiente',
    };
    setData([nueva, ...data]);
    setShowModal(false);
  };

  return (
    <>
      <SectionHeader
        title="Solicitudes"
        subtitle="Solicitudes de caja chica y entregas a rendir."
        action={
          <button className="gcc-btn gcc-btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={16} /> Nueva solicitud
          </button>
        }
      />

      <div className="gcc-table-wrap">
        <div className="gcc-table-toolbar">
          <h3>{filtered.length} solicitudes</h3>
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

        <table className="gcc-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Solicitante</th>
              <th>Área</th>
              <th>Tipo</th>
              <th className="num">Monto</th>
              <th>Estado</th>
              <th>Fecha</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan="7"><EmptyState message="Sin resultados" /></td></tr>
            ) : filtered.map((s) => (
              <tr key={s.id}>
                <td style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--md-on-surface-variant)' }}>{s.id}</td>
                <td style={{ fontWeight: 500 }}>{s.solicitante}</td>
                <td>{s.area}</td>
                <td>{s.tipo === 'caja-chica' ? 'Caja chica' : 'Entrega a rendir'}</td>
                <td className="num">{formatPEN(s.monto)}</td>
                <td><Badge value={s.estado} /></td>
                <td>{formatDate(s.fecha)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title="Nueva solicitud"
          onClose={() => setShowModal(false)}
        >
          <form onSubmit={handleCreate}>
            <div className="gcc-form-grid">
              <div className="gcc-field">
                <label htmlFor="solicitante">Solicitante</label>
                <input id="solicitante" name="solicitante" className="gcc-input" required />
              </div>
              <div className="gcc-field">
                <label htmlFor="area">Área</label>
                <select id="area" name="area" className="gcc-select" required defaultValue="">
                  <option value="" disabled>Seleccionar</option>
                  {AREAS.map((a) => <option key={a}>{a}</option>)}
                </select>
              </div>
              <div className="gcc-field">
                <label htmlFor="monto">Monto (S/)</label>
                <input id="monto" name="monto" type="number" min="0" step="0.01" className="gcc-input" required />
              </div>
              <div className="gcc-field">
                <label htmlFor="tipo">Tipo</label>
                <select id="tipo" name="tipo" className="gcc-select" required defaultValue="caja-chica">
                  <option value="caja-chica">Caja chica</option>
                  <option value="rendir">Entrega a rendir</option>
                </select>
              </div>
              <div className="gcc-field">
                <label htmlFor="fecha">Fecha</label>
                <input id="fecha" name="fecha" type="date" className="gcc-input" required defaultValue={new Date().toISOString().slice(0, 10)} />
              </div>
              <div className="gcc-field">
                <label htmlFor="adjunto">Adjuntar archivo</label>
                <input id="adjunto" name="adjunto" type="file" className="gcc-input" />
              </div>
              <div className="gcc-field full">
                <label htmlFor="motivo">Motivo</label>
                <textarea id="motivo" name="motivo" className="gcc-textarea" required />
              </div>
            </div>
            <div className="gcc-modal-actions">
              <button type="button" className="gcc-btn gcc-btn-ghost" onClick={() => setShowModal(false)}>Cancelar</button>
              <button type="submit" className="gcc-btn gcc-btn-primary">
                <Plus size={16} /> Crear solicitud
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

// ─────────────────────────────────────
// 2 · APROBACIONES
// ─────────────────────────────────────
export function AprobacionesSection() {
  const [data, setData] = useState(APROBACIONES);

  const decidir = (id, estado) => {
    setData(data.map((a) => a.id === id ? { ...a, estado } : a));
  };

  return (
    <>
      <SectionHeader
        title="Aprobaciones"
        subtitle="Revisa y autoriza las solicitudes pendientes."
      />

      <div className="gcc-table-wrap">
        <div className="gcc-table-toolbar">
          <h3>{data.filter((a) => a.estado === 'pendiente').length} pendientes</h3>
        </div>
        <table className="gcc-table">
          <thead>
            <tr>
              <th>Solicitud</th>
              <th>Solicitante</th>
              <th>Área</th>
              <th className="num">Monto</th>
              <th>Estado</th>
              <th style={{ width: 200 }}>Acción</th>
            </tr>
          </thead>
          <tbody>
            {data.map((a) => (
              <tr key={a.id}>
                <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{a.solicitudId}</td>
                <td style={{ fontWeight: 500 }}>{a.solicitante}</td>
                <td>{a.area}</td>
                <td className="num">{formatPEN(a.monto)}</td>
                <td><Badge value={a.estado} /></td>
                <td>
                  {a.estado === 'pendiente' ? (
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button className="gcc-btn gcc-btn-success" onClick={() => decidir(a.id, 'aprobada')}>
                        <Check size={14} /> Aprobar
                      </button>
                      <button className="gcc-btn gcc-btn-danger" onClick={() => decidir(a.id, 'rechazada')}>
                        <XCircle size={14} /> Rechazar
                      </button>
                    </div>
                  ) : (
                    <span style={{ fontSize: '0.8rem', color: 'var(--md-on-surface-variant)' }}>Decidido</span>
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
  const [data, setData] = useState(RENDICIONES);
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
                <td className="num" style={{ color: r.diferencia > 0 ? '#B91C1C' : 'inherit' }}>
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
                <label htmlFor="r-tipo">Tipo de gasto</label>
                <select id="r-tipo" className="gcc-select" required defaultValue="">
                  <option value="" disabled>Seleccionar</option>
                  {TIPOS_GASTO.map((t) => <option key={t.id}>{t.nombre}</option>)}
                </select>
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
// 6 · CONFIGURACIÓN
// ─────────────────────────────────────
export function ConfiguracionSection() {
  return (
    <>
      <SectionHeader
        title="Configuración"
        subtitle="Tipos de gasto, centros de costo, usuarios y roles."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1rem' }}>
        <div className="gcc-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>Tipos de gasto</h3>
            <button className="gcc-btn gcc-btn-link"><Plus size={14} /> Agregar</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {TIPOS_GASTO.map((t) => (
              <div key={t.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '0.5rem 0.75rem', background: 'var(--md-surface-variant)',
                borderRadius: 8, fontSize: '0.85rem',
              }}>
                <span>{t.nombre}</span>
                <Badge value={t.activo ? 'aprobada' : 'rechazada'} />
              </div>
            ))}
          </div>
        </div>

        <div className="gcc-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>Centros de costo</h3>
            <button className="gcc-btn gcc-btn-link"><Plus size={14} /> Agregar</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {CENTROS_COSTO.map((c) => (
              <div key={c.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '0.5rem 0.75rem', background: 'var(--md-surface-variant)',
                borderRadius: 8, fontSize: '0.85rem',
              }}>
                <div>
                  <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--md-on-surface-variant)' }}>{c.id}</span>
                  {' · '}
                  <span>{c.nombre}</span>
                </div>
                <Badge value={c.activo ? 'aprobada' : 'rechazada'} />
              </div>
            ))}
          </div>
        </div>

        <div className="gcc-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>Usuarios</h3>
            <button className="gcc-btn gcc-btn-link"><Plus size={14} /> Agregar</button>
          </div>
          <table className="gcc-table" style={{ borderTop: '1px solid var(--md-outline-variant)' }}>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Rol</th>
                <th>Área</th>
              </tr>
            </thead>
            <tbody>
              {USUARIOS.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 500 }}>{u.nombre}</td>
                  <td>{u.rol}</td>
                  <td>{u.area}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="gcc-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>Roles</h3>
            <button className="gcc-btn gcc-btn-link"><Plus size={14} /> Agregar</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {ROLES.map((r) => (
              <div key={r.id} style={{ padding: '0.6rem 0.75rem', background: 'var(--md-surface-variant)', borderRadius: 8 }}>
                <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{r.nombre}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--md-on-surface-variant)', marginTop: 2 }}>{r.permisos}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
