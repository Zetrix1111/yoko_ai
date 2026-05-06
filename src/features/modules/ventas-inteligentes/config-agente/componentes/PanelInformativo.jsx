import { Info } from 'lucide-react';

/**
 * Banner gris claro con icono Info. Usado para textos explicativos
 * persistentes (no tooltips) dentro de un paso del wizard.
 */
export default function PanelInformativo({ titulo, children, variant = 'info' }) {
  return (
    <div className={`via-panel-info via-panel-info-${variant}`} role="note">
      <div className="via-panel-info-icon">
        <Info size={16} />
      </div>
      <div className="via-panel-info-body">
        {titulo && <div className="via-panel-info-titulo">{titulo}</div>}
        <div className="via-panel-info-texto">{children}</div>
      </div>
    </div>
  );
}
