import { ArrowLeft, LayoutGrid, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// Wrapper común para pantallas de módulos. Usa la misma estética del chat.
// La otra persona solo necesita pasar title + children (el formulario).
export default function ModuleLayout({ title, subtitle, children, onOpenModules, onLogout }) {
  const navigate = useNavigate();

  return (
    <div className="chat-wrapper glass-panel">
      <header className="chat-header border-b">
        <div className="header-info">
          <button className="icon-btn" onClick={() => navigate('/')} title="Volver al chat">
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="agent-name">{title}</h1>
            {subtitle && <p className="agent-status">{subtitle}</p>}
          </div>
        </div>
        <div className="header-actions">
          {onLogout && (
            <button
              className="icon-btn"
              onClick={onLogout}
              title="Cerrar sesión"
              aria-label="Cerrar sesión"
            >
              <LogOut size={20} />
            </button>
          )}
          <button className="icon-btn lg:hidden" onClick={onOpenModules}>
            <LayoutGrid size={20} />
          </button>
        </div>
      </header>
      <main className="messages-area">
        {children}
      </main>
    </div>
  );
}
