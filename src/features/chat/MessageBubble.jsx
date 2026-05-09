import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Download } from 'lucide-react';
import { APP_NAME, APP_LOGO } from '../../shared/branding';
import { API, getAuthToken } from '../../shared/api';

// El backend (yoko_generar_registro_contable) le instruye al agent a
// incluir esta línea exacta al final de su respuesta cuando el archivo
// está listo para descargar. Acá la detectamos y la reemplazamos por un
// botón que dispara la descarga real via POST /api/facturas?action=concar.
const MARKER_REGEX = /\[DESCARGAR_REGISTRO:([a-zA-Z0-9_-]+)\]/g;

function DownloadRegistroButton({ procesoId }) {
  const [state, setState] = useState('idle'); // idle | loading | done | error

  const handleClick = async () => {
    if (state === 'loading') return;
    setState('loading');
    try {
      const token = getAuthToken();
      const res = await fetch(API.FACTURAS_CONCAR, {
        method: 'POST',
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ proceso_id: procesoId }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      // Si el server mandó Content-Disposition con filename, lo respetamos;
      // si no, fallback al patrón histórico.
      const cd = res.headers.get('Content-Disposition') || '';
      const m = cd.match(/filename="?([^";]+)"?/i);
      const filename = m ? m[1] : `REGISTRO_${procesoId}.xlsx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setState('done');
    } catch (err) {
      console.error('[chat/download-registro]', err);
      setState('error');
    }
  };

  const label =
    state === 'loading' ? 'Generando…' :
    state === 'done'    ? 'Descargado' :
    state === 'error'   ? 'Reintentar descarga' :
    'Descargar registro contable';

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={state === 'loading'}
      className="chat-download-btn"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 12px',
        marginTop: 8,
        borderRadius: 8,
        border: '1px solid currentColor',
        background: 'transparent',
        cursor: state === 'loading' ? 'wait' : 'pointer',
        font: 'inherit',
        opacity: state === 'loading' ? 0.6 : 1,
      }}
    >
      <Download size={14} />
      <span>{label}</span>
    </button>
  );
}

// Recibe el texto del bot y devuelve un array de nodos React: tramos de
// markdown intercalados con botones de descarga donde aparezcan markers.
function renderBotText(text) {
  if (!text || !text.includes('[DESCARGAR_REGISTRO:')) {
    return (
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text || ''}</ReactMarkdown>
    );
  }

  const parts = [];
  let lastIndex = 0;
  let match;
  // Reset lastIndex porque el regex tiene flag /g.
  MARKER_REGEX.lastIndex = 0;
  while ((match = MARKER_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'md', value: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: 'btn', procesoId: match[1] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push({ type: 'md', value: text.slice(lastIndex) });
  }

  return parts.map((p, i) =>
    p.type === 'md' ? (
      <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>{p.value}</ReactMarkdown>
    ) : (
      <DownloadRegistroButton key={i} procesoId={p.procesoId} />
    ),
  );
}

export default function MessageBubble({ message }) {
  const isUser = message.sender === 'user';
  return (
    <div className={`message-wrapper animate-fade-in ${isUser ? 'user' : 'yoko'}`}>
      <div className="message-bubble">
        {message.isLoading ? (
          <div className="loading-dots"><span /><span /><span /></div>
        ) : isUser ? (
          <div style={{ whiteSpace: 'pre-wrap' }}>{message.text}</div>
        ) : (
          <div className="markdown-content">
            {renderBotText(message.text)}
          </div>
        )}
      </div>
      <span className="message-icon">
        {isUser
          ? <User size={14} />
          : <img src={APP_LOGO} alt={APP_NAME} className="message-logo-image" />}
      </span>
    </div>
  );
}
