import { Check } from 'lucide-react';

const PASOS_LABELS = [
  { num: 1, label: 'Voz' },
  { num: 2, label: 'Política' },
  { num: 3, label: 'Cliente' },
  { num: 4, label: 'Marca' },
  { num: 5, label: 'Límites' },
];

/**
 * Barra superior con 5 pasos clickeables. Permite saltar libremente
 * entre pasos (no es lineal forzado).
 *
 * @param {number} pasoActual — 1..5 (0 es la pantalla inicial, no se muestra acá)
 * @param {Set<number>} pasosCompletados — pasos con al menos un campo activo
 * @param {(num: number) => void} onPasoClick
 */
export default function BarraProgreso({ pasoActual, pasosCompletados, onPasoClick }) {
  return (
    <nav className="via-progress-bar" aria-label="Progreso del wizard">
      {PASOS_LABELS.map(({ num, label }) => {
        const completado = pasosCompletados?.has(num);
        const activo = pasoActual === num;
        const cls = `via-progress-step ${
          activo ? 'active' : completado ? 'completed' : 'pending'
        }`;
        return (
          <button
            key={num}
            type="button"
            className={cls}
            onClick={() => onPasoClick(num)}
            aria-current={activo ? 'step' : undefined}
          >
            <span className="via-progress-num">
              {completado && !activo ? <Check size={14} /> : num}
            </span>
            <span className="via-progress-label">{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
