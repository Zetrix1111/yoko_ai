/**
 * src/shared/components/Toggle.jsx
 *
 * Switch genérico (button[role="switch"]). Antes vivía duplicado
 * byte-por-byte en 3 módulos (ventas-inteligentes, configuracion-empresa,
 * gestion-caja-chica), cada uno con su propio prefijo de clase CSS.
 *
 * Para preservar los estilos existentes de cada módulo sin migrarlos a
 * un CSS shared, el componente acepta `classPrefix`: usa
 * `${classPrefix}-toggle` y `${classPrefix}-toggle-thumb`. Así cada
 * módulo sigue dueño de sus colores/tamaños vía su propio archivo .css.
 *
 * Uso:
 *   import Toggle from '../../../shared/components/Toggle';
 *   <Toggle classPrefix="vom" checked={x} onChange={setX} ariaLabel="..." />
 */
export default function Toggle({ checked, onChange, ariaLabel, classPrefix }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      className={`${classPrefix}-toggle ${checked ? 'on' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span className={`${classPrefix}-toggle-thumb`} />
    </button>
  );
}
