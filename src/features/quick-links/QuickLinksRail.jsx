import { QUICK_LINKS } from './quickLinksConfig';

// Rail vertical a la izquierda estilo Outlook: solo ícono + nombre corto.
// Cada item abre el Excel compartido en nueva pestaña.
export default function QuickLinksRail() {
  return (
    <aside className="quick-links-rail">
      {QUICK_LINKS.map(({ id, name, url, Icon, color }) => {
        const disabled = !url;
        const content = (
          <>
            <div className="quick-link-icon" style={{ backgroundColor: color }}>
              <Icon size={20} />
            </div>
            <span className="quick-link-label">{name}</span>
          </>
        );

        if (disabled) {
          return (
            <div key={id} className="quick-link-item disabled" title="Próximamente">
              {content}
            </div>
          );
        }

        return (
          <a
            key={id}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="quick-link-item"
            title={`Abrir ${name} en nueva pestaña`}
          >
            {content}
          </a>
        );
      })}
    </aside>
  );
}
