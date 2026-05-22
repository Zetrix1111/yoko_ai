import './ModuleLayout.css';

/**
 * Wrapper de las pantallas de módulo dentro del shell ERP.
 *
 * El header viejo (con botón "atrás", logout y "abrir módulos") se quitó:
 * el shell ahora aporta la navegación por la sidebar izquierda y el chat
 * por el panel IA derecho. Este wrapper queda como un contenedor liviano
 * con título + subtítulo opcionales arriba del contenido del módulo.
 *
 * Si una pantalla no necesita header (porque ya tiene el suyo propio),
 * puede omitir `title` y este componente solo renderiza un `<section>`.
 */
export default function ModuleLayout({ title, subtitle, children, action }) {
  return (
    <section className="erp-module">
      {(title || action) && (
        <header className="erp-module-header">
          <div className="erp-module-titles">
            {title && <h1 className="erp-module-title">{title}</h1>}
            {subtitle && <p className="erp-module-subtitle">{subtitle}</p>}
          </div>
          {action && <div className="erp-module-action">{action}</div>}
        </header>
      )}
      <div className="erp-module-body">{children}</div>
    </section>
  );
}
