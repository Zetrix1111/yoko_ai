import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Download, ClipboardList } from 'lucide-react';
import { APP_NAME, APP_LOGO } from '../../shared/branding';
import { API, getAuthToken } from '../../shared/api';

// Sistema de "markers" emitidos por el agent en su respuesta de texto. Cada
// marker es una línea exacta que el frontend regex-detecta y reemplaza por
// un componente interactivo (botón de descarga, link a otra pantalla, etc.).
//
// Para agregar un marker nuevo:
//   1) Agregá una entrada en MARKERS con su `regex` y `Component`.
//   2) El backend debe devolver al agent una instrucción explícita
//      ("INCLUÍ al final esta línea exacta: [...]") y el SKILL.md debe
//      reforzarlo con ejemplo correcto + incorrecto.
const MARKERS = [
  {
    id:        'descargar',
    regex:     /\[DESCARGAR_REGISTRO:([a-zA-Z0-9_-]+)\]/g,
    Component: DownloadRegistroButton,
  },
  {
    id:        'revision',
    regex:     /\[ABRIR_REVISION:([a-zA-Z0-9_-]+)\]/g,
    Component: OpenRevisionButton,
  },
];

// ─────────────────────────────────────────────────────────────────────────
// Botón: Descargar registro contable
// ─────────────────────────────────────────────────────────────────────────

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
      className="chat-action-btn"
      style={chatActionBtnStyle(state)}
    >
      <Download size={14} />
      <span>{label}</span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Botón: Abrir revisión de extracción
// ─────────────────────────────────────────────────────────────────────────

function OpenRevisionButton({ procesoId }) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(
      `/modulos/facturas-inteligentes?section=revision&proceso_id=${encodeURIComponent(procesoId)}`,
    );
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="chat-action-btn"
      style={chatActionBtnStyle('idle')}
    >
      <ClipboardList size={14} />
      <span>Abrir revisión de extracción</span>
    </button>
  );
}

function chatActionBtnStyle(state) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '6px 12px',
    marginTop: 8,
    marginRight: 6,
    borderRadius: 8,
    border: '1px solid currentColor',
    background: 'transparent',
    cursor: state === 'loading' ? 'wait' : 'pointer',
    font: 'inherit',
    opacity: state === 'loading' ? 0.6 : 1,
  };
}

// ─────────────────────────────────────────────────────────────────────────
// Render del texto del bot: splitea por markers y renderiza el componente
// correspondiente entre los tramos de markdown.
// ─────────────────────────────────────────────────────────────────────────

function findFirstMarker(text, fromIndex) {
  // Busca la primera ocurrencia (en orden de aparición en el texto) de
  // CUALQUIER marker definido. Devuelve {index, length, marker, captured}
  // o null.
  let best = null;
  for (const marker of MARKERS) {
    marker.regex.lastIndex = fromIndex;
    const m = marker.regex.exec(text);
    if (!m) continue;
    if (best === null || m.index < best.index) {
      best = {
        index:    m.index,
        length:   m[0].length,
        marker,
        captured: m[1],
      };
    }
  }
  return best;
}

function renderBotText(text) {
  if (!text) return <ReactMarkdown remarkPlugins={[remarkGfm]}>{''}</ReactMarkdown>;

  // Si ningún marker está presente, render directo.
  if (!MARKERS.some(({ regex }) => { regex.lastIndex = 0; return regex.test(text); })) {
    return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>;
  }

  const parts = [];
  let cursor = 0;
  while (cursor < text.length) {
    const hit = findFirstMarker(text, cursor);
    if (!hit) {
      parts.push({ type: 'md', value: text.slice(cursor) });
      break;
    }
    if (hit.index > cursor) {
      parts.push({ type: 'md', value: text.slice(cursor, hit.index) });
    }
    parts.push({
      type:      'btn',
      Component: hit.marker.Component,
      captured:  hit.captured,
      key:       `${hit.marker.id}-${hit.index}`,
    });
    cursor = hit.index + hit.length;
  }

  return parts.map((p, i) =>
    p.type === 'md'
      ? <ReactMarkdown key={`md-${i}`} remarkPlugins={[remarkGfm]}>{p.value}</ReactMarkdown>
      : <p.Component key={p.key} procesoId={p.captured} />,
  );
}

// ─────────────────────────────────────────────────────────────────────────
// MessageBubble
// ─────────────────────────────────────────────────────────────────────────

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
