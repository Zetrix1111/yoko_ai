import { useState } from 'react';
import { Eye, Loader2 } from 'lucide-react';
import { getJsonAuth, API } from '../../../../../shared/api';

/**
 * Botón "Ver prompt generado" + dropdown que muestra el system prompt
 * resultante para el tenant actual. Hace GET a un endpoint del backend
 * (no implementado en este iter — gracefully muestra "próximamente"
 * si el endpoint devuelve 404 o el path no está definido en API).
 */
export default function PreviewPrompt({ empresaId }) {
  const [estado, setEstado] = useState('idle'); // 'idle' | 'loading' | 'ok' | 'unavailable' | 'error'
  const [prompt, setPrompt] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const previewUrl = API.SALES_PROMPT_PREVIEW;

  const cargar = async () => {
    if (!previewUrl) {
      setEstado('unavailable');
      return;
    }
    setEstado('loading');
    setErrorMsg('');
    try {
      const data = await getJsonAuth(`${previewUrl}?empresa_id=${encodeURIComponent(empresaId || '')}`);
      setPrompt(data?.prompt || '');
      setEstado('ok');
    } catch (err) {
      const msg = String(err?.message || err);
      if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
        setEstado('unavailable');
      } else {
        setEstado('error');
        setErrorMsg(msg);
      }
    }
  };

  return (
    <div className="via-preview-prompt-wrapper">
      <button
        type="button"
        className="vom-btn vom-btn-ghost"
        onClick={cargar}
        disabled={estado === 'loading'}
      >
        {estado === 'loading' ? <Loader2 size={14} className="spin" /> : <Eye size={14} />}
        {estado === 'loading' ? ' Generando preview...' : ' Ver prompt generado'}
      </button>

      {estado === 'unavailable' && (
        <div className="via-preview-prompt-msg">
          Función disponible próximamente. La preview del prompt requiere un endpoint
          adicional que se va a habilitar en una próxima versión.
        </div>
      )}

      {estado === 'error' && (
        <div className="via-preview-prompt-msg via-preview-prompt-msg-error">
          No se pudo generar el preview: {errorMsg}
        </div>
      )}

      {estado === 'ok' && prompt && (
        <pre className="via-preview-prompt">{prompt}</pre>
      )}
    </div>
  );
}
