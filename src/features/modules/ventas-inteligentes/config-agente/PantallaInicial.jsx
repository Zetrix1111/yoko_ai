import { ArrowRight } from 'lucide-react';
import PanelInformativo from './componentes/PanelInformativo';
import { PLANTILLAS_VERTICAL } from './plantillas';

/**
 * Pantalla inicial del wizard. Muestra 5 cards de plantillas de vertical.
 * Al elegir una, se precarga la config y se salta al Paso 1.
 */
export default function PantallaInicial({ onElegirPlantilla }) {
  return (
    <div className="via-wizard-inicio">
      <header className="via-wizard-inicio-header">
        <h2 className="via-wizard-inicio-titulo">
          Configurá el agente IA de tu negocio
        </h2>
        <p className="via-wizard-inicio-subtitulo">
          Tu agente ya tiene una configuración base que funciona. Personalizá
          solo lo que quieras cambiar.
        </p>
      </header>

      <PanelInformativo titulo="¿Por dónde empezar?">
        Elegí una plantilla de tu industria para arrancar con valores
        razonables, o empezá de cero y configurá todo a tu gusto. Siempre
        podés volver y cambiar cualquier campo.
      </PanelInformativo>

      <div className="via-plantilla-grid">
        {PLANTILLAS_VERTICAL.map((p) => (
          <button
            key={p.id}
            type="button"
            className="via-plantilla-card"
            onClick={() => onElegirPlantilla(p)}
          >
            <div className="via-plantilla-card-emoji" aria-hidden="true">
              {p.emoji}
            </div>
            <div className="via-plantilla-card-body">
              <div className="via-plantilla-card-titulo">{p.label}</div>
              <div className="via-plantilla-card-descripcion">
                {p.descripcion}
              </div>
            </div>
            <div className="via-plantilla-card-cta">
              Usar <ArrowRight size={14} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
