import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Plus, X, Sparkles, Users, MessageCircle, ShoppingBag, ArrowUpRight,
  Pencil, Trash2, Check, TrendingUp, Activity, Search, Package,
  Upload as UploadIcon, Image as ImageIcon,
} from 'lucide-react';
import {
  STATS, FUNNEL, ACTIVIDAD, CANALES, PRODUCTOS, CLIENTES,
  CANAL_LABELS, ESTADO_LABELS, STOCK_LABELS, getStockStatus,
  formatPEN, formatNum, formatDate,
} from './mockData';

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

function Toggle({ checked, onChange, ariaLabel }) {
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

function ProductoForm({ producto, onSubmit, onCancel }) {
  const editing = Boolean(producto?.id);
  const [foto, setFoto] = useState(producto?.foto || null);

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Mock: preview local. Cuando se integre con backend, subir y guardar URL.
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
    onSubmit({
      id:           producto?.id,
      nombre:       f.get('nombre'),
      precio:       Number(f.get('precio')),
      descripcion:  f.get('descripcion'),
      foto,
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

      <div className="vom-modal-actions">
        <button type="button" className="vom-btn vom-btn-ghost" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="vom-btn vom-btn-primary">
          {editing ? <><Check size={16} /> Guardar cambios</> : <><Plus size={16} /> Crear producto</>}
        </button>
      </div>
    </form>
  );
}

export function ProductosSection() {
  const [productos, setProductos] = useState(PRODUCTOS);
  const [editing, setEditing] = useState(null); // null | {} (nuevo) | producto (editar)

  const handleSave = (data) => {
    if (data.id) {
      setProductos(productos.map((p) => p.id === data.id ? { ...p, ...data } : p));
    } else {
      const nextId = Math.max(0, ...productos.map((p) => p.id)) + 1;
      setProductos([{ ...data, id: nextId }, ...productos]);
    }
    setEditing(null);
  };

  const handleDelete = (id) => {
    setProductos(productos.filter((p) => p.id !== id));
  };

  return (
    <>
      <SectionHeader
        title="Productos"
        subtitle={`${productos.length} productos y servicios disponibles para venta automática`}
        action={
          <button className="vom-btn vom-btn-primary" onClick={() => setEditing({})}>
            <Plus size={16} /> Agregar producto
          </button>
        }
      />

      <div className="vom-product-grid">
        {productos.map((p) => (
          <ProductoCard key={p.id} producto={p} onEdit={setEditing} onDelete={handleDelete} />
        ))}
      </div>

      {editing && (
        <Modal
          title={editing.id ? 'Editar producto' : 'Nuevo producto'}
          onClose={() => setEditing(null)}
        >
          <ProductoForm producto={editing} onSubmit={handleSave} onCancel={() => setEditing(null)} />
        </Modal>
      )}
    </>
  );
}

// ─────────────────────────────────────
// 4 · CONFIGURACIÓN (incluye Canales)
// ─────────────────────────────────────

function ConfigCard({ title, description, summary, enabled, onToggle, children }) {
  return (
    <div className={`vom-card vom-config-card ${enabled ? 'is-on' : ''}`}>
      <div className="vom-config-header">
        <div className="vom-config-title-block">
          <h3 className="vom-card-title">{title}</h3>
          {description && <p className="vom-config-description">{description}</p>}
        </div>
        <div className="vom-config-controls">
          {summary && <span className="vom-config-summary">{summary}</span>}
          <Toggle checked={enabled} onChange={onToggle} ariaLabel={title} />
        </div>
      </div>
      {enabled && children && <div className="vom-config-body">{children}</div>}
    </div>
  );
}

function CanalesBlock() {
  const [canales, setCanales] = useState(CANALES);
  const toggleCanal = (id) => {
    setCanales(canales.map((c) => c.id === id ? { ...c, conectado: !c.conectado } : c));
  };
  const conectados = canales.filter((c) => c.conectado).length;

  return (
    <div className="vom-card">
      <div className="vom-config-header">
        <div className="vom-config-title-block">
          <h3 className="vom-card-title">Canales</h3>
          <p className="vom-config-description">
            Conecta tus canales de mensajería para que la IA reciba y responda
            mensajes en una sola bandeja unificada.
          </p>
        </div>
        <div className="vom-config-controls">
          <span className="vom-config-summary">
            {conectados} de {canales.length} conectados
          </span>
          <button className="vom-btn vom-btn-ghost" style={{ padding: '0.45rem 0.85rem', fontSize: '0.82rem' }}>
            <Plus size={14} /> Conectar canal
          </button>
        </div>
      </div>

      <div className="vom-config-body" style={{ marginTop: '1.1rem', paddingTop: '1.1rem', borderTop: '1px solid #E2E8F0' }}>
        <div className="vom-channel-list">
          {canales.map((c) => (
            <div key={c.id} className={`vom-channel-row ${c.conectado ? 'connected' : 'disconnected'}`}>
              <div className="vom-channel-icon">
                <MessageCircle size={18} />
              </div>
              <div className="vom-channel-info">
                <div className="vom-channel-name">{c.nombre}</div>
                <div className="vom-channel-meta">
                  {c.numero} {c.conectado && `· ${c.mensajesHoy} mensajes hoy`}
                </div>
              </div>
              <span className={`vom-channel-status ${c.conectado ? 'connected' : 'disconnected'}`}>
                {c.conectado ? 'Conectado' : 'No conectado'}
              </span>
              <Toggle
                checked={c.conectado}
                onChange={() => toggleCanal(c.id)}
                ariaLabel={`Conectar ${c.nombre}`}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ConfiguracionSection() {
  const [webhooks, setWebhooks] = useState(true);
  const [integraciones, setIntegraciones] = useState(true);
  const [ajustes, setAjustes] = useState(false);

  return (
    <>
      <SectionHeader
        title="Configuración"
        subtitle="Conecta canales, dispara automatizaciones externas y personaliza el comportamiento de la IA."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* Canales como bloque destacado dentro de Configuración */}
        <CanalesBlock />

        <ConfigCard
          title="Webhooks"
          description="Dispara eventos hacia URLs externas: lead nuevo, venta cerrada, mensaje escalado a humano."
          summary={webhooks ? '3 endpoints activos' : 'Sin endpoints'}
          enabled={webhooks}
          onToggle={setWebhooks}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            lead.created · sale.closed · message.escalated
          </div>
        </ConfigCard>

        <ConfigCard
          title="Integraciones (Make)"
          description="Automatiza con Make, n8n o Zapier. Genera cotizaciones, registra ventas en CONCAR, notifica vendedores."
          summary={integraciones ? '2 escenarios activos' : 'Sin escenarios'}
          enabled={integraciones}
          onToggle={setIntegraciones}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            Cotización automática · Registro contable
          </div>
        </ConfigCard>

        <ConfigCard
          title="Ajustes generales"
          description="Tono, idioma y reglas de negocio que aplica la IA al responder a tus clientes."
          summary={ajustes ? 'Personalizado' : 'Default'}
          enabled={ajustes}
          onToggle={setAjustes}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            Tono: profesional cálido · Idioma: español peruano
          </div>
        </ConfigCard>
      </div>
    </>
  );
}
