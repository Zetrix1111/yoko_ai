import { useEffect, useState } from 'react';
import { EmpresaProvider } from '../empresa/EmpresaContext';
import ErpSidebar from './ErpSidebar';
import ErpAIPanel from './ErpAIPanel';
import './ErpShell.css';

/**
 * Shell maestro de 3 paneles del ERP.
 *
 *   ┌──────────┬──────────────────────┬───────────────┐
 *   │ Sidebar  │   Workspace central  │  Panel IA     │
 *   │  15%     │       60%            │    25%        │
 *   └──────────┴──────────────────────┴───────────────┘
 *
 * En tablet (768-1279 px) la sidebar colapsa a un rail de íconos (56 px)
 * y el panel IA crece a ~30%. Click en un ícono del rail abre la sidebar
 * completa como overlay.
 *
 * En mobile (<768 px) sidebar y panel IA se ocultan; queda solo el
 * workspace + un botón ☰ arriba a la izquierda para abrir la sidebar
 * como overlay. El bottom-sheet para el chat queda pendiente para otro
 * plan.
 *
 * Importante: el panel IA es PERSISTENTE — vive en este shell, no en
 * cada ruta. Por eso `useChat` (dentro de ErpAIPanel) no se desmonta
 * al cambiar de módulo, y la conversación no se pierde.
 */
export default function ErpShell({ user, onLogout, children }) {
  const [sidebarOverlayOpen, setSidebarOverlayOpen] = useState(false);
  const [breakpoint, setBreakpoint] = useState(getBreakpoint());

  useEffect(() => {
    const onResize = () => setBreakpoint(getBreakpoint());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const enabledModulos = new Set(user?.empresa?.modulos || []);
  const isDesktop = breakpoint === 'desktop';
  const isTablet = breakpoint === 'tablet';
  const isMobile = breakpoint === 'mobile';

  const openOverlay = () => setSidebarOverlayOpen(true);
  const closeOverlay = () => setSidebarOverlayOpen(false);

  return (
    <EmpresaProvider>
      <div className={`erp-shell erp-shell--${breakpoint}`}>
        {/* Sidebar inline: full en desktop, rail en tablet, oculta en mobile */}
        {!isMobile && (
          <aside className="erp-sidebar-slot">
            <ErpSidebar
              variant={isDesktop ? 'full' : 'rail'}
              enabledModulos={enabledModulos}
              user={user}
              onLogout={onLogout}
              onRailIconClick={openOverlay}
            />
          </aside>
        )}

        {/* Workspace central */}
        <main className="erp-workspace">
          {isMobile && (
            <div className="erp-workspace-toolbar">
              <button
                type="button"
                className="erp-workspace-burger"
                onClick={openOverlay}
                aria-label="Abrir navegación"
              >
                ☰
              </button>
            </div>
          )}
          <div className="erp-workspace-content">{children}</div>
        </main>

        {/* Panel IA derecho: visible en desktop y tablet */}
        {!isMobile && (
          <aside className="erp-ai-slot">
            <ErpAIPanel user={user} />
          </aside>
        )}

        {/* Overlay: la sidebar completa por encima cuando el usuario abre el rail/burger */}
        {sidebarOverlayOpen && (
          <div className="erp-sidebar-overlay" onClick={closeOverlay} role="presentation">
            <div className="erp-sidebar-overlay-panel" onClick={(e) => e.stopPropagation()}>
              <ErpSidebar
                variant="full"
                enabledModulos={enabledModulos}
                user={user}
                onLogout={onLogout}
                onNavigate={closeOverlay}
                showCloseButton
                onClose={closeOverlay}
              />
            </div>
          </div>
        )}
      </div>
    </EmpresaProvider>
  );
}

function getBreakpoint() {
  if (typeof window === 'undefined') return 'desktop';
  const w = window.innerWidth;
  if (w < 768) return 'mobile';
  if (w < 1280) return 'tablet';
  return 'desktop';
}
