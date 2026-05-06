import { useSearchParams } from 'react-router-dom';
import ModuleLayout from '../ModuleLayout';
import {
  InicioSection, ClientesSection, ProductosSection, WhatsAppSection,
  RespuestasIASection, ConfiguracionSection,
} from './sections';
import ConfigAgenteWizard from './config-agente/ConfigAgenteWizard';
import './VentasInteligentes.css';

const SECTIONS = {
  inicio:           InicioSection,
  'respuestas-ia':  RespuestasIASection,
  clientes:         ClientesSection,
  productos:        ProductosSection,
  whatsapp:         WhatsAppSection,
  'config-agente':  ConfigAgenteWizard,
  // Alias: ?section=configuracion (URLs antiguas) cae al wrapper de WhatsApp.
  configuracion:    ConfiguracionSection,
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
