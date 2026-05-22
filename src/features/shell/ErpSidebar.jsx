import { useState, useEffect } from 'react';
import {
  Link,
  NavLink,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import {
  ChevronRight,
  ExternalLink,
  LayoutDashboard,
  LogOut,
  X,
} from 'lucide-react';
import { MODULES } from '../modules/modulesConfig';
import './ErpSidebar.css';

/**
 * Sidebar izquierda del shell ERP. Dos variantes:
 *
 *  - `variant="full"` (desktop ≥1280 + overlay tablet/mobile):
 *      Header (logo Yoko) + Dashboard + lista de módulos con acordeón
 *      de submenús + footer con usuario y logout.
 *
 *  - `variant="rail"` (tablet 768-1279):
 *      Columna de íconos verticales (56 px). Click en cualquier ícono
 *      llama `onRailIconClick` para que el shell abra la variante
 *      `full` como overlay.
 *
 * Reusa la lógica de `ModulesSidebar` original (auto-expand del módulo
 * activo, filtro por `enabledModulos`, links a `?section=`), pero con
 * estilos nuevos del shell ERP.
 */
export default function ErpSidebar({
  variant = 'full',
  enabledModulos,
  user,
  onLogout,
  onNavigate,
  onRailIconClick,
  showCloseButton = false,
  onClose,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentSection = searchParams.get('section') || 'inicio';

  const enabled = enabledModulos instanceof Set
    ? enabledModulos
    : new Set(Array.isArray(enabledModulos) ? enabledModulos : []);
  // Mostramos:
  //  - Módulos habilitados para la empresa (vienen en el JWT).
  //  - Módulos `upcoming` aunque no estén contratados, atenuados y con
  //    badge "Próximamente" — para comunicar la oferta completa del
  //    producto y empujar la compra.
  const visibleModules = MODULES.filter(
    (m) => enabled.has(m.id) || m.upcoming
  );
  // Para la lógica de "módulo actualmente abierto" usamos solo los habilitados,
  // porque los upcoming no son navegables.
  const enabledModules = MODULES.filter((m) => enabled.has(m.id));

  const [expandedId, setExpandedId] = useState(() => {
    const matched = enabledModules.find((m) => m.submenus && location.pathname.startsWith(m.path));
    return matched?.id || null;
  });

  useEffect(() => {
    const matched = enabledModules.find((m) => m.submenus && location.pathname.startsWith(m.path));
    if (matched && expandedId !== matched.id) {
      setExpandedId(matched.id);
    }
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Variante RAIL: solo íconos ──
  if (variant === 'rail') {
    return (
      <nav className="erp-sb erp-sb--rail" aria-label="Navegación principal">
        <Link
          to="/"
          className={`erp-sb-rail-item ${location.pathname === '/' ? 'is-active' : ''}`}
          title="Dashboard"
          onClick={onNavigate}
        >
          <LayoutDashboard size={20} />
        </Link>
        {visibleModules.map((m) => {
          const isActive = location.pathname.startsWith(m.path);
          if (m.upcoming) {
            return (
              <span
                key={m.id}
                className="erp-sb-rail-item is-upcoming"
                title={`${m.name} · Próximamente`}
                aria-disabled="true"
              >
                <m.Icon size={20} />
              </span>
            );
          }
          if (m.externalUrl) {
            return (
              <a
                key={m.id}
                href={m.externalUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="erp-sb-rail-item"
                title={m.name}
              >
                <m.Icon size={20} />
              </a>
            );
          }
          // En rail, al hacer click en un ícono con submenús abrimos el overlay
          // para que el usuario vea el módulo completo. Si no tiene submenús,
          // navegamos directo.
          if (m.submenus && m.submenus.length > 0) {
            return (
              <button
                key={m.id}
                type="button"
                className={`erp-sb-rail-item ${isActive ? 'is-active' : ''}`}
                title={m.name}
                onClick={onRailIconClick}
              >
                <m.Icon size={20} />
              </button>
            );
          }
          return (
            <Link
              key={m.id}
              to={m.path}
              className={`erp-sb-rail-item ${isActive ? 'is-active' : ''}`}
              title={m.name}
              onClick={onNavigate}
            >
              <m.Icon size={20} />
            </Link>
          );
        })}
        <div className="erp-sb-rail-spacer" />
        {onLogout && (
          <button
            type="button"
            className="erp-sb-rail-item"
            title="Cerrar sesión"
            onClick={onLogout}
          >
            <LogOut size={18} />
          </button>
        )}
      </nav>
    );
  }

  // ── Variante FULL ──
  const handleNavClick = () => {
    if (onNavigate) onNavigate();
  };

  const handleParentToggle = (module) => {
    const onThisModule = location.pathname.startsWith(module.path);
    if (onThisModule) {
      setExpandedId(expandedId === module.id ? null : module.id);
    } else {
      setExpandedId(module.id);
      navigate(`${module.path}?section=${module.submenus[0].id}`);
      if (onNavigate) onNavigate();
    }
  };

  return (
    <nav className="erp-sb erp-sb--full" aria-label="Navegación principal">
      <div className="erp-sb-header">
        <Link to="/" className="erp-sb-brand" onClick={handleNavClick}>
          <span className="erp-sb-brand-name">Procesos</span>
        </Link>
        {showCloseButton && (
          <button
            type="button"
            className="erp-sb-close"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <div className="erp-sb-list">
        {/* Dashboard global como primer ítem */}
        <NavLink
          to="/"
          end
          className={({ isActive }) => `erp-sb-item ${isActive ? 'is-active' : ''}`}
          onClick={handleNavClick}
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>

        {visibleModules.map((m) => {
          // Módulo aún no contratado / no disponible: render atenuado, no
          // navegable, con badge "Próximamente". El usuario ve la oferta
          // completa del producto pero no puede entrar.
          if (m.upcoming) {
            return (
              <div
                key={m.id}
                className="erp-sb-item is-upcoming"
                aria-disabled="true"
                title={`${m.name} aún no está disponible para tu empresa.`}
              >
                <m.Icon size={18} />
                <span>{m.name}</span>
                <span className="erp-sb-badge erp-sb-badge-upcoming">Próximamente</span>
              </div>
            );
          }
          if (m.externalUrl) {
            return (
              <a
                key={m.id}
                href={m.externalUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleNavClick}
                className="erp-sb-item"
              >
                <m.Icon size={18} />
                <span>{m.name}</span>
                {m.badge && <span className="erp-sb-badge">{m.badge}</span>}
                <ExternalLink size={14} className="erp-sb-ext" />
              </a>
            );
          }
          if (m.submenus && m.submenus.length > 0) {
            const isExpanded = expandedId === m.id;
            const isCurrentModule = location.pathname.startsWith(m.path);
            return (
              <div key={m.id} className="erp-sb-accordion">
                <button
                  type="button"
                  className={`erp-sb-item ${isCurrentModule ? 'is-active' : ''}`}
                  onClick={() => handleParentToggle(m)}
                >
                  <m.Icon size={18} />
                  <span>{m.name}</span>
                  {m.badge && <span className="erp-sb-badge">{m.badge}</span>}
                  <ChevronRight
                    size={14}
                    className={`erp-sb-chev ${isExpanded ? 'open' : ''}`}
                  />
                </button>
                {isExpanded && (
                  <div className="erp-sb-submenu">
                    {m.submenus.map((sm) => {
                      const isActive = isCurrentModule && currentSection === sm.id;
                      if (sm.externalUrl) {
                        return (
                          <a
                            key={sm.id}
                            href={sm.externalUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={handleNavClick}
                            className="erp-sb-subitem"
                          >
                            <sm.Icon size={14} />
                            <span>{sm.label}</span>
                            <ExternalLink size={12} className="erp-sb-ext" />
                          </a>
                        );
                      }
                      return (
                        <Link
                          key={sm.id}
                          to={`${m.path}?section=${sm.id}`}
                          onClick={handleNavClick}
                          className={`erp-sb-subitem ${isActive ? 'is-active' : ''}`}
                        >
                          <sm.Icon size={14} />
                          <span>{sm.label}</span>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }
          // Módulo sin submenús → link directo
          return (
            <NavLink
              key={m.id}
              to={m.path}
              onClick={handleNavClick}
              className={({ isActive }) => `erp-sb-item ${isActive ? 'is-active' : ''}`}
            >
              <m.Icon size={18} />
              <span>{m.name}</span>
              {m.badge && <span className="erp-sb-badge">{m.badge}</span>}
            </NavLink>
          );
        })}
      </div>

      {user && (
        <div className="erp-sb-footer">
          <div className="erp-sb-user">
            <div className="erp-sb-user-avatar">
              {(user?.nombre || user?.email || '?').slice(0, 1).toUpperCase()}
            </div>
            <div className="erp-sb-user-info">
              <div className="erp-sb-user-name">{user?.nombre || 'Usuario'}</div>
              <div className="erp-sb-user-email">{user?.email || ''}</div>
            </div>
          </div>
          {onLogout && (
            <button
              type="button"
              className="erp-sb-logout"
              onClick={onLogout}
              title="Cerrar sesión"
            >
              <LogOut size={16} />
            </button>
          )}
        </div>
      )}
    </nav>
  );
}
