import { useState, useEffect } from 'react';
import { NavLink, Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { X, ChevronRight, ExternalLink } from 'lucide-react';
import { MODULES } from './modulesConfig';
import { isModuleEnabled } from '../../tenants';
import QuickLinksRail from '../quick-links/QuickLinksRail';

// ─────────────────────────────────────
// Accordion sub-components
// ─────────────────────────────────────

function ProcessItem({ module, isExpanded, isActive, onToggle, onClose }) {
  return (
    <button
      type="button"
      className={`module-card module-card-parent ${isActive ? 'is-current' : ''}`}
      onClick={() => onToggle(module)}
    >
      <div className={`module-icon-wrapper ${module.iconClass}`}>
        <module.Icon size={20} />
      </div>
      <div className="module-content">
        <h3 className="module-name">{module.name}</h3>
        {module.badge && <span className="module-badge">{module.badge}</span>}
      </div>
      <ChevronRight
        size={18}
        className={`module-chevron ${isExpanded ? 'open' : ''}`}
      />
    </button>
  );
}

function SubmenuItem({ to, label, Icon, isActive, onClick, externalUrl }) {
  // Si la subsección apunta a un sistema externo, abrimos en nueva
  // pestaña para no perder la sesión del usuario en Yoko.
  if (externalUrl) {
    return (
      <a
        href={externalUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={onClick}
        className="module-submenu-item"
      >
        <Icon size={14} />
        <span style={{ flex: 1 }}>{label}</span>
        <ExternalLink size={12} style={{ opacity: 0.6 }} />
      </a>
    );
  }
  // Usamos <Link> (no NavLink) porque NavLink solo matchea por pathname
  // y nuestros submenús comparten pathname (varían por ?section=). El
  // estado activo lo calcula el padre y se pasa por prop.
  return (
    <Link to={to} onClick={onClick} className={`module-submenu-item ${isActive ? 'active' : ''}`}>
      <Icon size={14} />
      <span>{label}</span>
    </Link>
  );
}

function ProcessAccordion({ module, currentPath, currentSection, isExpanded, onToggle, onClose }) {
  const isCurrentModule = currentPath.startsWith(module.path);
  return (
    <div className="module-accordion">
      <ProcessItem
        module={module}
        isExpanded={isExpanded}
        isActive={isCurrentModule}
        onToggle={onToggle}
        onClose={onClose}
      />
      <div className={`modules-submenu ${isExpanded ? 'open' : ''}`}>
        {module.submenus.map((sm) => {
          const isActive = !sm.externalUrl && isCurrentModule && currentSection === sm.id;
          return (
            <SubmenuItem
              key={sm.id}
              to={`${module.path}?section=${sm.id}`}
              label={sm.label}
              Icon={sm.Icon}
              isActive={isActive}
              onClick={onClose}
              externalUrl={sm.externalUrl}
            />
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────
// Main sidebar
// ─────────────────────────────────────

export default function ModulesSidebar({ show, onClose }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentSection = searchParams.get('section') || 'inicio';

  // Solo mostramos los módulos que el tenant tiene habilitados.
  const enabledModules = MODULES.filter((m) => isModuleEnabled(m.id));

  // Cuál acordeón está expandido. Auto-expande el del módulo donde está el user.
  const [expandedId, setExpandedId] = useState(() => {
    const matched = enabledModules.find((m) => m.submenus && location.pathname.startsWith(m.path));
    return matched?.id || null;
  });

  // Re-sincroniza expansión cuando cambia la URL (deep-link, back/forward, etc.)
  useEffect(() => {
    const matched = enabledModules.find((m) => m.submenus && location.pathname.startsWith(m.path));
    if (matched && expandedId !== matched.id) {
      setExpandedId(matched.id);
    }
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNavClick = () => {
    if (onClose) onClose();
  };

  const handleParentToggle = (module) => {
    const onThisModule = location.pathname.startsWith(module.path);
    if (onThisModule) {
      // Ya estamos en este módulo → solo togglear el acordeón
      setExpandedId(expandedId === module.id ? null : module.id);
    } else {
      // No estamos en este módulo → expandir + navegar
      setExpandedId(module.id);
      navigate(`${module.path}?section=${module.submenus[0].id}`);
      if (onClose) onClose();
    }
  };

  return (
    <aside className={`modules-sidebar ${show ? 'show-mobile' : 'hidden lg:flex'}`}>
      <QuickLinksRail />
      <div className="sidebar-header flex justify-between items-center">
        <div>
          <h2 className="sidebar-title">Procesos</h2>
          <p className="sidebar-subtitle">Selecciona un proceso</p>
        </div>
        <button className="icon-btn lg:hidden" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="modules-grid">
        {enabledModules.map((m) => {
          if (m.submenus && m.submenus.length > 0) {
            return (
              <ProcessAccordion
                key={m.id}
                module={m}
                currentPath={location.pathname}
                currentSection={currentSection}
                isExpanded={expandedId === m.id}
                onToggle={handleParentToggle}
                onClose={handleNavClick}
              />
            );
          }
          // Módulo sin submenús: NavLink directo (comportamiento clásico)
          return (
            <NavLink key={m.id} to={m.path} onClick={handleNavClick} className="module-card">
              <div className={`module-icon-wrapper ${m.iconClass}`}>
                <m.Icon size={20} />
              </div>
              <div className="module-content">
                <h3 className="module-name">{m.name}</h3>
                {m.badge && <span className="module-badge">{m.badge}</span>}
              </div>
            </NavLink>
          );
        })}
      </div>

      <div className="sidebar-footer glass-panel">
        <p>Más funciones en desarrollo...</p>
      </div>
    </aside>
  );
}
