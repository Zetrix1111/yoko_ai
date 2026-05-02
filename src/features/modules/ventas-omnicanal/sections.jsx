import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Plus, Sparkles, Users, MessageCircle, ShoppingBag, ArrowUpRight,
  Pencil, Trash2, Check, TrendingUp, Activity, Search,
} from 'lucide-react';
import {
  STATS, FUNNEL, ACTIVIDAD, CANALES, PRODUCTOS, CLIENTES,
  CANAL_LABELS, ESTADO_LABELS,
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
        const conversion = idx === 0
          ? null
          : Math.round((s.count / stages[idx - 1].count) * 100);
        return (
          <div key={s.id} className="vom-funnel-row">
            <div className="vom-funnel-label">
              <span className={`vom-funnel-dot ${s.variant}`} />
              {s.label}
            </div>
            <div className="vom-funnel-track">
              <div
                className={`vom-funnel-fill ${s.variant}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="vom-funnel-meta">
              <span className="vom-funnel-count">{formatNum(s.count)}</span>
              {conversion !== null && (
                <span className="vom-funnel-conv">{conversion}% conv.</span>
              )}
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
        subtitle="Controla, automatiza y aumenta tus ventas desde todos tus canales."
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
              ? 'Tu IA está respondiendo automáticamente y calificando leads en todos los canales.'
              : 'Activa la IA y deja que responda, califique y cierre ventas mientras trabajas en lo importante.'}
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

      {/* Mini embudo + Actividad reciente lado a lado en desktop */}
      <div className="vom-dashboard-row">
        <div className="vom-card">
          <div className="vom-card-header">
            <h3 className="vom-card-title">Embudo de ventas</h3>
            <span style={{ fontSize: '0.78rem', color: 'var(--md-on-surface-variant)' }}>
              Mes actual
            </span>
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
                    <div className="vom-activity-meta">
                      {a.asunto} · {CANAL_LABELS[a.canal]}
                    </div>
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
// 2 · CANALES
// ─────────────────────────────────────

export function CanalesSection() {
  const [canales, setCanales] = useState(CANALES);
  const toggleCanal = (id) => {
    setCanales(canales.map((c) => c.id === id ? { ...c, conectado: !c.conectado } : c));
  };
  const conectados = canales.filter((c) => c.conectado).length;

  return (
    <>
      <SectionHeader
        title="Canales"
        subtitle={`${conectados} de ${canales.length} canales activos · todos los mensajes en una sola bandeja`}
        action={
          <button className="vom-btn vom-btn-primary">
            <Plus size={16} /> Conectar canal
          </button>
        }
      />

      <div className="vom-card">
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
    </>
  );
}

// ─────────────────────────────────────
// 3 · CLIENTES
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
// 4 · CATÁLOGO
// ─────────────────────────────────────

export function CatalogoSection() {
  const [productos] = useState(PRODUCTOS);

  return (
    <>
      <SectionHeader
        title="Catálogo"
        subtitle={`${productos.length} productos y servicios disponibles para venta automática`}
        action={
          <button className="vom-btn vom-btn-primary">
            <Plus size={16} /> Agregar producto
          </button>
        }
      />

      <div className="vom-product-grid">
        {productos.map((p) => (
          <div key={p.id} className="vom-product-card">
            <div className="vom-product-name">{p.nombre}</div>
            <div className="vom-product-desc">{p.descripcion}</div>
            <div className="vom-product-row">
              <div className="vom-product-price">{formatPEN(p.precio)}</div>
              <div className="vom-product-actions">
                <button className="vom-icon-btn" title="Editar">
                  <Pencil size={14} />
                </button>
                <button className="vom-icon-btn danger" title="Eliminar">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 5 · CONFIGURACIÓN
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

export function ConfiguracionSection() {
  const [integraciones, setIntegraciones] = useState(true);
  const [webhooks, setWebhooks] = useState(true);
  const [ajustes, setAjustes] = useState(false);

  return (
    <>
      <SectionHeader
        title="Configuración"
        subtitle="Conecta tus canales, dispara automatizaciones externas y personaliza el comportamiento."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <ConfigCard
          title="Integraciones"
          description="Conecta WhatsApp, Facebook, Instagram y LinkedIn a través de las API oficiales de Meta."
          summary={integraciones ? 'Conectado' : 'Sin conectar'}
          enabled={integraciones}
          onToggle={setIntegraciones}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            Última sincronización: hace 5 minutos · 3 de 4 canales activos
          </div>
        </ConfigCard>

        <ConfigCard
          title="Webhooks"
          description="Dispara automatizaciones externas (Make, n8n, Zapier) cuando ocurre un evento: lead nuevo, venta cerrada, mensaje escalado."
          summary={webhooks ? '3 endpoints activos' : 'Sin endpoints'}
          enabled={webhooks}
          onToggle={setWebhooks}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            lead.created · sale.closed · message.escalated
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
