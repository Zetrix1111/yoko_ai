import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Inbox, MessageSquarePlus, ArrowRight } from 'lucide-react';
import useProcesos from '../hooks/useProcesos';
import '../fi-sections.css';

/**
 * Sección "Procesos" del módulo Facturas Inteligentes.
 *
 * Bandeja operativa con todos los lotes procesados por la IA. El
 * listado viene de `GET /api/facturas?action=listar-procesos`
 * (filtrado por empresa_id del JWT).
 *
 * Filtros (pills arriba): client-side sobre el array.
 * Acciones por fila: "Abrir" navega a `?section=revision&proceso_id=X`;
 * el resto son maqueta.
 *
 * Limitación: el backend lee SQLite efímera (/tmp, TTL 24h). Los
 * procesos viejos no aparecen.
 */

const FILTROS = [
  { id: 'todos',       label: 'Todos' },
  { id: 'pendientes',  label: 'Pendientes' },
  { id: 'revisados',   label: 'Revisados' },
  { id: 'errores',     label: 'Con errores' },
  { id: 'compras',     label: 'Compras' },
  { id: 'ventas',      label: 'Ventas' },
];

function formatTipo(tipo) {
  if (!tipo) return '—';
  const t = String(tipo).toLowerCase();
  if (t === 'compra' || t === 'compras') return 'Compras';
  if (t === 'venta' || t === 'ventas') return 'Ventas';
  return tipo;
}

function formatMes(mes) {
  if (!mes) return '—';
  // Aceptamos "YYYY-MM" o ya formateado. Mostramos como "Mayo 2026".
  const m = String(mes).match(/^(\d{4})-(\d{2})$/);
  if (!m) return mes;
  const year = m[1];
  const meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','setiembre','octubre','noviembre','diciembre'];
  const idx = parseInt(m[2], 10) - 1;
  const nombre = meses[idx] || m[2];
  return `${nombre.charAt(0).toUpperCase()}${nombre.slice(1)} ${year}`;
}

function formatRelative(ts) {
  if (!ts) return '—';
  const seconds = Math.floor(Date.now() / 1000 - ts);
  if (seconds < 60) return 'hace instantes';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  return `hace ${days} d`;
}

function badgeClass(estado) {
  switch (estado) {
    case 'Revisado':           return 'fi-badge fi-badge-success';
    case 'Pendiente revisión': return 'fi-badge fi-badge-warning';
    case 'Con errores':        return 'fi-badge fi-badge-error';
    case 'Exportado':          return 'fi-badge fi-badge-info';
    case 'Procesando':         return 'fi-badge fi-badge-neutral';
    default:                   return 'fi-badge fi-badge-neutral';
  }
}

function focusChatInput() {
  const el = document.querySelector('.chat-input');
  if (el) el.focus();
}

export default function ProcesosSection() {
  const navigate = useNavigate();
  const { procesos, loading, error, refetch } = useProcesos();
  const [filtro, setFiltro] = useState('todos');

  const filtrados = useMemo(() => {
    return procesos.filter((p) => {
      if (filtro === 'todos') return true;
      if (filtro === 'pendientes') return p.estado_inferido === 'Pendiente revisión';
      if (filtro === 'revisados')  return p.estado_inferido === 'Revisado';
      if (filtro === 'errores')    return p.estado_inferido === 'Con errores';
      if (filtro === 'compras') {
        const t = String(p.tipo || '').toLowerCase();
        return t === 'compra' || t === 'compras';
      }
      if (filtro === 'ventas') {
        const t = String(p.tipo || '').toLowerCase();
        return t === 'venta' || t === 'ventas';
      }
      return true;
    });
  }, [procesos, filtro]);

  return (
    <div className="fi-section">
      <header className="fi-section-header">
        <div>
          <h1 className="fi-section-title">Procesos</h1>
          <p className="fi-section-subtitle">
            Lotes procesados por la IA. Abre un proceso para revisar o exportar.
            <span className="fi-section-hint"> · Retención 24 h</span>
          </p>
        </div>
        <button
          type="button"
          className="fi-btn fi-btn-primary"
          onClick={focusChatInput}
          title="Adjunta los comprobantes en el chat de Yoko"
        >
          <MessageSquarePlus size={16} />
          Procesar comprobantes
        </button>
      </header>

      <nav className="fi-filter-pills" aria-label="Filtrar procesos">
        {FILTROS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`fi-pill ${filtro === f.id ? 'is-active' : ''}`}
            onClick={() => setFiltro(f.id)}
          >
            {f.label}
          </button>
        ))}
      </nav>

      {error && (
        <div className="fi-alert fi-alert-error">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button className="fi-btn fi-btn-ghost" onClick={refetch}>Reintentar</button>
        </div>
      )}

      {!loading && filtrados.length === 0 ? (
        <div className="fi-empty">
          <Inbox size={32} />
          <h3>
            {procesos.length === 0
              ? 'Aún no hay procesos'
              : 'Sin resultados para este filtro'}
          </h3>
          {procesos.length === 0 && (
            <p>
              Adjunta tus comprobantes desde el chat de Yoko para procesar tu primer lote.
            </p>
          )}
          {procesos.length === 0 && (
            <button
              type="button"
              className="fi-btn fi-btn-primary"
              onClick={focusChatInput}
            >
              <MessageSquarePlus size={16} />
              Abrir chat
            </button>
          )}
        </div>
      ) : (
        <div className="fi-table-wrap">
          <table className="fi-table">
            <thead>
              <tr>
                <th>Proceso</th>
                <th>Tipo</th>
                <th>Mes contable</th>
                <th className="num">Comprobantes</th>
                <th>Estado</th>
                <th>Creado</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="fi-table-loading">Cargando procesos…</td>
                </tr>
              ) : (
                filtrados.map((p) => (
                  <tr
                    key={p.proceso_id}
                    className="fi-table-row-clickable"
                    onClick={() => navigate(`/modulos/facturas-inteligentes?section=revision&proceso_id=${encodeURIComponent(p.proceso_id)}`)}
                  >
                    <td className="fi-cell-mono">{p.proceso_id}</td>
                    <td>{formatTipo(p.tipo)}</td>
                    <td>{formatMes(p.mes)}</td>
                    <td className="num">{p.count}</td>
                    <td>
                      <span className={badgeClass(p.estado_inferido)}>
                        {p.estado_inferido || '—'}
                      </span>
                    </td>
                    <td>{formatRelative(p.first_created)}</td>
                    <td className="fi-cell-actions">
                      <button
                        type="button"
                        className="fi-btn fi-btn-link"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/modulos/facturas-inteligentes?section=revision&proceso_id=${encodeURIComponent(p.proceso_id)}`);
                        }}
                      >
                        Abrir <ArrowRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
