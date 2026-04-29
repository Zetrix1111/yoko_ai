import { useRef, useEffect, useState } from 'react';
import { LayoutGrid, UploadCloud, LogOut } from 'lucide-react';
import { tenantConfig, tenantLogo } from '../../tenants';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import { useChat } from './useChat';

export default function ChatScreen({ user, onOpenModules, onLogout }) {
  const { messages, sendMessage, isUploading } = useChat(user);
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef(null);
  const dragCounter = useRef(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- Drag & Drop handlers ---
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
      setFiles(prev => [...prev, ...dropped]);
    }
    e.dataTransfer?.clearData?.();
  };

  return (
    <div
      className="chat-wrapper glass-panel"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div className="drag-overlay">
          <div className="drag-overlay-content">
            <UploadCloud size={52} />
            <p className="drag-overlay-title">Suelta los archivos aquí</p>
            <p className="drag-overlay-subtitle">Se adjuntarán a tu próximo mensaje</p>
          </div>
        </div>
      )}

      <header className="chat-header border-b">
        <div className="header-info">
          <div className="avatar yoko-avatar">
            <img src={tenantLogo} alt={`${tenantConfig.agent.name} Logo`} className="logo-image" />
          </div>
          <div>
            <h1 className="agent-name">{tenantConfig.agent.name}</h1>
            <p className="agent-status">En línea</p>
          </div>
        </div>
        <div className="header-actions">
          <button
            className="icon-btn"
            onClick={onLogout}
            title="Cerrar sesión"
            aria-label="Cerrar sesión"
          >
            <LogOut size={20} />
          </button>
          <button className="icon-btn lg:hidden" onClick={onOpenModules}>
            <LayoutGrid size={20} />
          </button>
        </div>
      </header>

      <main className="messages-area">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </main>

      <footer className="chat-footer border-t">
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
