import { useSearchParams } from 'react-router-dom';
import ModuleLayout from '../ModuleLayout';
import {
  InicioSection, ClientesSection, ProductosSection, ConfiguracionSection,
  RespuestasIASection,
} from './sections';
import ConfigAgenteWizard from './config-agente/ConfigAgenteWizard';
import './VentasInteligentes.css';

const SECTIONS = {
  inicio:           InicioSection,
  'respuestas-ia':  RespuestasIASection,
  clientes:         ClientesSection,
  productos:        ProductosSection,
  configuracion:    ConfiguracionSection,
  'config-agente':  ConfigAgenteWizard,
};

export default function VentasInteligentesScreen({ user, onOpenModules, onLogout }) {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'inicio';
  const ActiveComp = SECTIONS[section] || InicioSection;

  return (
    <ModuleLayout
      title="Ventas Inteligentes"
      onOpenModules={onOpenModules}
      onLogout={onLogout}
    >
      <div className="vom-content vom-content-full">
        <ActiveComp user={user} />
      </div>
    </ModuleLayout>
  );
}
