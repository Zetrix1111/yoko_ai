import { useState, useRef, useEffect } from 'react';
import { Send, User, MoreVertical, Paperclip, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import yokoLogo from './assets/logo.png';
import './App.css';

const WEBHOOK_UPLOAD = import.meta.env.VITE_WEBHOOK_UPLOAD;
const WEBHOOK_AI = import.meta.env.VITE_WEBHOOK_AI;
const WEBHOOK_AUTH = import.meta.env.VITE_WEBHOOK_AUTH;
const CHANNEL = import.meta.env.VITE_CHANNEL;

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [dni, setDni] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [files, setFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isLoggedIn) {
      scrollToBottom();
    }
  }, [messages, isLoggedIn]);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (dni.length !== 8) {
      setLoginError('Ingresa tu DNI de 8 dígitos.');
      return;
    }

    setIsAuthenticating(true);
    setLoginError('');

    try {
      const response = await fetch(WEBHOOK_AUTH, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dni }),
      });

      if (!response.ok) throw new Error('Error de red');

      const data = await response.json();

      if (data.authorized) {
        const nombre = data.nombre || '';
        setSessionId(`${dni}-${Date.now()}`);
        setMessages([{
          id: crypto.randomUUID(),
          text: `¡Hola${nombre ? `, ${nombre}` : ''}! Soy Yoko, tu asistente personal de IA. ¿En qué puedo ayudarte hoy?`,
          sender: 'yoko',
        }]);
        setIsLoggedIn(true);
      } else {
        setLoginError('DNI no autorizado. Contacta al administrador.');
      }
    } catch (error) {
      setLoginError('Error al verificar. Intenta de nuevo.');
    } finally {
      setIsAuthenticating(false);
    }
  };

  const handleDniChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 8);
    setDni(value);
    if (loginError) setLoginError('');
  };

  const handleFileSelect = (e) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles(prev => [...prev, ...selectedFiles]);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (indexToRemove) => {
    setFiles(prev => prev.filter((_, index) => index !== indexToRemove));
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() && files.length === 0) return;

    const userText = input;
    const currentFiles = [...files];

    let messageText = userText;
    if (currentFiles.length > 0) {
      messageText += messageText
        ? `\n[${currentFiles.length} archivo(s) adjunto(s)]`
        : `[${currentFiles.length} archivo(s) adjunto(s)]`;
    }

    const userMessage = { id: crypto.randomUUID(), text: messageText, sender: 'user' };
    setMessages((prev) => [...prev, userMessage]);

    setInput('');
    setFiles([]);

    let batchId = null;

    // Fase 1: Subida de archivos (Webhook A)
    if (currentFiles.length > 0) {
      batchId = `Lote-${Date.now()}`;
      setIsUploading(true);

      const uploadMsgId = crypto.randomUUID();
      setMessages((prev) => [...prev, { id: uploadMsgId, text: 'Preparando subida...', sender: 'yoko', isLoading: true }]);

      try {
        for (let i = 0; i < currentFiles.length; i++) {
          const file = currentFiles[i];
          const formData = new FormData();
          formData.append('file', file);
          formData.append('batchId', batchId);
          formData.append('fileName', file.name);

          setMessages((prev) => prev.map(msg =>
            msg.id === uploadMsgId ? { ...msg, text: `Subiendo archivo ${i + 1} de ${currentFiles.length}...` } : msg
          ));

          const uploadRes = await fetch(WEBHOOK_UPLOAD, {
            method: 'POST',
            body: formData,
          });

          if (!uploadRes.ok) {
            throw new Error(`Error al subir archivo ${i + 1}: HTTP ${uploadRes.status}`);
          }
        }

        setMessages((prev) => prev.filter(msg => msg.id !== uploadMsgId));
        setIsUploading(false);

      } catch (error) {
        console.error('Error subiendo archivos:', error);
        setMessages((prev) => prev.map(msg =>
          msg.id === uploadMsgId ? { ...msg, text: 'Hubo un error al subir los archivos.', isLoading: false } : msg
        ));
        setIsUploading(false);
        return;
      }
    }

    // Fase 2: Procesamiento de IA (Webhook B)
    const loadingId = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: loadingId, text: '', sender: 'yoko', isLoading: true }]);

    try {
      const payload = {
        canal: CHANNEL,
        message: userText,
        has_attachment: batchId !== null,
        session_id: sessionId,
      };
      if (batchId) payload.batchId = batchId;

      const response = await fetch(WEBHOOK_AI, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error(`Error de red al conectar con Make: HTTP ${response.status}`);

      const contentType = response.headers.get('content-type');
      let yokoText = '';

      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        yokoText = data.response || data.text || data.message || data.respuesta || JSON.stringify(data);
      } else {
        yokoText = await response.text();
      }

      if (yokoText === 'Accepted') {
        yokoText = 'He recibido tu mensaje (Make respondió "Accepted"). Recuerda configurar el módulo "Webhook Response".';
      }

      setMessages((prev) => prev.map(msg =>
        msg.id === loadingId ? { ...msg, text: yokoText, isLoading: false } : msg
      ));

    } catch (error) {
      console.error('Error webhook:', error);
      setMessages((prev) => prev.map(msg =>
        msg.id === loadingId ? { ...msg, text: 'Lo siento, hubo un problema al conectar con el servidor.', isLoading: false } : msg
      ));
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="app-container login-container">
        <div className="login-card glass-panel animate-fade-in">
          <div className="login-logo-wrapper yoko-avatar">
            <img src={yokoLogo} alt="Yoko Logo" className="logo-image" />
          </div>
          <h1 className="login-title">Yoko</h1>
          <p className="login-subtitle">Asistente de IA para Procesos</p>
          <form onSubmit={handleLogin} className="login-form">
            <input
              type="text"
              inputMode="numeric"
              value={dni}
              onChange={handleDniChange}
              placeholder="Ingresa tu DNI"
              className="login-input"
              maxLength={8}
              autoFocus
            />
            {loginError && <p className="login-error">{loginError}</p>}
            <button
              type="submit"
              className="login-btn"
              disabled={isAuthenticating || dni.length !== 8}
            >
              {isAuthenticating ? (
                <span className="login-loading">
                  <span /><span /><span />
                </span>
              ) : 'Ingresar'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="chat-wrapper glass-panel">
        <header className="chat-header border-b">
          <div className="header-info">
            <div className="avatar yoko-avatar">
              <img src={yokoLogo} alt="Yoko Logo" className="logo-image" />
            </div>
            <div>
              <h1 className="agent-name">Yoko</h1>
              <p className="agent-status">En línea</p>
            </div>
          </div>
          <button className="icon-btn">
            <MoreVertical size={20} />
          </button>
        </header>

        <main className="messages-area">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`message-wrapper animate-fade-in ${msg.sender === 'user' ? 'user' : 'yoko'}`}
            >
              <div className="message-bubble">
                {msg.isLoading ? (
                  <div className="loading-dots">
                    <span /><span /><span />
                  </div>
                ) : msg.sender === 'user' ? (
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
                ) : (
                  <div className="markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.text}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
              <span className="message-icon">
                {msg.sender === 'user' ? (
                  <User size={14} />
                ) : (
                  <img src={yokoLogo} alt="Yoko" className="message-logo-image" />
                )}
              </span>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </main>

        <footer className="chat-footer border-t">
          {files.length > 0 && (
            <div className="files-preview">
              {files.map((file, idx) => (
                <div key={idx} className="file-pill">
                  <span className="file-name">{file.name}</span>
                  <button type="button" className="remove-file-btn" onClick={() => removeFile(idx)}>
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <form onSubmit={handleSend} className="input-form">
            <button
              type="button"
              className="attach-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              <Paperclip size={20} />
            </button>
            <input
              type="file"
              multiple
              hidden
              ref={fileInputRef}
              onChange={handleFileSelect}
            />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Escribe tu mensaje a Yoko..."
              className="chat-input"
              disabled={isUploading}
            />
            <button
              type="submit"
              className="send-button"
              disabled={(!input.trim() && files.length === 0) || isUploading}
            >
              <Send size={18} />
            </button>
          </form>
        </footer>
      </div>
    </div>
  );
}

export default App;
