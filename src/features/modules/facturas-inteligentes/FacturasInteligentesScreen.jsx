import { useSearchParams } from 'react-router-dom';
import ModuleLayout from '../ModuleLayout';
import { DashboardSection, RevisionSection } from './sections';
import ProcesosSection from './sections/ProcesosSection';
import ExportacionesSection from './sections/ExportacionesSection';
import './FacturasInteligentes.css';

// La sub-navegación vive en la sidebar izquierda del shell (ErpSidebar).
// Esta pantalla solo lee `?section=<id>` de la URL y renderiza la sección
// correspondiente. Default: `inicio` (dashboard).
const SECTIONS = {
  inicio:        DashboardSection,
  procesos:      ProcesosSection,
  revision:      RevisionSection,
  exportaciones: ExportacionesSection,
};

export default function FacturasInteligentesScreen({ user }) {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'inicio';
  const ActiveComp = SECTIONS[section] || DashboardSection;

  return (
    <ModuleLayout>
      <ActiveComp user={user} />
    </ModuleLayout>
  );
}
