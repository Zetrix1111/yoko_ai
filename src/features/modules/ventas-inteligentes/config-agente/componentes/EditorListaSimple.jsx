import { useState } from 'react';
import { Plus, X, Lightbulb } from 'lucide-react';

/**
 * Editor de lista de strings simples. Items chips con borrar, input para
 * agregar nuevos, sugerencias clickeables opcionales.
 *
 * @param {string[]} items
 * @param {(next: string[]) => void} onChange
 * @param {string} placeholder
 * @param {number} maxItems
 * @param {string[]} sugerencias
 * @param {string} ariaLabel
 * @param {boolean} disabled
 */
export default function EditorListaSimple({
  items = [], onChange, placeholder = 'Agregar...', maxItems = 10,
  sugerencias = [], ariaLabel, disabled = false,
}) {
  const [draft, setDraft] = useState('');

  const lista = Array.isArray(items) ? items : [];
  const lleno = lista.length >= maxItems;
  const sinUsar = sugerencias.filter((s) => !lista.includes(s));

  const agregar = (str) => {
    const v = (str || '').trim();
    if (!v || lleno) return;
    if (lista.includes(v)) return;
    onChange([...lista, v]);
    setDraft('');
  };

  const quitar = (idx) => {
    onChange(lista.filter((_, i) => i !== idx));
  };

  return (
    <div className={`via-editor-lista ${disabled ? 'disabled' : ''}`}>
      {lista.length > 0 && (
        <div className="via-editor-lista-items" aria-label={ariaLabel}>
          {lista.map((item, idx) => (
            <span key={`${item}-${idx}`} className="via-editor-lista-item">
              <span>{item}</span>
              <button
                type="button"
                className="via-editor-lista-quitar"
                aria-label={`Quitar ${item}`}
                onClick={() => quitar(idx)}
                disabled={disabled}
              >
                <X size={14} />
              </button>
            </span>
          ))}
        </div>
      )}

      {!lleno && (
        <div className="via-editor-lista-input">
          <input
            type="text"
            className="vom-input"
            placeholder={placeholder}
            value={draft}
            disabled={disabled}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                agregar(draft);
              }
            }}
          />
          <button
            type="button"
            className="vom-btn vom-btn-ghost"
            onClick={() => agregar(draft)}
            disabled={disabled || !draft.trim()}
          >
            <Plus size={14} /> Agregar
          </button>
        </div>
      )}

      {!lleno && sinUsar.length > 0 && (
        <div className="via-editor-lista-sugerencias">
          <div className="via-editor-lista-sugerencias-titulo">
            <Lightbulb size={12} /> Sugerencias:
          </div>
          {sinUsar.slice(0, 5).map((s) => (
            <button
              key={s}
              type="button"
              className="via-chip via-chip-sugerencia"
              onClick={() => agregar(s)}
              disabled={disabled}
            >
              + {s}
            </button>
          ))}
        </div>
      )}

      <div className="via-editor-lista-contador">
        {lista.length} / {maxItems}
      </div>
    </div>
  );
}
