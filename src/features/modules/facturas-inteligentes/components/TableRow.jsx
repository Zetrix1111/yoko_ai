import { useEffect, useRef } from 'react';
import { Trash2, AlertCircle } from 'lucide-react';
import DropdownObras from './DropdownObras';

const TIPO_DOC_OPTIONS = [
  { codigo: 'FT', nombre: 'Factura' },
  { codigo: 'BV', nombre: 'Boleta' },
  { codigo: 'NC', nombre: 'Nota de Crédito' },
  { codigo: 'ND', nombre: 'Nota de Débito' },
  { codigo: 'BA', nombre: 'Boleto Aéreo' },
  { codigo: 'RH', nombre: 'Recibo por Honorarios' },
  { codigo: 'TK', nombre: 'Ticket' },
];

const MONEDA_OPTIONS = ['PEN', 'USD', 'EUR', 'CNY'].map((m) => ({
  codigo: m,
  nombre: m,
}));

/**
 * Fila de tabla con 14 columnas editables.
 *
 * Columnas 1-11: datos de la factura (editables inline), incluyendo Tipo
 *   de cambio (campo SIRE #26, obligatorio si moneda ≠ PEN).
 * Columna 12: cuenta contable (input libre con default por template).
 * Columna 13: estado (read-only por ahora).
 * Columna 14: acciones (botón eliminar + warning de confianza baja).
 */
