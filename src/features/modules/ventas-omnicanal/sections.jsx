import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Plus, Sparkles, Users, MessageCircle, ShoppingBag, ArrowUpRight,
  Zap, BellRing, Pencil, Trash2, Check,
  TrendingUp, Activity, Search, Brain,
} from 'lucide-react';
import {
  STATS, ACTIVIDAD, CANALES, FLUJO_IA, PRODUCTOS,
  PIPELINE_ETAPAS, PIPELINE_CLIENTES, AUTOMATIZACIONES, TRAINING,
  CLIENTES, NOTIFICACIONES, CANAL_LABELS, ESTADO_LABELS,
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
// 0 · DASHBOARD
// ─────────────────────────────────────

const STAT_CARDS = [
  { key: 'totalLeads',           label: 'Total leads',          Icon: Users,          variant: 'primary',  trend: '+18% vs mes anterior',  trendVariant: 'success', format: 'num' },
  { key: 'conversacionesActivas',label: 'Conversaciones activas', Icon: MessageCircle,variant: 'tertiary', trend: '45 en tiempo real',     trendVariant: '',        format: 'num' },
  { key: 'ventasCerradas',       label: 'Ventas cerradas',      Icon: ShoppingBag,    variant: 'success',  trend: 'S/ 5,200 hoy',          trendVariant: 'success', format: 'pen' },
  { key: 'clientesCalientes',    label: 'Clientes calientes',   Icon: Sparkles,       variant: 'warning',  trend: 'Listos para comprar',    trendVariant: 'warning', format: 'num' },
];

export function InicioSection() {
  const [, setSearchParams] = useSearchParams();
  const [iaActiva, setIaActiva] = useState(true);

  const goTo = (section, params = {}) => setSearchParams({ section, ...params });

  return (
    <>
      <SectionHeader
        title="Dashboard"
        subtitle="Controla, automatiza y aumenta tus ventas desde todos tus canales digitales."
        action={
          <button className="vom-btn vom-btn-primary" onClick={() => goTo('crm', { new: '1' })}>
            <Plus size={16} /> Nuevo lead
          </button>
        }
      />

      {/* CTA destacado: Activar IA de ventas */}
      <div className="vom-cta-banner">
        <div className="vom-cta-icon">
          <Sparkles size={22} />
        </div>
        <div className="vom-cta-text">
          <h3>{iaActiva ? 'IA de ventas activa' : 'Activar IA de ventas'}</h3>
          <p>
            {iaActiva
              ? 'Tu IA está respondiendo automáticamente en todos los canales conectados.'
              : 'Deja que la IA califique leads, responda dudas y cierre ventas mientras tu equipo se enfoca en lo importante.'}
          </p>
        </div>
        <button
          className={`vom-btn ${iaActiva ? 'vom-btn-ghost' : 'vom-btn-primary'}`}
          onClick={() => setIaActiva((v) => !v)}
        >
          {iaActiva ? 'Desactivar' : (<><Sparkles size={16} /> Activar IA</>)}
        </button>
      </div>

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

      <div className="vom-card">
        <div className="vom-card-header">
          <h3 className="vom-card-title">Actividad reciente</h3>
          <button className="vom-link" onClick={() => goTo('crm')}>Ver todo →</button>
        </div>
        <div className="vom-activity">
          {ACTIVIDAD.slice(0, 6).map((a) => {
            const { Icon, variant } = activityIconFor(a.estado);
            return (
              <button key={a.id} type="button" className="vom-activity-row" onClick={() => goTo('crm')}>
                <div className={`vom-activity-icon ${variant}`}>
                  <Icon size={16} />
                </div>
                <div className="vom-activity-text">
                  <div className="vom-activity-title">{a.cliente} — {a.asunto}</div>
                  <div className="vom-activity-meta">
                    {CANAL_LABELS[a.canal]} · {formatDate(a.fecha)}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexShrink: 0 }}>
                  <Badge value={a.estado} />
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
// 1 · CANALES
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
        title="Canales integrados"
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
                {c.conectado ? 'Conectado' : 'Desconectado'}
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
// 2 · FLUJO DE VENTAS (IA)
// ─────────────────────────────────────

export function FlujoSection() {
  const [pasos, setPasos] = useState(FLUJO_IA);
  const togglePaso = (id) => {
    setPasos(pasos.map((p) => p.id === id ? { ...p, activo: !p.activo } : p));
  };
  const activos = pasos.filter((p) => p.activo).length;

  return (
    <>
      <SectionHeader
        title="Flujo de ventas con IA"
        subtitle={`${activos} de ${pasos.length} pasos activos en el flujo automático`}
        action={
          <button className="vom-btn vom-btn-ghost">
            <Pencil size={14} /> Editar flujo
          </button>
        }
      />

      <div className="vom-card">
        <div className="vom-flow-list">
          {pasos.map((p, idx) => (
            <div key={p.id} className="vom-flow-step">
              <div className="vom-flow-num">{idx + 1}</div>
              <div className="vom-flow-info">
                <div className="vom-flow-title">{p.titulo}</div>
                <div className="vom-flow-desc">{p.descripcion}</div>
              </div>
              <Toggle checked={p.activo} onChange={() => togglePaso(p.id)} ariaLabel={p.titulo} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 3 · CATÁLOGO
// ─────────────────────────────────────

export function CatalogoSection() {
  const [productos] = useState(PRODUCTOS);

  return (
    <>
      <SectionHeader
        title="Catálogo de productos"
        subtitle={`${productos.length} productos disponibles para venta automática vía IA`}
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
              <div>
                <div className="vom-product-price">{formatPEN(p.precio)}</div>
                <div className="vom-product-stock">
                  {p.stock === null ? 'Servicio' : `Stock: ${p.stock}`}
                </div>
              </div>
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
// 4 · EMBUDO (PIPELINE)
// ─────────────────────────────────────

export function PipelineSection() {
  const [clientes] = useState(PIPELINE_CLIENTES);

  return (
    <>
      <SectionHeader
        title="Embudo de ventas"
        subtitle="Mueve los leads entre etapas según avancen en el proceso de venta."
      />

      <div className="vom-pipeline">
        {PIPELINE_ETAPAS.map((etapa) => {
          const items = clientes.filter((c) => c.etapa === etapa.id);
          const total = items.reduce((sum, c) => sum + c.monto, 0);
          return (
            <div key={etapa.id} className="vom-pipeline-col">
              <div className="vom-pipeline-col-header">
                <span className="vom-pipeline-col-title">{etapa.label}</span>
                <span className="vom-pipeline-col-count">{items.length}</span>
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--md-on-surface-variant)', marginBottom: '0.25rem' }}>
                {formatPEN(total)}
              </div>
              {items.map((c) => (
                <div key={c.id} className="vom-pipeline-card">
                  <div className="vom-pipeline-card-name">{c.nombre}</div>
                  <div className="vom-pipeline-card-meta">
                    <ChannelBadge value={c.canal} />
                    <span className="vom-pipeline-card-monto">{formatPEN(c.monto)}</span>
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 5 · AUTOMATIZACIONES
// ─────────────────────────────────────

export function AutomatizacionesSection() {
  const [autos, setAutos] = useState(AUTOMATIZACIONES);
  const toggle = (id) => setAutos(autos.map((a) => a.id === id ? { ...a, activa: !a.activa } : a));
  const activas = autos.filter((a) => a.activa).length;

  return (
    <>
      <SectionHeader
        title="Automatizaciones"
        subtitle={`${activas} de ${autos.length} reglas activas. La IA ejecuta estas acciones sin intervención humana.`}
        action={
          <button className="vom-btn vom-btn-primary">
            <Plus size={16} /> Nueva automatización
          </button>
        }
      />

      <div className="vom-card">
        <div className="vom-flow-list">
          {autos.map((a) => (
            <div key={a.id} className="vom-flow-step">
              <div className="vom-flow-num"><Zap size={14} /></div>
              <div className="vom-flow-info">
                <div className="vom-flow-title">{a.nombre}</div>
                <div className="vom-flow-desc">{a.descripcion}</div>
              </div>
              <Toggle checked={a.activa} onChange={() => toggle(a.id)} ariaLabel={a.nombre} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 6 · RESPUESTAS INTELIGENTES (Training)
// ─────────────────────────────────────

export function TrainingSection() {
  return (
    <>
      <SectionHeader
        title="Respuestas inteligentes"
        subtitle="Entrena a la IA con tu conocimiento de negocio: FAQs, objeciones, scripts y tono."
        action={
          <button className="vom-btn vom-btn-ghost">
            <Brain size={14} /> Editar conocimiento
          </button>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.85rem' }}>
        {TRAINING.map((t) => (
          <div key={t.id} className="vom-card">
            <div className="vom-stat-top">
              <span className="vom-stat-label">{t.titulo}</span>
              <div className="vom-stat-icon-wrap primary">
                <Brain size={16} />
              </div>
            </div>
            <div className="vom-stat-value" style={{ fontSize: '1.5rem' }}>{t.items}</div>
            <div className="vom-stat-trend">Última edición: {formatDate(t.ultimaEdicion)}</div>
          </div>
        ))}
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 7 · CRM (Clientes)
// ─────────────────────────────────────

export function CrmSection() {
  const [clientes] = useState(CLIENTES);
  const [filter, setFilter] = useState('');

  const filtered = clientes.filter((c) =>
    !filter || c.nombre.toLowerCase().includes(filter.toLowerCase()) ||
    c.email.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <>
      <SectionHeader
        title="Clientes (CRM)"
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
              <th>ID</th>
              <th>Cliente</th>
              <th>Email</th>
              <th>Canal</th>
              <th>Estado</th>
              <th>Última interacción</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan="6"><div className="vom-table-empty">Sin resultados</div></td></tr>
            ) : filtered.map((c) => (
              <tr key={c.id}>
                <td style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--md-on-surface-variant)' }}>{c.id}</td>
                <td style={{ fontWeight: 500 }}>{c.nombre}</td>
                <td style={{ fontSize: '0.82rem', color: 'var(--md-on-surface-variant)' }}>{c.email}</td>
                <td><ChannelBadge value={c.canal} /></td>
                <td><Badge value={c.estado} /></td>
                <td>{formatDate(c.ultimaInteraccion)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 8 · NOTIFICACIONES
// ─────────────────────────────────────

const NOTIF_ICONS = {
  lead:     { Icon: BellRing,   variant: 'lead' },
  caliente: { Icon: Sparkles,   variant: 'caliente' },
  venta:    { Icon: ShoppingBag,variant: 'venta' },
};

export function NotificacionesSection() {
  return (
    <>
      <SectionHeader
        title="Notificaciones"
        subtitle="Avisos en tiempo real de los eventos importantes en tus canales."
      />

      <div className="vom-card">
        <div className="vom-notif-list">
          {NOTIFICACIONES.map((n) => {
            const { Icon, variant } = NOTIF_ICONS[n.tipo] || NOTIF_ICONS.lead;
            return (
              <div key={n.id} className="vom-notif-row">
                <div className={`vom-notif-icon ${variant}`}>
                  <Icon size={16} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p className="vom-notif-msg">{n.mensaje}</p>
                  <div className="vom-notif-fecha">{n.fecha}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────
// 9 · CONFIGURACIÓN
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
  const [personalizacion, setPersonalizacion] = useState(false);

  return (
    <>
      <SectionHeader
        title="Configuración"
        subtitle="Integraciones, claves de API y personalización del comportamiento de la IA."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <ConfigCard
          title="Integraciones de mensajería"
          description="Conecta WhatsApp, Messenger, Instagram y otros canales a través de Meta Business y API oficiales."
          summary={integraciones ? 'Conectado' : 'Sin conectar'}
          enabled={integraciones}
          onToggle={setIntegraciones}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            Última sincronización: hace 5 minutos · 4 canales activos
          </div>
        </ConfigCard>

        <ConfigCard
          title="Webhooks (Make / n8n)"
          description="Dispara automatizaciones externas cuando ocurre un evento en el módulo (lead nuevo, venta cerrada, etc.)."
          summary={webhooks ? '3 endpoints activos' : 'Sin endpoints'}
          enabled={webhooks}
          onToggle={setWebhooks}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            Endpoints: lead.created · sale.closed · message.escalated
          </div>
        </ConfigCard>

        <ConfigCard
          title="Personalización de la IA"
          description="Define el tono, vocabulario y reglas de negocio que tu IA usará al responder a los clientes."
          summary={personalizacion ? 'Personalizada' : 'Default'}
          enabled={personalizacion}
          onToggle={setPersonalizacion}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            Tono actual: profesional cálido · Idioma: español peruano
          </div>
        </ConfigCard>

        <ConfigCard
          title="API keys"
          description="Genera o revoca claves para integrar terceros con el módulo de Ventas Omnicanal."
          summary="2 keys activas"
          enabled={true}
          onToggle={() => {}}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--md-on-surface-variant)' }}>
            sk_live_••••••3F4A · sk_test_••••••B921
          </div>
        </ConfigCard>
      </div>
    </>
  );
}
