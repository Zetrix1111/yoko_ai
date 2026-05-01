import { useSearchParams } from 'react-router-dom';
import ModuleLayout from '../ModuleLayout';
import {
  InicioSection, SolicitudesSection, AprobacionesSection,
  PagosSection, RendicionesSection, ReportesSection, ConfiguracionSection,
} from './sections';
import './GestionCajaChica.css';

// La sub-navegación ahora vive en la sidebar derecha (acordeón en
// ModulesSidebar.jsx). Esta pantalla solo lee ?section=<id> de la URL
// y renderiza la sección correspondiente.
const SECTIONS = {
  inicio:        InicioSection,
  solicitudes:   SolicitudesSection,
  aprobaciones:  AprobacionesSection,
  pagos:         PagosSection,
  rendiciones:   RendicionesSection,
  reportes:      ReportesSection,
  configuracion: ConfiguracionSection,
};

export default function GestionCajaChicaScreen({ user, onOpenModules, onLogout }) {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'inicio';
  const ActiveComp = SECTIONS[section] || InicioSection;

  return (
    <ModuleLayout
      title="Gestión de Caja Chica y Rendición de fondos"
      onOpenModules={onOpenModules}
      onLogout={onLogout}
    >
      <div className="gcc-content gcc-content-full">
        <ActiveComp user={user} />
      </div>
    </ModuleLayout>
  );
}
