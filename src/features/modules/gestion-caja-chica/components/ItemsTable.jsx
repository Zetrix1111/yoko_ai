import { Trash2, Plus } from 'lucide-react';

/**
 * Tabla editable de ítems de una solicitud de caja chica.
 *
 * Columnas: Descripción, Unidad, Cantidad, P. unit, Total, Proveedor.
 *
 * Diseño:
 *   - `items` es el array controlado por el padre (SolicitudDetalle).
 *   - Cada cambio dispara `onChange(idx, key, value)` para que el padre
 *     actualice su estado; el padre tiene useAutoSaveItems que debouncea
 *     y persiste.
 *   - `editable=false` deshabilita todos los inputs y botones (estados no
 *     PENDIENTE_*).
 *   - El `total` por fila NO se recalcula client-side al cambiar cantidad
 *     o precio_unitario — eso lo hace el backend (suma final del array
 *     determina TOTAL_GENERAL). El usuario edita los valores libremente.
 *
 * Patrón inspirado en `features/modules/facturas-inteligentes/components/FacturasTable.jsx`.
 */
export default function ItemsTable({ items, onChange, onAdd, onDelete, editable }) {
  const cols = [
    { key: 'descripcion',     label: 'Descripción',  align: 'left',  width: '28%' },
    { key: 'unidad',          label: 'Unidad',       align: 'left',  width: '10%' },
    { key: 'cantidad',        label: 'Cantidad',     align: 'right', width: '10%' },
    { key: 'precio_unitario', label: 'P. unit',      align: 'right', width: '12%' },
    { key: 'total',           label: 'Total',        align: 'right', width: '12%' },
    { key: 'proveedor',       label: 'Proveedor',    align: 'left',  width: '22%' },
  ];

  return (
    <div className="gcc-table-wrap">
      <table className="gcc-table">
        <thead>
          <tr>
            {cols.map((c) => (
              <th
                key={c.key}
                style={{ width: c.width, textAlign: c.align }}
                className={c.align === 'right' ? 'num' : ''}
              >
                {c.label}
              </th>
            ))}
            <th style={{ width: '40px' }} aria-label="Acciones" />
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={cols.length + 1} style={{ textAlign: 'center', color: 'var(--md-on-surface-variant)', padding: '1.5rem' }}>
                Sin ítems. {editable && 'Click "Agregar ítem" para empezar.'}
              </td>
            </tr>
          ) : (
            items.map((item, idx) => (
              <tr key={idx}>
                {cols.map((c) => (
                  <td key={c.key} className={c.align === 'right' ? 'num' : ''}>
                    <input
                      className="gcc-input"
                      style={{
                        width: '100%',
                        border: 'none',
                        background: 'transparent',
                        padding: '0.25rem',
                        textAlign: c.align,
                        fontSize: '0.85rem',
                      }}
                      value={item[c.key] ?? ''}
                      onChange={(e) => onChange(idx, c.key, e.target.value)}
                      disabled={!editable}
                    />
                  </td>
                ))}
                <td>
                  {editable && (
                    <button
                      type="button"
                      className="gcc-btn gcc-btn-ghost"
                      style={{ padding: '0.25rem', minWidth: 'auto' }}
                      onClick={() => onDelete(idx)}
                      aria-label="Eliminar ítem"
                      title="Eliminar ítem"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {editable && (
        <div style={{ padding: '0.5rem', textAlign: 'left' }}>
          <button
            type="button"
            className="gcc-btn gcc-btn-ghost"
            onClick={onAdd}
          >
            <Plus size={14} /> Agregar ítem
          </button>
        </div>
      )}
    </div>
  );
}
