import { useSearchParams } from 'react-router-dom';
import ModuleLayout from '../ModuleLayout';
import { DashboardSection, RevisionSection } from './sections';
import './FacturasInteligentes.css';

// La sub-navegación vive en la sidebar derecha (acordeón en
// ModulesSidebar.jsx) y comparte el patrón de `gestion-caja-chica`.
// Esta pantalla solo lee `?section=<id>` de la URL y renderiza la sección
// correspondiente. Default: `inicio` (dashboard).
const SECTIONS = {
  inicio:   DashboardSection,
  revision: RevisionSection,
};

export default function FacturasInteligentesScreen({ user, onOpenModules, onLogout }) {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'inicio';
  const ActiveComp = SECTIONS[section] || DashboardSection;

  return (
    <ModuleLayout
      title="Facturas Inteligentes"
      onOpenModules={onOpenModules}
      onLogout={onLogout}
    >
      <ActiveComp user={user} />
    </ModuleLayout>
  );
}
