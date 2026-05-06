import { Plus, Trash2 } from 'lucide-react';

/**
 * Editor de lista de objetos según un schema declarado. Útil para
 * `faq`, `promociones_activas`, `objeciones`, `discovery_preguntas`.
 *
 * @param {Array<object>} items — la lista actual
 * @param {(next: Array<object>) => void} onChange
 * @param {Array<{key, label, type: 'text'|'textarea'|'date'|'switch', placeholder?, optional?, rows?}>} schema
 * @param {number} maxItems
 * @param {string} itemLabel — singular ("FAQ", "Objeción", etc.)
 * @param {Array<object>} plantillas — items pre-cargables con un click
 * @param {boolean} disabled
 */
export default function EditorListaCompleja({
  items = [], onChange, schema = [], maxItems = 30,
  itemLabel = 'Item', plantillas = [], disabled = false,
}) {
  const lista = Array.isArray(items) ? items : [];
  const lleno = lista.length >= maxItems;

  const agregar = (preset = null) => {
    if (lleno || disabled) return;
    const nuevo = preset || schema.reduce((acc, f) => {
      acc[f.key] =
        f.type === 'switch' ? false :
        f.type === 'date'   ? '' :
        '';
      return acc;
    }, {});
    onChange([...lista, nuevo]);
  };

  const quitar = (idx) => {
    onChange(lista.filter((_, i) => i !== idx));
  };

  const actualizar = (idx, key, valor) => {
    onChange(lista.map((item, i) => (i === idx ? { ...item, [key]: valor } : item)));
  };

  return (
    <div className={`via-editor-compleja ${disabled ? 'disabled' : ''}`}>
      {lista.map((item, idx) => (
        <div key={idx} className="via-editor-compleja-item">
          <div className="via-editor-compleja-item-header">
            <span className="via-editor-compleja-item-num">{itemLabel} #{idx + 1}</span>
            <button
              type="button"
              className="via-editor-compleja-quitar"
              onClick={() => quitar(idx)}
              disabled={disabled}
              aria-label={`Eliminar ${itemLabel} #${idx + 1}`}
            >
              <Trash2 size={14} />
            </button>
          </div>
          <div className="via-editor-compleja-item-fields">
            {schema.map((f) => {
              const id = `via-edcom-${idx}-${f.key}`;
              const val = item[f.key] ?? (f.type === 'switch' ? false : '');
              if (f.type === 'textarea') {
                return (
                  <div key={f.key} className="via-edcom-field">
                    <label htmlFor={id}>{f.label}{f.optional ? ' (opcional)' : ''}</label>
                    <textarea
                      id={id}
                      className="vom-textarea"
                      rows={f.rows || 2}
                      placeholder={f.placeholder || ''}
                      value={val || ''}
                      disabled={disabled}
                      onChange={(e) => actualizar(idx, f.key, e.target.value)}
                    />
                  </div>
                );
              }
              if (f.type === 'date') {
                return (
                  <div key={f.key} className="via-edcom-field">
                    <label htmlFor={id}>{f.label}{f.optional ? ' (opcional)' : ''}</label>
                    <input
                      id={id}
                      type="date"
                      className="vom-input"
                      value={val || ''}
                      disabled={disabled}
                      onChange={(e) => actualizar(idx, f.key, e.target.value)}
                    />
                  </div>
                );
              }
              if (f.type === 'switch') {
                return (
                  <div key={f.key} className="via-edcom-field-inline">
                    <label className="via-edcom-switch">
                      <input
                        type="checkbox"
                        checked={!!val}
                        disabled={disabled}
                        onChange={(e) => actualizar(idx, f.key, e.target.checked)}
                      />
                      {f.label}
                    </label>
                  </div>
                );
              }
              return (
                <div key={f.key} className="via-edcom-field">
                  <label htmlFor={id}>{f.label}{f.optional ? ' (opcional)' : ''}</label>
                  <input
                    id={id}
                    type="text"
                    className="vom-input"
                    placeholder={f.placeholder || ''}
                    value={val || ''}
                    disabled={disabled}
                    onChange={(e) => actualizar(idx, f.key, e.target.value)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {!lleno && (
        <div className="via-editor-compleja-acciones">
          <button
            type="button"
            className="vom-btn vom-btn-ghost"
            onClick={() => agregar()}
            disabled={disabled}
          >
            <Plus size={14} /> Agregar {itemLabel.toLowerCase()}
          </button>

          {plantillas.length > 0 && (
            <div className="via-editor-compleja-plantillas">
              <span>Plantillas:</span>
              {plantillas.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  className="via-chip via-chip-sugerencia"
                  onClick={() => agregar(p)}
                  disabled={disabled}
                >
                  + {p[schema[0]?.key]?.slice(0, 30) || 'Plantilla'}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="via-editor-compleja-contador">
        {lista.length} / {maxItems}
      </div>
    </div>
  );
}
