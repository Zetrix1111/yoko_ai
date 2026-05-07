import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { apiFetch } from '../../../../shared/api';
import TableRow from './TableRow';
import useAutoSave from '../hooks/useAutoSave';
import './FacturasTable.css';

/**
 * Tabla editable de facturas con 13 columnas.
 *
 * Features:
 * - Edición inline de todas las celdas
 * - Auto-save con debounce de 1s (useAutoSave)
 * - Eliminación de filas individuales
 * - Indicador visual de confianza (verde/amarillo/rojo) por fila
 * - Scroll horizontal en pantallas chicas
 */
export default function FacturasTable({ proceso, facturas, setFacturas }) {
  const [editingCell, setEditingCell] = useState(null); // { rowId, field }

  // Auto-save: cada cambio en `facturas` dispara un PUT debounced (1s).
  useAutoSave(proceso?.proceso_id, facturas);

  const handleCellChange = (facturaId, field, newValue) => {
    setFacturas((prev) =>
      prev.map((f) => (f.id === facturaId ? { ...f, [field]: newValue } : f))
    );
  };

  const handleDeleteRow = async (facturaId) => {
    if (!window.confirm('¿Eliminar esta factura?')) return;

    try {
      await apiFetch('/api/facturas?action=eliminar-fila', {
        method: 'DELETE',
        body: {
          proceso_id: proceso.proceso_id,
          factura_id: facturaId,
        },
      });
      setFacturas((prev) => prev.filter((f) => f.id !== facturaId));
    } catch (err) {
      console.error('[FacturasTable] error eliminando fila:', err);
      window.alert('No se pudo eliminar la factura. Intentá de nuevo.');
    }
  };

  const getConfidenceClass = (confianza) => {
    if (confianza >= 0.9) return 'confidence-high';
    if (confianza >= 0.7) return 'confidence-medium';
    return 'confidence-low';
  };

  if (!facturas || facturas.length === 0) {
    return (
      <div className="facturas-table-empty">
        <AlertCircle size={48} />
        <p>No hay facturas para mostrar</p>
      </div>
    );
  }

  return (
    <div className="facturas-table-container">
      <div className="facturas-table-wrapper">
        <table className="facturas-table">
          <thead>
            <tr>
              <th className="col-fecha">Fecha emisión</th>
              <th className="col-tipo">Tipo doc</th>
              <th className="col-serie">Serie</th>
              <th className="col-numero">Número</th>
              <th className="col-ruc">RUC</th>
              <th className="col-proveedor">Proveedor</th>
              <th className="col-concepto">Concepto</th>
              <th className="col-moneda">Moneda</th>
              <th className="col-monto">Monto inc. IGV</th>
              <th className="col-tributo">Monto tributo</th>
              <th className="col-obra">Obra / área</th>
              <th className="col-estado">Estado</th>
              <th className="col-actions" aria-label="Acciones" />
            </tr>
          </thead>
          <tbody>
            {facturas.map((factura, idx) => (
              <TableRow
                key={factura.id}
                factura={factura}
                index={idx}
                confidenceClass={getConfidenceClass(factura.confianza)}
                editingCell={editingCell}
                setEditingCell={setEditingCell}
                onChange={handleCellChange}
                onDelete={handleDeleteRow}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="facturas-table-footer">
        <span className="facturas-count">
          {facturas.length} factura{facturas.length !== 1 ? 's' : ''}
        </span>
        <span className="facturas-autosave">
          Cambios guardados automáticamente
        </span>
      </div>
    </div>
  );
}
