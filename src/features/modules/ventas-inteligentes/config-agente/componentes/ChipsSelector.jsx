/**
 * Selector de chips reusable. Soporta single y multi.
 *
 * @param {Array<{id, label, hint?, preview?}>} options
 * @param {string|string[]} value
 * @param {(next: string|string[]) => void} onChange
 * @param {'single'|'multi'} mode
 * @param {boolean} disabled
 */
export default function ChipsSelector({
  options, value, onChange, mode = 'single', disabled = false, ariaLabel,
}) {
  const isSelected = (id) => {
    if (mode === 'multi') return Array.isArray(value) && value.includes(id);
    return value === id;
  };

  const toggle = (id) => {
    if (disabled) return;
    if (mode === 'multi') {
      const cur = Array.isArray(value) ? value : [];
      onChange(cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id]);
    } else {
      onChange(id);
    }
  };

  return (
    <div
      className={`via-chips ${disabled ? 'disabled' : ''}`}
      role={mode === 'single' ? 'radiogroup' : 'group'}
      aria-label={ariaLabel}
    >
      {options.map((opt) => {
        const sel = isSelected(opt.id);
        return (
          <button
            key={opt.id}
            type="button"
            role={mode === 'single' ? 'radio' : 'checkbox'}
            aria-checked={sel}
            className={`via-chip ${sel ? 'selected' : ''}`}
            onClick={() => toggle(opt.id)}
            disabled={disabled}
            title={opt.hint || opt.preview}
          >
            <span className="via-chip-label">{opt.label}</span>
            {opt.hint && <span className="via-chip-hint">{opt.hint}</span>}
          </button>
        );
      })}
    </div>
  );
}
