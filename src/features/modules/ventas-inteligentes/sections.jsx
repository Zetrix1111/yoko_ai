import { useState, useEffect, useRef, Component } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Plus, X, Sparkles, Users, MessageCircle, ShoppingBag, ArrowUpRight,
  Pencil, Trash2, Check, TrendingUp, Activity, Search, Package,
  Upload as UploadIcon, Image as ImageIcon, Loader2, AlertCircle,
  Power, PowerOff, Send, Trash, Bot, User as UserIcon,
} from 'lucide-react';
// qrcode.react: named exports estables, sin problemas de interop CJS/ESM.
import { QRCodeSVG } from 'qrcode.react';
import {
  STATS, FUNNEL, ACTIVIDAD, CANALES, CLIENTES,
  CANAL_LABELS, ESTADO_LABELS, STOCK_LABELS, getStockStatus,
  formatPEN, formatNum, formatDate,
} from './mockData';
import { API, getJsonAuth, postJsonAuth, patchJsonAuth, deleteJsonAuth } from '../../../shared/api';
import { useEmpresaConfig } from '../../../shared/useEmpresaConfig';

// ─────────────────────────────────────
// Helpers UI
// ─────────────────────────────────────

function SectionHeader({ title, subtitle, action }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
      <div>
        <h1 className="vom-section-title">{title}</h1>
        {subtitle && <p className="vom-section-subtitle">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

function Badge({ value, label }) {
  return <span className={`vom-badge ${value}`}>{label || ESTADO_LABELS[value] || value}</span>;
}

function ChannelBadge({ value }) {
  return <span className="vom-channel-badge">{CANAL_LABELS[value] || value}</span>;
}

export function Toggle({ checked, onChange, ariaLabel }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      className={`vom-toggle ${checked ? 'on' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span className="vom-toggle-thumb" />
    </button>
  );
}

// Error Boundary local — captura crashes en sub-secciones para no dejar
// la página en blanco. Muestra el mensaje del error para diagnóstico.
export class SectionErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error('[SectionErrorBoundary] Crash:', error, info);
  }
  render() {
    if (this.state.hasError) {
      const err = this.state.error;
      const msg = err?.message || String(err);
      const stack = err?.stack || '';
      return (
        <div className="vom-card" style={{ padding: '1.5rem', borderColor: 'var(--md-error)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--md-error)', marginBottom: '0.5rem' }}>
            <AlertCircle size={18} />
            <strong>Error en esta sección</strong>
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface)', marginBottom: '0.5rem' }}>
            {msg}
          </div>
          <pre style={{ fontSize: '0.7rem', color: 'var(--md-on-surface-variant)', whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto', background: 'var(--md-surface-variant)', padding: '0.5rem', borderRadius: 6 }}>
            {stack}
          </pre>
          <button
            className="vom-btn vom-btn-ghost"
            style={{ marginTop: '0.75rem' }}
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Reintentar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function Modal({ title, onClose, children }) {
  return (
    <div className="vom-modal-overlay" onClick={onClose}>
      <div className="vom-modal" onClick={(e) => e.stopPropagation()}>
        <div className="vom-modal-header">
          <h2 className="vom-modal-title">{title}</h2>
          <button className="vom-modal-close" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function activityIconFor(estado) {
  switch (estado) {
    case 'cerrado':     return { Icon: Check, variant: 'cerrado' };
    case 'negociacion': return { Icon: TrendingUp, variant: 'negociacion' };
    case 'interesado':  return { Icon: Sparkles, variant: 'interesado' };
    case 'nuevo':       return { Icon: MessageCircle, variant: 'nuevo' };
    default:            return { Icon: Activity, variant: 'frio' };
  }
}

// ─────────────────────────────────────
// 1 · DASHBOARD
// ─────────────────────────────────────

const STAT_CARDS = [
  { key: 'totalLeads',           label: 'Total leads',          Icon: Users,         variant: 'primary',  trend: '+18% vs mes anterior',  trendVariant: 'success', format: 'num' },
  { key: 'conversacionesActivas',label: 'Conversaciones activas', Icon: MessageCircle,variant: 'tertiary', trend: '45 en tiempo real',    trendVariant: '',        format: 'num' },
  { key: 'ventasCerradas',       label: 'Ventas cerradas',      Icon: ShoppingBag,   variant: 'success',  trend: 'S/ 5,200 hoy',          trendVariant: 'success', format: 'pen' },
  { key: 'clientesCalientes',    label: 'Clientes calientes',   Icon: Sparkles,      variant: 'warning',  trend: 'Listos para comprar',    trendVariant: 'warning', format: 'num' },
];

function MiniFunnel({ stages }) {
  const max = Math.max(...stages.map((s) => s.count));
  return (
    <div className="vom-funnel">
      {stages.map((s, idx) => {
        const pct = max > 0 ? Math.round((s.count / max) * 100) : 0;
        const conversion = idx === 0 ? null : Math.round((s.count / stages[idx - 1].count) * 100);
        return (
          <div key={s.id} className="vom-funnel-row">
            <div className="vom-funnel-label">
              <span className={`vom-funnel-dot ${s.variant}`} />
              {s.label}
            </div>
            <div className="vom-funnel-track">
              <div className={`vom-funnel-fill ${s.variant}`} style={{ width: `${pct}%` }} />
            </div>
            <div className="vom-funnel-meta">
              <span className="vom-funnel-count">{formatNum(s.count)}</span>
              {conversion !== null && <span className="vom-funnel-conv">{conversion}% conv.</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function InicioSection() {
  const [, setSearchParams] = useSearchParams();
  const [iaActiva, setIaActiva] = useState(true);

  const goTo = (section, params = {}) => setSearchParams({ section, ...params });

  return (
    <>
      <SectionHeader
        title="Dashboard"
        subtitle="Controla y aumenta tus ventas desde todos tus canales en un solo lugar."
        action={
          <button className="vom-btn vom-btn-primary" onClick={() => goTo('clientes', { new: '1' })}>
            <Plus size={16} /> Nuevo lead
          </button>
        }
      />

      {/* Bloque destacado: IA de ventas activa */}
      <div className={`vom-cta-banner ${iaActiva ? 'is-active' : ''}`}>
        <div className="vom-cta-icon">
          <Sparkles size={22} />
        </div>
        <div className="vom-cta-text">
          <h3>{iaActiva ? 'IA de ventas activa' : 'IA de ventas pausada'}</h3>
          <p>
            {iaActiva
              ? 'Tu IA está respondiendo automáticamente y generando oportunidades de venta.'
              : 'Activa la IA y deja que responda, califique leads y cierre ventas mientras trabajas en lo importante.'}
          </p>
        </div>
        <button
          className={`vom-btn ${iaActiva ? 'vom-btn-ghost' : 'vom-btn-primary'}`}
          onClick={() => setIaActiva((v) => !v)}
        >
          {iaActiva ? 'Desactivar' : (<><Sparkles size={16} /> Activar IA</>)}
        </button>
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '1rem' }}>
        {STAT_CARDS.map(({ key, label, Icon, variant, trend, trendVariant, format }) => {
          const raw = STATS[key];
          const value = format === 'pen' ? formatPEN(raw) : formatNum(raw);
          return (
            <div key={key} className="vom-card vom-stat-card">
              <div className="vom-stat-top">
                <span className="vom-stat-label">{label}</span>
                <div className={`vom-stat-icon-wrap ${variant}`}>
                  <Icon size={18} />
                </div>
              </div>
              <div className="vom-stat-value">{value}</div>
              <div className={`vom-stat-trend ${trendVariant || ''}`}>
                {trendVariant === 'success' && <ArrowUpRight size={12} />}
                {trend}
              </div>
            </div>
          );
        })}
      </div>

      {/* Mini embudo + Actividad reciente */}
      <div className="vom-dashboard-row">
        <div className="vom-card">
          <div className="vom-card-header">
            <h3 className="vom-card-title">Embudo de ventas</h3>
            <span style={{ fontSize: '0.78rem', color: 'var(--md-on-surface-variant)' }}>Mes actual</span>
          </div>
          <MiniFunnel stages={FUNNEL} />
        </div>

        <div className="vom-card">
          <div className="vom-card-header">
            <h3 className="vom-card-title">Actividad reciente</h3>
            <button className="vom-link" onClick={() => goTo('clientes')}>Ver todo →</button>
          </div>
          <div className="vom-activity">
            {ACTIVIDAD.slice(0, 5).map((a) => {
              const { Icon, variant } = activityIconFor(a.estado);
              return (
                <button key={a.id} type="button" className="vom-activity-row" onClick={() => goTo('clientes')}>
                  <div className={`vom-activity-icon ${variant}`}>
                    <Icon size={16} />
                  </div>
                  <div className="vom-activity-text">
                    <div className="vom-activity-title">{a.cliente}</div>
                    <div className="vom-activity-meta">{a.asunto} · {CANAL_LABELS[a.canal]}</div>
                  </div>
                  <Badge value={a.estado} />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 2 · CLIENTES
// ─────────────────────────────────────

export function ClientesSection() {
  const [clientes] = useState(CLIENTES);
  const [filter, setFilter] = useState('');

  const filtered = clientes.filter((c) =>
    !filter || c.nombre.toLowerCase().includes(filter.toLowerCase()) ||
    (c.ultimoMensaje || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <>
      <SectionHeader
        title="Clientes"
        subtitle="Todos los contactos capturados en cualquier canal, con su estado actual."
        action={
          <button className="vom-btn vom-btn-primary">
            <Plus size={16} /> Nuevo lead
          </button>
        }
      />

      <div className="vom-table-wrap">
        <div className="vom-table-toolbar">
          <h3>{filtered.length} clientes</h3>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--md-on-surface-variant)' }} />
            <input
              type="text"
              placeholder="Buscar..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              style={{
                paddingLeft: 32, fontSize: '0.85rem', padding: '0.45rem 0.75rem 0.45rem 2rem',
                border: '1.5px solid var(--md-outline-variant)', borderRadius: 10,
                background: 'var(--md-surface)', outline: 'none', minWidth: 220,
              }}
            />
          </div>
        </div>
        <table className="vom-table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Canal</th>
              <th>Estado</th>
              <th>Último mensaje</th>
              <th>Fecha</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan="5"><div className="vom-table-empty">Sin resultados</div></td></tr>
            ) : filtered.map((c) => (
              <tr key={c.id}>
                <td style={{ fontWeight: 500 }}>{c.nombre}</td>
                <td><ChannelBadge value={c.canal} /></td>
                <td><Badge value={c.estado} /></td>
                <td className="vom-msg-cell">{c.ultimoMensaje}</td>
                <td style={{ color: 'var(--md-on-surface-variant)', fontSize: '0.82rem' }}>
                  {formatDate(c.fecha)}
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
// 3 · PRODUCTOS
// ─────────────────────────────────────

function ProductoCard({ producto, onEdit, onDelete }) {
  const status = getStockStatus(producto);
  return (
    <div className="vom-product-card">
      <div className="vom-product-photo">
        {producto.foto ? (
          <img src={producto.foto} alt={producto.nombre} />
        ) : (
          <div className="vom-product-photo-placeholder">
            <Package size={28} />
          </div>
        )}
        <span className={`vom-stock-badge ${status} vom-stock-badge--floating`}>
          {STOCK_LABELS[status]}
        </span>
      </div>
      <div className="vom-product-body">
        <div className="vom-product-name">{producto.nombre}</div>
        <div className="vom-product-desc">{producto.descripcion}</div>
        <div className="vom-product-row">
          <div>
            <div className="vom-product-price">{formatPEN(producto.precio)}</div>
            {producto.stock !== null && producto.stock !== undefined && (
              <div className="vom-product-stock-num">
                Stock: <strong>{producto.stock}</strong>
                {producto.stockMinimo !== null && producto.stockMinimo !== undefined && (
                  <span style={{ color: 'var(--md-on-surface-variant)' }}>
                    {' '}· mín {producto.stockMinimo}
                  </span>
                )}
              </div>
            )}
          </div>
          <div className="vom-product-actions">
            <button className="vom-icon-btn" title="Editar" onClick={() => onEdit(producto)}>
              <Pencil size={14} />
            </button>
            <button className="vom-icon-btn danger" title="Eliminar" onClick={() => onDelete(producto.id)}>
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProductoForm({ producto, onSubmit, onCancel, saving }) {
  const editing = Boolean(producto?.id);
  const [foto, setFoto] = useState(producto?.foto || null);
  // El backend no acepta blob: URLs (creadas localmente con createObjectURL).
  // Para el MVP, si el usuario sube un archivo guardamos preview local pero
  // mandamos foto=null a Airtable (necesita upload a CDN aparte). Si el
  // usuario pega una URL pública (https://...) la guardamos tal cual.
  const isLocalBlob = typeof foto === 'string' && foto.startsWith('blob:');

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setFoto(url);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const stockStr = f.get('stock');
    const stock = stockStr === '' || stockStr === null ? null : Number(stockStr);
    const stockMinStr = f.get('stockMinimo');
    const stockMinimo = stockMinStr === '' || stockMinStr === null ? null : Number(stockMinStr);
    const stockIniStr = f.get('stockInicial');
    const stockInicial = stockIniStr === '' || stockIniStr === null ? null : Number(stockIniStr);
    // Si la foto es un blob:// local, no se la mandamos al backend (Airtable
    // no la puede acceder). Quedará como null hasta que tengamos upload a CDN.
    const fotoToSend = isLocalBlob ? null : foto;
    onSubmit({
      id:           producto?.id,
      nombre:       f.get('nombre'),
      precio:       Number(f.get('precio')),
      descripcion:  f.get('descripcion'),
      foto:         fotoToSend,
      stockInicial,
      stock,
      stockMinimo,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="vom-form">
      {/* Foto */}
      <label className="vom-photo-uploader">
        <input type="file" accept="image/*" onChange={handleFile} hidden />
        {foto ? (
          <img src={foto} alt="Preview" />
        ) : (
          <div className="vom-photo-uploader-empty">
            <ImageIcon size={28} />
            <span>Click para subir foto del producto</span>
          </div>
        )}
        <div className="vom-photo-uploader-overlay">
          <UploadIcon size={14} /> {foto ? 'Cambiar foto' : 'Subir foto'}
        </div>
      </label>

      <div className="vom-form-grid">
        <div className="vom-field full">
          <label htmlFor="p-nombre">Nombre del producto</label>
          <input
            id="p-nombre" name="nombre" required
            defaultValue={producto?.nombre || ''}
            className="vom-input"
          />
        </div>
        <div className="vom-field">
          <label htmlFor="p-precio">Precio (S/)</label>
          <input
            id="p-precio" name="precio" type="number" min="0" step="0.01" required
            defaultValue={producto?.precio || ''}
            className="vom-input"
          />
        </div>
        <div className="vom-field">
          <label htmlFor="p-stock">Stock actual</label>
          <input
            id="p-stock" name="stock" type="number" min="0"
            defaultValue={producto?.stock ?? ''}
            placeholder="Vacío = servicio"
            className="vom-input"
          />
        </div>
        <div className="vom-field">
          <label htmlFor="p-stockInicial">Stock inicial</label>
          <input
            id="p-stockInicial" name="stockInicial" type="number" min="0"
            defaultValue={producto?.stockInicial ?? producto?.stock ?? ''}
            className="vom-input"
          />
        </div>
        <div className="vom-field">
          <label htmlFor="p-stockMinimo">Stock mínimo (alerta)</label>
          <input
            id="p-stockMinimo" name="stockMinimo" type="number" min="0"
            defaultValue={producto?.stockMinimo ?? ''}
            className="vom-input"
          />
        </div>
        <div className="vom-field full">
          <label htmlFor="p-desc">Descripción</label>
          <textarea
            id="p-desc" name="descripcion" required rows="3"
            defaultValue={producto?.descripcion || ''}
            className="vom-textarea"
          />
        </div>
      </div>

      {isLocalBlob && (
        <div style={{ fontSize: '0.78rem', color: 'var(--md-warning)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <AlertCircle size={14} />
          La foto se previsualiza localmente. Para guardarla en el catálogo,
          subila a un servicio público (Drive, Imgur) y pegá la URL.
        </div>
      )}

      <div className="vom-modal-actions">
        <button type="button" className="vom-btn vom-btn-ghost" onClick={onCancel} disabled={saving}>
          Cancelar
        </button>
        <button type="submit" className="vom-btn vom-btn-primary" disabled={saving}>
          {saving ? (
            <><Loader2 size={16} style={{ animation: 'vom-fade 1s linear infinite' }} /> Guardando...</>
          ) : editing ? (
            <><Check size={16} /> Guardar cambios</>
          ) : (
            <><Plus size={16} /> Crear producto</>
          )}
        </button>
      </div>
    </form>
  );
}

export function ProductosSection() {
  const [productos, setProductos] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [editing, setEditing]     = useState(null); // null | {} (nuevo) | producto (editar)
  const [saving, setSaving]       = useState(false);

  // Carga inicial desde el API
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getJsonAuth(API.PRODUCTOS)
      .then((data) => {
        if (cancelled) return;
        setProductos(Array.isArray(data?.productos) ? data.productos : []);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('[productos]', err);
        setError('No se pudieron cargar los productos. Verificá que la tabla "productos" exista en Airtable.');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleSave = async (data) => {
    setSaving(true);
    try {
      if (data.id) {
        const res = await patchJsonAuth(`${API.PRODUCTOS}?id=${encodeURIComponent(data.id)}`, data);
        const updated = res.producto;
        setProductos(productos.map((p) => p.id === data.id ? updated : p));
      } else {
        const res = await postJsonAuth(API.PRODUCTOS, data);
        const created = res.producto;
        setProductos([created, ...productos]);
      }
      setEditing(null);
    } catch (err) {
      console.error('[productos] save', err);
      alert('No se pudo guardar el producto. Revisá la consola.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar este producto?')) return;
    try {
      await deleteJsonAuth(`${API.PRODUCTOS}?id=${encodeURIComponent(id)}`);
      setProductos(productos.filter((p) => p.id !== id));
    } catch (err) {
      console.error('[productos] delete', err);
      alert('No se pudo eliminar el producto.');
    }
  };

  return (
    <>
      <SectionHeader
        title="Productos"
        subtitle={
          loading
            ? 'Cargando catálogo...'
            : `${productos.length} producto${productos.length === 1 ? '' : 's'} y servicio${productos.length === 1 ? '' : 's'} disponibles para venta automática`
        }
        action={
          <button className="vom-btn vom-btn-primary" onClick={() => setEditing({})} disabled={loading}>
            <Plus size={16} /> Agregar producto
          </button>
        }
      />

      {loading && (
        <div className="vom-card" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center', padding: '2rem' }}>
          <Loader2 size={18} style={{ animation: 'vom-fade 1s linear infinite' }} />
          <span style={{ color: 'var(--md-on-surface-variant)' }}>Cargando productos desde Airtable...</span>
        </div>
      )}

      {error && !loading && (
        <div className="vom-card" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--md-error)' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && productos.length === 0 && (
        <div className="vom-card" style={{ textAlign: 'center', padding: '2.5rem 1rem', color: 'var(--md-on-surface-variant)' }}>
          <Package size={32} style={{ color: 'var(--md-outline)', marginBottom: '0.5rem' }} />
          <p style={{ margin: 0 }}>Todavía no tenés productos cargados.</p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
            Hacé click en <strong>"Agregar producto"</strong> para empezar tu catálogo.
          </p>
        </div>
      )}

      {!loading && !error && productos.length > 0 && (
        <div className="vom-product-grid">
          {productos.map((p) => (
            <ProductoCard key={p.id} producto={p} onEdit={setEditing} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {editing && (
        <Modal
          title={editing.id ? 'Editar producto' : 'Nuevo producto'}
          onClose={() => !saving && setEditing(null)}
        >
          <ProductoForm
            producto={editing}
            onSubmit={handleSave}
            onCancel={() => setEditing(null)}
            saving={saving}
          />
        </Modal>
      )}
    </>
  );
}

// ─────────────────────────────────────
// 4 · RESPUESTAS IA (chats)
// ─────────────────────────────────────

export function RespuestasIASection() {
  const [conversaciones, setConversaciones] = useState([]);
  const [loading, setLoading]               = useState(true);
  const [selectedId, setSelectedId]         = useState(null);
  const [error, setError]                   = useState(null);

  // Polling lista de conversaciones cada 3s
  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const tick = async () => {
      try {
        const data = await getJsonAuth(API.CONVERSACIONES);
        if (cancelled) return;
        const list = Array.isArray(data?.conversaciones) ? data.conversaciones : [];
        setConversaciones(list);
        setError(null);
        // Si no hay seleccionada, autoselect la primera
        if (!selectedId && list.length > 0) {
          setSelectedId(list[0].id);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('[RespuestasIA] poll convs:', err);
        setError('No se pudieron cargar las conversaciones.');
      } finally {
        if (!cancelled) {
          setLoading(false);
          timer = setTimeout(tick, 3000);
        }
      }
    };
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = conversaciones.find((c) => c.id === selectedId) || null;

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar esta conversación y todos sus mensajes?')) return;
    try {
      await deleteJsonAuth(`${API.CONVERSACIONES}&id=${encodeURIComponent(id)}`);
      setConversaciones((curr) => curr.filter((c) => c.id !== id));
      if (selectedId === id) setSelectedId(null);
    } catch (err) {
      console.error('[RespuestasIA] delete:', err);
      alert('No se pudo eliminar.');
    }
  };

  const handleModoChange = async (convId, nuevoModo) => {
    try {
      await postJsonAuth(API.CONVERSACIONES_MODO, { conversacion_id: convId, modo: nuevoModo });
      setConversaciones((curr) => curr.map((c) => c.id === convId ? { ...c, modo: nuevoModo } : c));
    } catch (err) {
      console.error('[RespuestasIA] modo:', err);
      alert('No se pudo cambiar el modo.');
    }
  };

  return (
    <>
      <SectionHeader
        title="Respuestas IA"
        subtitle="Conversaciones reales que la IA está manejando vía WhatsApp. Cambiá a modo HUMAN para tomar el control."
      />

      {loading && (
        <div className="vom-card" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center', padding: '2rem' }}>
          <Loader2 size={18} className="ce-spin" />
          <span style={{ color: 'var(--md-on-surface-variant)' }}>Cargando conversaciones...</span>
        </div>
      )}

      {error && !loading && (
        <div className="vom-card" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--md-error)' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && conversaciones.length === 0 && (
        <div className="vom-card" style={{ textAlign: 'center', padding: '2.5rem 1rem', color: 'var(--md-on-surface-variant)' }}>
          <MessageCircle size={32} style={{ color: 'var(--md-outline)', marginBottom: '0.5rem' }} />
          <p style={{ margin: 0 }}>Todavía no hay conversaciones.</p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
            Cuando alguien te escriba a tu WhatsApp conectado, va a aparecer acá.
          </p>
        </div>
      )}

      {!loading && !error && conversaciones.length > 0 && (
        <div className="vom-chat-layout">
          <ConversacionesList
            items={conversaciones}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          {selected ? (
            <ConversacionPanel
              conversacion={selected}
              onModoChange={(modo) => handleModoChange(selected.id, modo)}
              onDelete={() => handleDelete(selected.id)}
            />
          ) : (
            <div className="vom-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px', color: 'var(--md-on-surface-variant)' }}>
              Seleccioná una conversación
            </div>
          )}
        </div>
      )}
    </>
  );
}

function ConversacionesList({ items, selectedId, onSelect }) {
  return (
    <div className="vom-card vom-conv-list">
      <h3 className="vom-card-title" style={{ marginBottom: '0.6rem' }}>
        {items.length} conversaci{items.length === 1 ? 'ón' : 'ones'}
      </h3>
      <div className="vom-conv-list-items">
        {items.map((c) => {
          const isSelected = c.id === selectedId;
          return (
            <button
              key={c.id}
              type="button"
              className={`vom-conv-item ${isSelected ? 'is-selected' : ''}`}
              onClick={() => onSelect(c.id)}
            >
              <div className="vom-conv-item-top">
                <span className="vom-conv-item-name">{c.nombre || c.phone || '—'}</span>
                <span className={`vom-conv-modo-badge ${c.modo === 'HUMAN' ? 'human' : 'ai'}`}>
                  {c.modo === 'HUMAN' ? 'HUMAN' : 'IA'}
                </span>
              </div>
              <div className="vom-conv-item-meta">
                {c.phone}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ConversacionPanel({ conversacion, onModoChange, onDelete }) {
  const [mensajes, setMensajes] = useState([]);
  const [draft, setDraft]       = useState('');
  const [sending, setSending]   = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(true);
  const scrollRef = useRef(null);

  // Polling de mensajes cada 2.5s
  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const tick = async () => {
      try {
        const data = await getJsonAuth(`${API.MENSAJES}&conversacion_id=${encodeURIComponent(conversacion.id)}`);
        if (cancelled) return;
        const list = Array.isArray(data?.mensajes) ? data.mensajes : [];
        setMensajes((prev) => {
          // Solo actualizar si cambió el count o el último id (evita re-render innecesario)
          if (prev.length === list.length && prev[prev.length - 1]?.id === list[list.length - 1]?.id) {
            return prev;
          }
          return list;
        });
      } catch (err) {
        if (cancelled) return;
        console.error('[Panel] poll msgs:', err);
      } finally {
        if (!cancelled) {
          setLoadingMsgs(false);
          timer = setTimeout(tick, 2500);
        }
      }
    };
    setLoadingMsgs(true);
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [conversacion.id]);

  // Auto-scroll al fondo cuando llegan mensajes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [mensajes.length]);

  const isHuman = conversacion.modo === 'HUMAN';

  const handleSend = async () => {
    const txt = draft.trim();
    if (!txt) return;
    setSending(true);
    try {
      await postJsonAuth(API.MENSAJES, {
        conversacion_id: conversacion.id,
        role: 'human',
        content: txt,
      });
      setDraft('');
    } catch (err) {
      console.error('[Panel] send:', err);
      alert('No se pudo enviar.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="vom-card vom-conv-panel">
      {/* Header del panel */}
      <div className="vom-conv-panel-header">
        <div>
          <div className="vom-conv-panel-name">{conversacion.nombre || conversacion.phone}</div>
          <div className="vom-conv-panel-phone">{conversacion.phone}</div>
        </div>
        <div className="vom-conv-panel-actions">
          <ModeToggle modo={conversacion.modo} onChange={onModoChange} />
          <button className="vom-icon-btn danger" title="Borrar" onClick={onDelete}>
            <Trash size={14} />
          </button>
        </div>
      </div>

      {/* Mensajes */}
      <div className="vom-conv-msgs" ref={scrollRef}>
        {loadingMsgs && mensajes.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--md-on-surface-variant)' }}>
            Cargando mensajes...
          </div>
        ) : mensajes.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--md-on-surface-variant)' }}>
            Sin mensajes todavía.
          </div>
        ) : (
          mensajes.map((m) => <MessageBubble key={m.id} mensaje={m} />)
        )}
      </div>

      {/* Composer (solo en HUMAN) */}
      <div className="vom-conv-composer">
        {isHuman ? (
          <>
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !sending) handleSend(); }}
              placeholder="Escribí tu respuesta..."
              disabled={sending}
              className="vom-composer-input"
            />
            <button
              className="vom-btn vom-btn-primary"
              onClick={handleSend}
              disabled={sending || !draft.trim()}
              style={{ padding: '0.55rem 0.95rem' }}
            >
              {sending ? <Loader2 size={14} className="ce-spin" /> : <Send size={14} />}
            </button>
          </>
        ) : (
          <div className="vom-composer-disabled">
            <Bot size={14} /> El bot responde automáticamente. Cambiá a modo HUMAN para tomar el control.
          </div>
        )}
      </div>
    </div>
  );
}

function ModeToggle({ modo, onChange }) {
  return (
    <div className="vom-mode-toggle">
      <button
        type="button"
        className={`vom-mode-option ${modo === 'AI' ? 'is-active ai' : ''}`}
        onClick={() => onChange('AI')}
      >
        <Bot size={12} /> IA
      </button>
      <button
        type="button"
        className={`vom-mode-option ${modo === 'HUMAN' ? 'is-active human' : ''}`}
        onClick={() => onChange('HUMAN')}
      >
        <UserIcon size={12} /> HUMAN
      </button>
    </div>
  );
}

function MessageBubble({ mensaje }) {
  // user → izquierda (cliente), assistant/human → derecha (la empresa)
  const isInbound = mensaje.role === 'user';
  const variant = mensaje.role === 'human' ? 'human' : (mensaje.role === 'assistant' ? 'ai' : 'user');
  return (
    <div className={`vom-msg-row ${isInbound ? 'inbound' : 'outbound'}`}>
      <div className={`vom-msg-bubble ${variant}`}>
        <div className="vom-msg-content">{mensaje.content}</div>
        <div className="vom-msg-time">
          {mensaje.created_at ? formatTime(mensaje.created_at) : ''}
          {mensaje.role === 'human' && <span className="vom-msg-who"> · humano</span>}
          {mensaje.role === 'assistant' && <span className="vom-msg-who"> · IA</span>}
        </div>
      </div>
    </div>
  );
}

function formatTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

// ─────────────────────────────────────
// 5 · CONFIGURACIÓN (solo Canales WhatsApp)
// ─────────────────────────────────────


function CanalesBlock() {
  return (
    <>
      <WhatsAppBlock />
      <ProximamenteBlock />
    </>
  );
}

function WhatsAppBlock() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);

  // Polling de /api/wa: cada 2s si no está conectado, cada 15s si lo está
  // (para detectar desconexiones externas). El backend resuelve `empresa_id`
  // del JWT — no se manda por query/body desde el frontend.
  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      let nextDelay = 2000;
      try {
        const data = await getJsonAuth(API.WA);
        if (cancelled) return;
        const newSession = data?.session || null;
        setSession(newSession);
        setError(null);
        nextDelay = newSession?.status === 'connected' ? 15000 : 2000;
      } catch (err) {
        if (cancelled) return;
        console.error('[CanalesBlock] poll error:', err);
        setError('No se pudo consultar el estado. Reintentando...');
        nextDelay = 5000;
      } finally {
        if (!cancelled) {
          setLoading(false);
          timer = setTimeout(tick, nextDelay);
        }
      }
    };
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const handleConnect = async () => {
    setActionLoading(true);
    try {
      await postJsonAuth(`${API.WA}&action=connect`, {});
    } catch (err) {
      console.error('[CanalesBlock] connect:', err);
      alert('No se pudo iniciar la conexión.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('¿Desconectar WhatsApp? El bot dejará de recibir y enviar mensajes.')) return;
    setActionLoading(true);
    try {
      await postJsonAuth(`${API.WA}&action=disconnect`, {});
    } catch (err) {
      console.error('[CanalesBlock] disconnect:', err);
      alert('No se pudo desconectar.');
    } finally {
      setActionLoading(false);
    }
  };

  const status = session?.status || 'disconnected';
  const qrString = session?.qr_string;
  const phone = session?.phone;

  return (
    <div className="vom-card">
      <div className="vom-config-header">
        <div className="vom-config-title-block">
          <h3 className="vom-card-title">WhatsApp Business</h3>
          <p className="vom-config-description">
            Conectá tu número de WhatsApp para que la IA reciba y responda
            mensajes automáticamente.
          </p>
        </div>
        <div className="vom-config-controls">
          <span className="vom-config-summary">
            {status === 'connected' ? 'Conectado' : 'Sin conectar'}
          </span>
        </div>
      </div>

      <div className="vom-config-body" style={{ marginTop: '1.1rem', paddingTop: '1.1rem', borderTop: '1px solid #E2E8F0' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--md-on-surface-variant)', padding: '1rem' }}>
            <Loader2 size={16} className="ce-spin" />
            Consultando estado de la conexión...
          </div>
        ) : (
          <WhatsAppCard
            status={status}
            qrString={qrString}
            phone={phone}
            error={error}
            actionLoading={actionLoading}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
          />
        )}
      </div>
    </div>
  );
}

// Bloque separado para canales en roadmap. Sin lógica, solo placeholders.
function ProximamenteBlock() {
  return (
    <div className="vom-card">
      <div className="vom-config-header">
        <div className="vom-config-title-block">
          <h3 className="vom-card-title">Próximamente</h3>
          <p className="vom-config-description">
            Estos canales se podrán conectar en próximas versiones.
          </p>
        </div>
      </div>
      <div className="vom-config-body" style={{ marginTop: '1.1rem', paddingTop: '1.1rem', borderTop: '1px solid #E2E8F0' }}>
        <div className="vom-channel-list">
          {[
            { id: 'facebook',  nombre: 'Facebook Messenger' },
            { id: 'instagram', nombre: 'Instagram DM' },
            { id: 'linkedin',  nombre: 'LinkedIn' },
          ].map((c) => (
            <div key={c.id} className="vom-channel-row disconnected" style={{ opacity: 0.5 }}>
              <div className="vom-channel-icon">
                <MessageCircle size={18} />
              </div>
              <div className="vom-channel-info">
                <div className="vom-channel-name">{c.nombre}</div>
                <div className="vom-channel-meta">Próximamente</div>
              </div>
              <span className="vom-channel-status disconnected">No disponible</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function WhatsAppCard({ status, qrString, phone, error, actionLoading, onConnect, onDisconnect }) {
  // Coerción defensiva: Airtable a veces devuelve campos como arrays/objetos
  // si la columna fue cambiada de tipo. Si llega algo raro, lo serializamos
  // a string en lugar de crashear React (#130 "Objects are not valid as a React child").
  const safe = (v) => {
    if (v == null) return '';
    if (typeof v === 'string' || typeof v === 'number') return v;
    if (Array.isArray(v)) return v.map(safe).join(', ');
    try { return JSON.stringify(v); } catch { return ''; }
  };
  const phoneStr  = safe(phone);
  const qrStr     = safe(qrString);
  const statusStr = safe(status) || 'disconnected';
  return (
    <div className={`vom-channel-row ${statusStr === 'connected' ? 'connected' : 'disconnected'}`} style={{ flexDirection: 'column', alignItems: 'stretch', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', width: '100%' }}>
        <div className="vom-channel-icon">
          <MessageCircle size={18} />
        </div>
        <div className="vom-channel-info" style={{ flex: 1 }}>
          <div className="vom-channel-name">WhatsApp Business</div>
          <div className="vom-channel-meta">
            {statusStr === 'connected' && phoneStr ? phoneStr : statusLabel(statusStr)}
          </div>
        </div>
        <span className={`vom-channel-status ${statusStr === 'connected' ? 'connected' : 'disconnected'}`}>
          {statusLabel(statusStr)}
        </span>

        {status === 'disconnected' && (
          <button
            className="vom-btn vom-btn-primary"
            onClick={onConnect}
            disabled={actionLoading}
            style={{ padding: '0.5rem 0.95rem', fontSize: '0.85rem' }}
          >
            {actionLoading ? <Loader2 size={14} className="ce-spin" /> : <Power size={14} />}
            Vincular WhatsApp
          </button>
        )}

        {status === 'connected' && (
          <button
            className="vom-btn vom-btn-ghost"
            onClick={onDisconnect}
            disabled={actionLoading}
            style={{ padding: '0.5rem 0.95rem', fontSize: '0.85rem' }}
          >
            {actionLoading ? <Loader2 size={14} className="ce-spin" /> : <PowerOff size={14} />}
            Desconectar
          </button>
        )}
      </div>

      {/* QR */}
      {(statusStr === 'qr' || statusStr === 'connecting') && (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '1.25rem', background: 'var(--md-surface)', borderRadius: '12px',
          border: '1px solid var(--md-outline-variant)',
        }}>
          {qrStr ? (
            <>
              <div style={{ background: 'white', padding: '12px', borderRadius: '12px' }}>
                <QRCodeSVG value={qrStr} size={240} level="M" />
              </div>
              <p style={{ marginTop: '1rem', fontSize: '0.88rem', color: 'var(--md-on-surface)', textAlign: 'center', maxWidth: 320 }}>
                <strong>Escaneá con tu WhatsApp:</strong><br />
                Ajustes → Dispositivos vinculados → Vincular un dispositivo
              </p>
              <p style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--md-on-surface-variant)', textAlign: 'center' }}>
                El QR se actualiza cada ~30 segundos automáticamente.
              </p>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.6rem', padding: '2rem' }}>
              <Loader2 size={32} className="ce-spin" style={{ color: 'var(--md-primary)' }} />
              <p style={{ fontSize: '0.88rem', color: 'var(--md-on-surface-variant)' }}>
                {statusStr === 'connecting' ? 'Conectando...' : 'Generando código QR...'}
              </p>
            </div>
          )}
        </div>
      )}

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: 'var(--md-error)' }}>
          <AlertCircle size={14} />
          {safe(error)}
        </div>
      )}
    </div>
  );
}

function statusLabel(status) {
  switch (status) {
    case 'connected':    return 'Conectado';
    case 'connecting':   return 'Conectando...';
    case 'qr':           return 'Esperando escaneo';
    case 'disconnected':
    default:             return 'No conectado';
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Contexto del agente IA — config.ventas.* (paso 4)
// ─────────────────────────────────────────────────────────────────────────

const DEFAULT_VENTAS_CONFIG = {
  estilo_vendedor:      { activo: false, valor: 'formal_profesional' },
  nombre_vendedor:      { activo: false, valor: '' },
  tipo_cliente:         { activo: false, valor: 'mixto' },
  zona_cobertura:       { activo: false, valor: '' },
  tiempo_entrega:       { activo: false, valor: '' },
  metodos_pago:         { activo: false, valor: [] },
  politica_precios:     { activo: false, valor: { igv: 'incluido', comprobantes: 'ambos' } },
  asesor_humano:        { activo: false, valor: { nombre: '', telefono: '' } },
  criterios_derivacion: { activo: false, valor: [] },
  horario_ia:           { activo: false, valor: '24_7' },
  info_adicional:       { activo: false, valor: [] },
};

const ESTILO_VENDEDOR_OPCIONES = [
  { id: 'formal_profesional', label: 'Formal y profesional (usted, vocabulario corporativo)' },
  { id: 'cercano_amigable',   label: 'Cercano y amigable (tú, conversacional)' },
  { id: 'tecnico_consultivo', label: 'Técnico-consultivo (usted, vocabulario especializado)' },
  { id: 'casual_directo',     label: 'Casual y directo (tú, mensajes cortos)' },
];

const TIPO_CLIENTE_OPCIONES = [
  { id: 'b2b',   label: 'Empresas (B2B)' },
  { id: 'b2c',   label: 'Consumidores finales (B2C)' },
  { id: 'mixto', label: 'Mixto' },
];

const METODOS_PAGO_OPCIONES = [
  { id: 'efectivo',            label: 'Efectivo' },
  { id: 'yape_plin',           label: 'Yape / Plin' },
  { id: 'transferencia',       label: 'Transferencia bancaria' },
  { id: 'tarjeta_pos',         label: 'Tarjeta (POS presencial)' },
  { id: 'tarjeta_online',      label: 'Tarjeta online' },
  { id: 'credito_empresarial', label: 'Crédito empresarial (30/60/90 días)' },
  { id: 'contra_entrega',      label: 'Contra-entrega' },
];

const IGV_OPCIONES = [
  { id: 'incluido',    label: 'Incluyen IGV' },
  { id: 'no_incluido', label: 'NO incluyen IGV (se agrega al final)' },
  { id: 'referencial', label: 'Son referenciales (cotización formal aparte)' },
];

const COMPROBANTES_OPCIONES = [
  { id: 'boleta',  label: 'Solo boleta' },
  { id: 'factura', label: 'Solo factura' },
  { id: 'ambos',   label: 'Boleta o factura según el cliente' },
];

const CRITERIOS_DERIVACION_OPCIONES = [
  { id: 'cotizacion_formal',     label: 'Pide cotización formal o factura proforma' },
  { id: 'descuento_negociacion', label: 'Pide descuento especial o negociación' },
  { id: 'modificar_pedido',      label: 'Quiere modificar o cancelar un pedido en curso' },
  { id: 'queja_reclamo',         label: 'Expresa queja, reclamo o tono molesto' },
  { id: 'fuera_catalogo',        label: 'Pide algo que no figura en el catálogo' },
  { id: 'menciona_competencia',  label: 'Menciona competencia o compara precios' },
  { id: 'intencion_compra',      label: 'Confirma intención clara de compra' },
  { id: 'conversacion_larga',    label: 'La conversación supera 10 mensajes sin avanzar' },
];

const HORARIO_IA_OPCIONES = [
  { id: '24_7',                  label: '24/7 (siempre responde)' },
  { id: 'solo_horario_atencion', label: 'Solo en horario de atención de la empresa' },
];

const INFO_CATEGORIA_OPCIONES = [
  { id: 'faq',                label: 'FAQ' },
  { id: 'promocion',          label: 'Promoción' },
  { id: 'servicio_adicional', label: 'Servicio adicional' },
  { id: 'info_importante',    label: 'Información importante' },
  { id: 'politica',           label: 'Política' },
];

const INFO_ADICIONAL_MAX = 20;

const todayISO = () => new Date().toISOString().slice(0, 10);

// ── Helpers de UI compartidos ────────────────────────────────────────────

export function CampoToggle({ campo, label, helpText, activo, onActivoChange, children }) {
  return (
    <div className={`via-config-row ${activo ? '' : 'disabled'}`}>
      <div className="via-config-row-header">
        <Toggle checked={activo} onChange={onActivoChange} ariaLabel={label} />
        <label className="via-config-row-label" htmlFor={campo ? `via-${campo}` : undefined}>
          {label}
          <span className="via-config-row-optional"> (opcional)</span>
        </label>
      </div>
      <div className="via-config-row-input">
        {children}
      </div>
      {helpText && <div className="via-config-row-help">{helpText}</div>}
    </div>
  );
}

function CampoTexto({ campo, label, helpText, placeholder, maxLength, activo, valor, onActivoChange, onValorChange }) {
  return (
    <CampoToggle campo={campo} label={label} helpText={helpText} activo={activo} onActivoChange={onActivoChange}>
      <input
        id={`via-${campo}`}
        className="vom-input"
        type="text"
        placeholder={placeholder}
        value={valor || ''}
        disabled={!activo}
        maxLength={maxLength}
        onChange={(e) => onValorChange(e.target.value)}
      />
    </CampoToggle>
  );
}

function CampoTextarea({ campo, label, helpText, placeholder, rows = 3, activo, valor, onActivoChange, onValorChange }) {
  return (
    <CampoToggle campo={campo} label={label} helpText={helpText} activo={activo} onActivoChange={onActivoChange}>
      <textarea
        id={`via-${campo}`}
        className="vom-textarea"
        placeholder={placeholder}
        rows={rows}
        value={valor || ''}
        disabled={!activo}
        onChange={(e) => onValorChange(e.target.value)}
      />
    </CampoToggle>
  );
}

function CampoSelect({ campo, label, helpText, opciones, activo, valor, onActivoChange, onValorChange }) {
  return (
    <CampoToggle campo={campo} label={label} helpText={helpText} activo={activo} onActivoChange={onActivoChange}>
      <select
        id={`via-${campo}`}
        className="vom-input"
        value={valor || opciones[0]?.id}
        disabled={!activo}
        onChange={(e) => onValorChange(e.target.value)}
      >
        {opciones.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
    </CampoToggle>
  );
}

function CampoRadio({ campo, label, helpText, opciones, activo, valor, onActivoChange, onValorChange }) {
  return (
    <CampoToggle campo={campo} label={label} helpText={helpText} activo={activo} onActivoChange={onActivoChange}>
      <div className="via-radio-group">
        {opciones.map(o => (
          <label key={o.id} className={`via-radio-option ${valor === o.id ? 'selected' : ''}`}>
            <input
              type="radio"
              name={`via-${campo}`}
              value={o.id}
              checked={valor === o.id}
              disabled={!activo}
              onChange={() => onValorChange(o.id)}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </CampoToggle>
  );
}

function CampoMultiCheck({ campo, label, helpText, opciones, activo, valor, onActivoChange, onToggleItem }) {
  const seleccionados = Array.isArray(valor) ? valor : [];
  return (
    <CampoToggle campo={campo} label={label} helpText={helpText} activo={activo} onActivoChange={onActivoChange}>
      <div className="via-check-group">
        {opciones.map(o => {
          const checked = seleccionados.includes(o.id);
          return (
            <label key={o.id} className={`via-check-option ${checked ? 'selected' : ''}`}>
              <input
                type="checkbox"
                checked={checked}
                disabled={!activo}
                onChange={() => onToggleItem(o.id)}
              />
              <span>{o.label}</span>
            </label>
          );
        })}
      </div>
    </CampoToggle>
  );
}

function CampoPoliticaPrecios({ campo, label, helpText, activo, valor, onActivoChange, onValorChange }) {
  const v = valor || { igv: 'incluido', comprobantes: 'ambos' };
  return (
    <CampoToggle campo={campo} label={label} helpText={helpText} activo={activo} onActivoChange={onActivoChange}>
      <div className="via-subfield-grid">
        <div className="via-subfield">
          <label className="via-subfield-label">Los precios del catálogo:</label>
          <select
            className="vom-input"
            value={v.igv}
            disabled={!activo}
            onChange={(e) => onValorChange({ ...v, igv: e.target.value })}
          >
            {IGV_OPCIONES.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
        <div className="via-subfield">
          <label className="via-subfield-label">Comprobantes que emitimos:</label>
          <select
            className="vom-input"
            value={v.comprobantes}
            disabled={!activo}
            onChange={(e) => onValorChange({ ...v, comprobantes: e.target.value })}
          >
            {COMPROBANTES_OPCIONES.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
      </div>
    </CampoToggle>
  );
}

function CampoAsesorHumano({ campo, label, helpText, activo, valor, onActivoChange, onValorChange }) {
  const v = valor || { nombre: '', telefono: '' };
  return (
    <CampoToggle campo={campo} label={label} helpText={helpText} activo={activo} onActivoChange={onActivoChange}>
      <div className="via-subfield-grid">
        <div className="via-subfield">
          <label className="via-subfield-label">Nombre:</label>
          <input
            className="vom-input"
            type="text"
            placeholder="Carlos Mejía"
            value={v.nombre || ''}
            disabled={!activo}
            onChange={(e) => onValorChange({ ...v, nombre: e.target.value })}
          />
        </div>
        <div className="via-subfield">
          <label className="via-subfield-label">Teléfono:</label>
          <input
            className="vom-input"
            type="text"
            placeholder="+51 999 888 777"
            value={v.telefono || ''}
            disabled={!activo}
            onChange={(e) => onValorChange({ ...v, telefono: e.target.value })}
          />
        </div>
      </div>
    </CampoToggle>
  );
}

function InfoAdicionalEditor({ activo, valor, onActivoChange, onValorChange }) {
  const entradas = Array.isArray(valor) ? valor : [];
  const hoy = todayISO();

  const updateEntry = (idx, patch) => {
    onValorChange(entradas.map((e, i) => i === idx ? { ...e, ...patch } : e));
  };
  const removeEntry = (idx) => {
    if (!window.confirm('¿Eliminar esta entrada?')) return;
    onValorChange(entradas.filter((_, i) => i !== idx));
  };
  const addEntry = () => {
    if (entradas.length >= INFO_ADICIONAL_MAX) return;
    onValorChange([
      ...entradas,
      { categoria: 'faq', titulo: '', respuesta: '', vigencia_inicio: null, vigencia_fin: null },
    ]);
  };

  return (
    <CampoToggle
      campo="info_adicional"
      label="Información adicional"
      helpText={`FAQs, promociones, servicios y políticas que el agente puede usar al responder. Máximo ${INFO_ADICIONAL_MAX} entradas.`}
      activo={activo}
      onActivoChange={onActivoChange}
    >
      <div className="via-info-adicional">
        <div className="via-info-adicional-header">
          {entradas.length} / {INFO_ADICIONAL_MAX} entradas
        </div>
        {entradas.length === 0 && (
          <div className="via-info-adicional-empty">
            Sin entradas. Agregá una para empezar.
          </div>
        )}
        {entradas.map((e, idx) => {
          const esPromocion = e.categoria === 'promocion';
          const vencida = esPromocion && e.vigencia_fin && e.vigencia_fin < hoy;
          const respuestaLen = (e.respuesta || '').length;
          return (
            <div key={idx} className="via-info-adicional-entry">
              <div className="via-info-adicional-entry-head">
                <select
                  className="vom-input"
                  value={e.categoria}
                  disabled={!activo}
                  onChange={(ev) => updateEntry(idx, { categoria: ev.target.value })}
                >
                  {INFO_CATEGORIA_OPCIONES.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
                </select>
                {vencida && (
                  <span className="via-info-adicional-vencida">Vencida</span>
                )}
                <button
                  type="button"
                  className="via-info-adicional-remove"
                  onClick={() => removeEntry(idx)}
                  disabled={!activo}
                  aria-label="Eliminar entrada"
                >
                  <X size={14} />
                </button>
              </div>
              <input
                className="vom-input"
                type="text"
                placeholder="Título corto (ej. ¿Tienen garantía?)"
                value={e.titulo || ''}
                disabled={!activo}
                maxLength={120}
                onChange={(ev) => updateEntry(idx, { titulo: ev.target.value })}
              />
              <textarea
                className="vom-textarea"
                placeholder="Respuesta o detalle…"
                rows={2}
                value={e.respuesta || ''}
                disabled={!activo}
                maxLength={600}
                onChange={(ev) => updateEntry(idx, { respuesta: ev.target.value })}
              />
              <div className="via-info-adicional-counter">{respuestaLen} / 600</div>

              {esPromocion && (
                <div className="via-info-adicional-vigencia">
                  <label>
                    Desde:
                    <input
                      type="date"
                      className="vom-input"
                      value={e.vigencia_inicio || ''}
                      disabled={!activo}
                      onChange={(ev) => updateEntry(idx, { vigencia_inicio: ev.target.value || null })}
                    />
                  </label>
                  <label>
                    Hasta:
                    <input
                      type="date"
                      className="vom-input"
                      value={e.vigencia_fin || ''}
                      disabled={!activo}
                      onChange={(ev) => updateEntry(idx, { vigencia_fin: ev.target.value || null })}
                    />
                  </label>
                </div>
              )}
            </div>
          );
        })}
        <button
          type="button"
          className="via-info-adicional-add"
          onClick={addEntry}
          disabled={!activo || entradas.length >= INFO_ADICIONAL_MAX}
        >
          <Plus size={14} /> Agregar entrada
        </button>
      </div>
    </CampoToggle>
  );
}

function ContextoAgenteBlock() {
  // Persistencia centralizada en Airtable Config_Ventas (paso 6).
  const { data, loading, saving, save } = useEmpresaConfig('ventas');

  const [config, setConfig] = useState(DEFAULT_VENTAS_CONFIG);
  const [savedHint, setSavedHint] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Hidratar el form cuando llegan los datos de Airtable.
  useEffect(() => {
    if (!data) return;
    const merged = { ...DEFAULT_VENTAS_CONFIG };
    for (const key of Object.keys(merged)) {
      if (data[key]) {
        merged[key] = {
          activo: !!data[key].activo,
          valor:  data[key].valor !== undefined ? data[key].valor : merged[key].valor,
        };
      }
    }
    setConfig(merged);
  }, [data]);

  const setActivo = (campo, activo) =>
    setConfig(prev => ({ ...prev, [campo]: { ...prev[campo], activo } }));

  const setValor = (campo, valor) =>
    setConfig(prev => ({ ...prev, [campo]: { ...prev[campo], valor } }));

  const toggleArrayItem = (campo, item) =>
    setConfig(prev => {
      const arr = Array.isArray(prev[campo].valor) ? prev[campo].valor : [];
      const next = arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item];
      return { ...prev, [campo]: { ...prev[campo], valor: next } };
    });

  const handleSave = async () => {
    setSaveError(null);
    const ok = await save(config);
    if (ok) {
      setSavedHint(true);
      setTimeout(() => setSavedHint(false), 2500);
    } else {
      setSaveError('No se pudo guardar. Intentá de nuevo.');
    }
  };

  return (
    <div className="vom-card via-config-block">
      <div className="vom-config-header">
        <div className="vom-config-title-block">
          <h3 className="vom-card-title">Contexto del agente IA</h3>
          <p className="vom-config-description">
            Datos opcionales que enriquecen las respuestas del agente. Activá solo
            los campos que quieras compartir; los apagados no se incluyen en su
            comportamiento.
          </p>
        </div>
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--md-on-surface-variant)', padding: '1rem' }}>
          <Loader2 size={16} className="ce-spin" />
          Cargando configuración...
        </div>
      ) : (
        <>
          {/* Grupo 1 — Estilo de comunicación */}
          <div className="via-config-group">
            <h4 className="via-config-group-title">Estilo de comunicación</h4>
            <CampoSelect
              campo="estilo_vendedor"
              label="Estilo del agente"
              helpText="Define el tratamiento (tú/usted) y el tono general del agente."
              opciones={ESTILO_VENDEDOR_OPCIONES}
              activo={config.estilo_vendedor.activo}
              valor={config.estilo_vendedor.valor}
              onActivoChange={(v) => setActivo('estilo_vendedor', v)}
              onValorChange={(v) => setValor('estilo_vendedor', v)}
            />
            <CampoTexto
              campo="nombre_vendedor"
              label="Nombre del agente"
              helpText="Nombre con el que se presenta el agente. Si lo dejás vacío, se presenta como 'el equipo de [empresa]'."
              placeholder="Ej: Carlos, Sofía"
              maxLength={30}
              activo={config.nombre_vendedor.activo}
              valor={config.nombre_vendedor.valor}
              onActivoChange={(v) => setActivo('nombre_vendedor', v)}
              onValorChange={(v) => setValor('nombre_vendedor', v)}
            />
          </div>

          {/* Grupo 2 — Quién compra y desde dónde */}
          <div className="via-config-group">
            <h4 className="via-config-group-title">Quién compra y desde dónde</h4>
            <CampoRadio
              campo="tipo_cliente"
              label="Tipo de cliente"
              helpText="Cambia qué datos pide el agente al cierre (RUC para empresas, DNI para personas)."
              opciones={TIPO_CLIENTE_OPCIONES}
              activo={config.tipo_cliente.activo}
              valor={config.tipo_cliente.valor}
              onActivoChange={(v) => setActivo('tipo_cliente', v)}
              onValorChange={(v) => setValor('tipo_cliente', v)}
            />
            <CampoTextarea
              campo="zona_cobertura"
              label="Zona de cobertura"
              helpText="Zonas donde la empresa atiende u opera. Ej: 'Lima Metropolitana y Callao' o 'Atendemos online en todo Perú'."
              placeholder="Lima Metropolitana y Callao"
              rows={2}
              activo={config.zona_cobertura.activo}
              valor={config.zona_cobertura.valor}
              onActivoChange={(v) => setActivo('zona_cobertura', v)}
              onValorChange={(v) => setValor('zona_cobertura', v)}
            />
          </div>

          {/* Grupo 3 — Operación comercial */}
          <div className="via-config-group">
            <h4 className="via-config-group-title">Operación comercial</h4>
            <CampoTextarea
              campo="tiempo_entrega"
              label="Tiempos de entrega / respuesta"
              helpText="Tiempos típicos en lenguaje natural. Ej: 'Stock: 24-48h Lima, 3-5 días provincias. Bajo pedido: 7-15 días'."
              placeholder="Stock: 24-48h Lima, 3-5 días provincias..."
              rows={3}
              activo={config.tiempo_entrega.activo}
              valor={config.tiempo_entrega.valor}
              onActivoChange={(v) => setActivo('tiempo_entrega', v)}
              onValorChange={(v) => setValor('tiempo_entrega', v)}
            />
            <CampoMultiCheck
              campo="metodos_pago"
              label="Métodos de pago aceptados"
              helpText="Métodos que aceptás. El agente los menciona al cierre."
              opciones={METODOS_PAGO_OPCIONES}
              activo={config.metodos_pago.activo}
              valor={config.metodos_pago.valor}
              onActivoChange={(v) => setActivo('metodos_pago', v)}
              onToggleItem={(item) => toggleArrayItem('metodos_pago', item)}
            />
            <CampoPoliticaPrecios
              campo="politica_precios"
              label="Política de precios y comprobantes"
              helpText="Política tributaria y de comprobantes."
              activo={config.politica_precios.activo}
              valor={config.politica_precios.valor}
              onActivoChange={(v) => setActivo('politica_precios', v)}
              onValorChange={(v) => setValor('politica_precios', v)}
            />
          </div>

          {/* Grupo 4 — Derivación a humano */}
          <div className="via-config-group">
            <h4 className="via-config-group-title">Derivación a humano</h4>
            <CampoAsesorHumano
              campo="asesor_humano"
              label="Asesor humano"
              helpText="Datos del asesor humano al que el agente deriva cuando no puede resolver algo."
              activo={config.asesor_humano.activo}
              valor={config.asesor_humano.valor}
              onActivoChange={(v) => setActivo('asesor_humano', v)}
              onValorChange={(v) => setValor('asesor_humano', v)}
            />
            <CampoMultiCheck
              campo="criterios_derivacion"
              label="Criterios de derivación"
              helpText="Situaciones en las que el agente debe derivar al humano."
              opciones={CRITERIOS_DERIVACION_OPCIONES}
              activo={config.criterios_derivacion.activo}
              valor={config.criterios_derivacion.valor}
              onActivoChange={(v) => setActivo('criterios_derivacion', v)}
              onToggleItem={(item) => toggleArrayItem('criterios_derivacion', item)}
            />
            <CampoRadio
              campo="horario_ia"
              label="Horario de la IA"
              helpText="Cuándo el agente responde automáticamente."
              opciones={HORARIO_IA_OPCIONES}
              activo={config.horario_ia.activo}
              valor={config.horario_ia.valor}
              onActivoChange={(v) => setActivo('horario_ia', v)}
              onValorChange={(v) => setValor('horario_ia', v)}
            />
          </div>

          {/* Grupo 5 — Información adicional */}
          <div className="via-config-group">
            <h4 className="via-config-group-title">Información adicional</h4>
            <InfoAdicionalEditor
              activo={config.info_adicional.activo}
              valor={config.info_adicional.valor}
              onActivoChange={(v) => setActivo('info_adicional', v)}
              onValorChange={(v) => setValor('info_adicional', v)}
            />
          </div>

          <div className="via-config-actions">
            <button
              type="button"
              className="via-btn-primary"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? (
                <><Loader2 size={14} className="ce-spin" /> Guardando...</>
              ) : (
                <>Guardar configuración</>
              )}
            </button>
            {savedHint && (
              <span className="via-saved-hint">
                <Check size={14} /> Guardado
              </span>
            )}
            {saveError && (
              <span className="via-save-error">
                <AlertCircle size={14} /> {saveError}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function ConfiguracionSection() {
  return (
    <>
      <SectionHeader
        title="Configuración"
        subtitle="Conectá tu WhatsApp y configurá el contexto que tendrá el agente IA al responder a tus clientes."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <SectionErrorBoundary>
          <CanalesBlock />
        </SectionErrorBoundary>

        <SectionErrorBoundary>
          <ContextoAgenteBlock />
        </SectionErrorBoundary>
      </div>
    </>
  );
}
