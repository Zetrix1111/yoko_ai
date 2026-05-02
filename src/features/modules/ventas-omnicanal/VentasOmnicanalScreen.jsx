import { useSearchParams } from 'react-router-dom';
import ModuleLayout from '../ModuleLayout';
import {
  InicioSection, CanalesSection, FlujoSection, CatalogoSection,
  PipelineSection, AutomatizacionesSection, TrainingSection, CrmSection,
  NotificacionesSection, ConfiguracionSection,
} from './sections';
import './VentasOmnicanal.css';

const SECTIONS = {
  inicio:           InicioSection,
  canales:          CanalesSection,
  flujo:            FlujoSection,
  catalogo:         CatalogoSection,
  pipeline:         PipelineSection,
  automatizaciones: AutomatizacionesSection,
  training:         TrainingSection,
  crm:              CrmSection,
  notificaciones:   NotificacionesSection,
  configuracion:    ConfiguracionSection,
};

export default function VentasOmnicanalScreen({ user, onOpenModules, onLogout }) {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'inicio';
  const ActiveComp = SECTIONS[section] || InicioSection;

  return (
    <ModuleLayout
      title="Ventas Omnicanal con IA"
      onOpenModules={onOpenModules}
      onLogout={onLogout}
    >
      <div className="vom-content vom-content-full">
        <ActiveComp user={user} />
      </div>
    </ModuleLayout>
  );
}
