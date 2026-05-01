import { useState } from 'react';
import {
  LayoutDashboard, FileText, ShieldCheck, CreditCard,
  Receipt, BarChart3, Settings,
} from 'lucide-react';
import ModuleLayout from '../ModuleLayout';
import {
  InicioSection, SolicitudesSection, AprobacionesSection,
  PagosSection, RendicionesSection, ReportesSection, ConfiguracionSection,
} from './sections';
import './GestionCajaChica.css';

const NAV = [
  { id: 'inicio',         label: 'Inicio',         Icon: LayoutDashboard },
  { id: 'solicitudes',    label: 'Solicitudes',    Icon: FileText        },
  { id: 'aprobaciones',   label: 'Aprobaciones',   Icon: ShieldCheck     },
  { id: 'pagos',          label: 'Pagos',          Icon: CreditCard      },
  { id: 'rendiciones',    label: 'Rendiciones',    Icon: Receipt         },
  { id: 'reportes',       label: 'Reportes',       Icon: BarChart3       },
  { id: 'configuracion',  label: 'Configuración',  Icon: Settings        },
];

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
  const [active, setActive] = useState('inicio');
  const ActiveComp = SECTIONS[active];

  return (
    <ModuleLayout
      title="Gestión de Caja Chica"
      onOpenModules={onOpenModules}
      onLogout={onLogout}
    >
      <div className="gcc-shell">
        <aside className="gcc-sidebar">
          {NAV.map(({ id, label, Icon }) => (
            <button
              key={id}
              className={`gcc-nav-item ${active === id ? 'active' : ''}`}
              onClick={() => setActive(id)}
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </aside>

        <section className="gcc-content">
          <ActiveComp user={user} />
        </section>
      </div>
    </ModuleLayout>
  );
}
