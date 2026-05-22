import { useRef, useEffect, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { APP_NAME, APP_LOGO } from '../../shared/branding';
import MessageBubble from '../chat/MessageBubble';
import ChatInput from '../chat/ChatInput';
import BackendSwitch from '../chat/BackendSwitch';
import { useChat } from '../chat/useChat';
import './ErpAIPanel.css';

/**
 * Panel IA derecho del shell ERP. Vive en `ErpShell` y NO se desmonta
 * al cambiar de ruta — por eso la conversación se mantiene cuando el
 * usuario navega entre módulos.
 *
 * Diseño: estilo "Claude desktop pegado a la derecha" — header
 * compacto, body de mensajes con scroll, footer con input flotante.
 *
 * Reusa los componentes del chat clásico (`MessageBubble`, `ChatInput`,
 * `BackendSwitch`) y el hook `useChat` — la lógica del backend, polling
 * async, drag&drop, markers `[DESCARGAR_REGISTRO:X]`, etc., no cambia.
 */
export default function ErpAIPanel({ user }) {
  const {
    messages,
    sendMessage,
    isUploading,
    currentBackend,
    switchBackend,
  } = useChat(user);

  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef(null);
  const dragCounter = useRef(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Drag & drop sobre el panel entero ──
  const hasFiles = (e) =>
    Array.from(e.dataTransfer?.types || []).includes('Files');

  const handleDragEnter = (e) => {
    e.preventDefault();
    if (!hasFiles(e)) return;
    dragCounter.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounter.current = Math.max(0, dragCounter.current - 1);
    if (dragCounter.current === 0) setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (hasFiles(e)) e.dataTransfer.dropEffect = 'copy';
  };

  const handleDrop = (e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);
    if (isUploading) return;
    const dropped = Array.from(e.dataTransfer?.files || []);
    if (dropped.length > 0) {
      setFiles((prev) => [...prev, ...dropped]);
    }
    e.dataTransfer?.clearData?.();
  };

  return (
    <div
      className="erp-ai-panel"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div className="erp-ai-drag-overlay">
          <UploadCloud size={36} />
          <p>Suelte los archivos aquí</p>
        </div>
      )}

      <header className="erp-ai-header">
        <div className="erp-ai-brand">
          <div className="erp-ai-avatar">
            <img src={APP_LOGO} alt={APP_NAME} />
          </div>
          <div className="erp-ai-brand-info">
            <span className="erp-ai-brand-name">{APP_NAME}</span>
            <span className="erp-ai-brand-status">
              <span className="erp-ai-dot" /> en línea
            </span>
          </div>
        </div>
        <BackendSwitch value={currentBackend} onChange={switchBackend} />
      </header>

      <main className="erp-ai-messages">
        {messages.length === 0 ? (
          <div className="erp-ai-empty">
            <p className="erp-ai-empty-title">¿En qué puedo ayudarle hoy?</p>
            <p className="erp-ai-empty-sub">
              Suba un documento, realice una consulta o solicite una acción.
            </p>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        <div ref={messagesEndRef} />
      </main>

      <footer className="erp-ai-footer">
        <ChatInput
          onSend={sendMessage}
          disabled={isUploading}
          files={files}
          setFiles={setFiles}
        />
      </footer>
    </div>
  );
}
