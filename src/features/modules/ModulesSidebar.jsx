import { NavLink } from 'react-router-dom';
import { X } from 'lucide-react';
import { MODULES } from './modulesConfig';
import QuickLinksRail from '../quick-links/QuickLinksRail';

export default function ModulesSidebar({ show, onClose }) {
  const handleClick = () => {
    if (onClose) onClose();
  };

  return (
    <aside className={`modules-sidebar ${show ? 'show-mobile' : 'hidden lg:flex'}`}>
      <QuickLinksRail />
      <div className="sidebar-header flex justify-between items-center">
        <div>
          <h2 className="sidebar-title">Módulos</h2>
          <p className="sidebar-subtitle">Selecciona uno</p>
        </div>
        <button className="icon-btn lg:hidden" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="modules-grid">
        {MODULES.map(({ id, path, name, Icon, iconClass, badge }) => (
          <NavLink key={id} to={path} onClick={handleClick} className="module-card">
            <div className={`module-icon-wrapper ${iconClass}`}>
              <Icon size={20} />
            </div>
            <div className="module-content">
              <h3 className="module-name">{name}</h3>
              {badge && <span className="module-badge">{badge}</span>}
            </div>
          </NavLink>
        ))}
      </div>

      <div className="sidebar-footer glass-panel">
        <p>Más funciones en desarrollo...</p>
      </div>
    </aside>
  );
}