export default function TableRow({
  factura,
  confidenceClass,
  editingCell,
  setEditingCell,
  onChange,
  onDelete,
}) {
  const isEditing = (field) =>
    editingCell?.rowId === factura.id && editingCell?.field === field;

  const handleStartEdit = (field) => setEditingCell({ rowId: factura.id, field });
  const handleStopEdit = () => setEditingCell(null);
  const handleChange = (field, value) => onChange(factura.id, field, value);

  const showWarning = factura.confianza < 0.7;

  return (
    <tr className={`factura-row ${confidenceClass}`}>
      {/* Fecha Emisión */}
      <td className="col-fecha">
        <EditableCell
          value={factura.fecha_emision}
          type="text"
          isEditing={isEditing('fecha_emision')}
          onStartEdit={() => handleStartEdit('fecha_emision')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('fecha_emision', val)}
          placeholder="DD/MM/YYYY"
        />
      </td>

      {/* Tipo DOC */}
      <td className="col-tipo">
        <SelectCell
          value={factura.tipo_doc_codigo}
          options={TIPO_DOC_OPTIONS}
          onChange={(val) => {
            const option = TIPO_DOC_OPTIONS.find((o) => o.codigo === val);
            handleChange('tipo_doc_codigo', val);
            handleChange('tipo_doc_nombre', option?.nombre || val);
          }}
        />
      </td>

      {/* Serie */}
      <td className="col-serie">
        <EditableCell
          value={factura.serie}
          type="text"
          isEditing={isEditing('serie')}
          onStartEdit={() => handleStartEdit('serie')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('serie', val.toUpperCase())}
          placeholder="F001"
        />
      </td>

      {/* Número */}
      <td className="col-numero">
        <EditableCell
          value={factura.numero}
          type="text"
          isEditing={isEditing('numero')}
          onStartEdit={() => handleStartEdit('numero')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('numero', val)}
          placeholder="00012345"
        />
      </td>

      {/* RUC */}
      <td className="col-ruc">
        <EditableCell
          value={factura.ruc}
          type="text"
          isEditing={isEditing('ruc')}
          onStartEdit={() => handleStartEdit('ruc')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('ruc', val)}
          placeholder="20123456789"
          maxLength={11}
        />
      </td>

      {/* Proveedor */}
      <td className="col-proveedor">
        <EditableCell
          value={factura.proveedor}
          type="text"
          isEditing={isEditing('proveedor')}
          onStartEdit={() => handleStartEdit('proveedor')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('proveedor', val)}
          placeholder="Razón social"
        />
      </td>

      {/* Concepto */}
      <td className="col-concepto">
        <EditableCell
          value={factura.concepto}
          type="text"
          isEditing={isEditing('concepto')}
          onStartEdit={() => handleStartEdit('concepto')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('concepto', val)}
          placeholder="Descripción"
        />
      </td>

      {/* Moneda */}
      <td className="col-moneda">
        <SelectCell
          value={factura.moneda}
          options={MONEDA_OPTIONS}
          onChange={(val) => handleChange('moneda', val)}
        />
      </td>

      {/* Tipo de cambio — solo relevante si moneda ≠ PEN. Obligatorio en
          SIRE para monedas extranjeras (campo 26 de la estructura 8.4). */}
      <td className="col-tipo-cambio">
        <EditableCell
          value={factura.tipo_cambio}
          type="text"
          isEditing={isEditing('tipo_cambio')}
          onStartEdit={() => handleStartEdit('tipo_cambio')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('tipo_cambio', val)}
          placeholder={factura.moneda === 'PEN' ? '—' : 'Ej: 3.755'}
        />
      </td>

      {/* Monto Total */}
      <td className="col-monto">
        <EditableCell
          value={factura.monto_total}
          type="number"
          isEditing={isEditing('monto_total')}
          onStartEdit={() => handleStartEdit('monto_total')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('monto_total', parseFloat(val) || 0)}
          placeholder="0.00"
          step="0.01"
        />
      </td>

      {/* Monto Tributo */}
      <td className="col-tributo">
        <EditableCell
          value={factura.monto_tributo}
          type="number"
          isEditing={isEditing('monto_tributo')}
          onStartEdit={() => handleStartEdit('monto_tributo')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('monto_tributo', parseFloat(val) || 0)}
          placeholder="0.00"
          step="0.01"
        />
      </td>

      {/* Obra / Área — dropdown con obras de Airtable (centros_costo) */}
      <td className="col-obra">
        <DropdownObras
          value={factura.obra_area}
          onChange={(val) => handleChange('obra_area', val)}
        />
      </td>

      {/* Cuenta contable — input libre. Vacía → fallback al default
          del template CONCAR (63/65). Se usa en columna K del Excel. */}
      <td className="col-cuenta">
        <EditableCell
          value={factura.cuenta_contable}
          type="text"
          isEditing={isEditing('cuenta_contable')}
          onStartEdit={() => handleStartEdit('cuenta_contable')}
          onStopEdit={handleStopEdit}
          onChange={(val) => handleChange('cuenta_contable', val)}
          placeholder="63/65 (default)"
          maxLength={12}
        />
      </td>

      {/* Estado */}
      <td className="col-estado">
        <span className="estado-badge">{factura.estado}</span>
      </td>

      {/* Acciones */}
      <td className="col-actions">
        {showWarning && (
          <AlertCircle
            size={16}
            className="warning-icon"
            title="Confianza baja — revisar datos"
          />
        )}
        <button
          type="button"
          className="btn-delete-row"
          onClick={() => onDelete(factura.id)}
          title="Eliminar fila"
          aria-label="Eliminar fila"
        >
          <Trash2 size={16} />
        </button>
      </td>
    </tr>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Componentes auxiliares
// ─────────────────────────────────────────────────────────────────────

function EditableCell({
  value,
  type,
  isEditing,
  onStartEdit,
  onStopEdit,
  onChange,
  placeholder,
  maxLength,
  step,
}) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select?.();
    }
  }, [isEditing]);

  const isEmpty = value === undefined || value === null || value === '';

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onStopEdit}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === 'Escape') onStopEdit();
        }}
        className="cell-input"
        maxLength={maxLength}
        step={step}
      />
    );
  }

  return (
    <div
      className={`cell-display ${isEmpty ? 'empty' : ''}`}
      onClick={onStartEdit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') onStartEdit();
      }}
      role="button"
      tabIndex={0}
      title="Click para editar"
    >
      {isEmpty ? placeholder : value}
    </div>
  );
}

function SelectCell({ value, options, onChange }) {
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className="cell-select"
    >
      {options.map((opt) => (
        <option key={opt.codigo} value={opt.codigo}>
          {opt.nombre}
        </option>
      ))}
    </select>
  );
}
