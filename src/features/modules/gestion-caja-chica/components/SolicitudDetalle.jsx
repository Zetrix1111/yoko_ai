import { useEffect, useState } from 'react';
import { X, Loader2, AlertCircle } from 'lucide-react';
import useSolicitud from '../hooks/useSolicitud';
import useAutoSaveItems from '../hooks/useAutoSaveItems';
import ItemsTable from './ItemsTable';

/**
 * Vista de detalle de una solicitud con tabla editable de ítems.
 *
 * El modal hace fetch del detalle, mantiene los `items` en estado local,
 * y delega la persistencia a useAutoSaveItems (debounce 1s).
 *
 * Estados editables: PENDIENTE_*. Si está en otro estado (PAGADA, RENDIDA),
 * la tabla queda read-only.
 *
 * El total se muestra recalculado client-side sumando los `total` de cada
 * ítem — coincide con lo que va a quedar en Airtable tras el próximo save.
 */
function formatPEN(n) {
  const num = Number(n) || 0;
  return `S/ ${num.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function toNumber(v) {
  if (v === null || v === undefined || v === '') return 0;
  if (typeof v === 'number') return v;
  const cleaned = String(v).replace(/[^0-9.\-,]/g, '').replace(/,/g, '');
  const n = parseFloat(cleaned);
  return isNaN(n) ? 0 : n;
}

export default function SolicitudDetalle({ solicitudId, onClose }) {
  const { solicitud, loading, error, refetch } = useSolicitud(solicitudId);
  const [items, setItems] = useState([]);
  const [saveState, setSaveState] = useState('idle'); // idle | saving | saved | error

  // Hidratamos el estado local cuando llega el fetch.
  useEffect(() => {
    if (solicitud?.items) {
      setItems(solicitud.items);
    }
  }, [solicitud]);

  const editable = !!solicitud?.editable;

  useAutoSaveItems(solicitudId, items, {
    enabled: editable,
    onSaved: () => {
      setSaveState('saved');
      setTimeout(() => setSaveState((s) => (s === 'saved' ? 'idle' : s)), 1500);
    },
    onError: () => setSaveState('error'),
  });

  // Marcamos "saving" en cuanto cambia items (después del primer render).
  useEffect(() => {
    if (!editable) return;
    if (!solicitud) return;
    setSaveState('saving');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  const handleChange = (idx, key, value) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [key]: value } : it)));
  };

  const handleAdd = () => {
    setItems((prev) => [
      ...prev,
      { descripcion: '', unidad: 'UND', cantidad: '1', precio_unitario: '', total: '', proveedor: '' },
    ]);
  };

  const handleDelete = (idx) => {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const totalCalculado = items.reduce((acc, it) => acc + toNumber(it.total), 0);

  return (
    <div className="gcc-modal-overlay" onClick={onClose}>
      <div
        className="gcc-modal"
        style={{ maxWidth: '900px', width: '95vw' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="gcc-modal-header">
          <h2 className="gcc-modal-title">
            {solicitud?.numero ? `Solicitud ${solicitud.numero}` : 'Solicitud'}
          </h2>
          <button className="gcc-modal-close" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>

        {loading && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--md-on-surface-variant)' }}>
            <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
            <div>Cargando…</div>
          </div>
        )}

        {error && !loading && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--md-on-error-container)' }}>
            <AlertCircle size={20} />
            <div>{error}</div>
            <button className="gcc-btn gcc-btn-ghost" onClick={refetch} style={{ marginTop: '0.5rem' }}>
              Reintentar
            </button>
          </div>
        )}

        {solicitud && !loading && !error && (
          <>
            <div style={{ padding: '0 1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
              <Field label="Solicitante" value={solicitud.nombre} />
              <Field label="Tipo" value={solicitud.tipo} />
              <Field label="Estado" value={solicitud.estado} />
              <Field label="Moneda" value={solicitud.moneda} />
              <Field label="Plazo" value={solicitud.plazo} />
              <Field label="Centro de costo" value={solicitud.centro_costo || '—'} />
            </div>

            <div style={{ padding: '0 1rem', marginTop: '0.75rem' }}>
              <Field label="Motivo" value={solicitud.motivo} multiline />
            </div>

            <div style={{ padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0, fontSize: '0.95rem' }}>Ítems</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--md-on-surface-variant)' }}>
                  {editable
                    ? 'Edición en vivo · ' + ({
                        idle:   '',
                        saving: 'Guardando…',
                        saved:  '✓ Guardado',
                        error:  '⚠ Error al guardar',
                      }[saveState] || '')
                    : 'Solo lectura (estado no permite edición)'}
                </span>
              </div>

              <ItemsTable
                items={items}
                onChange={handleChange}
                onAdd={handleAdd}
                onDelete={handleDelete}
                editable={editable}
              />

              <div style={{ marginTop: '0.75rem', textAlign: 'right', fontSize: '0.95rem', fontWeight: 600 }}>
                Total: {formatPEN(totalCalculado)}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, multiline }) {
  return (
    <div>
      <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--md-on-surface-variant)' }}>
        {label}
      </div>
      <div style={{ fontSize: '0.9rem', fontWeight: 500, whiteSpace: multiline ? 'pre-wrap' : 'normal' }}>
        {value || '—'}
      </div>
    </div>
  );
}
