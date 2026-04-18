import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MoreVertical, Paperclip, X } from 'lucide-react';
import yokoLogo from './assets/logo.png';
import './App.css';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [messages, setMessages] = useState([
    { id: 1, text: '¡Hola! Soy Yoko, tu asistente personal de IA. ¿En qué puedo ayudarte hoy?', sender: 'yoko' }
  ]);
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

  const handleFileSelect = (e) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles(prev => [...prev, ...selectedFiles]);
    }
    // Resetear el input para permitir seleccionar el mismo archivo de nuevo si se borra
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
    
    // Mostrar mensaje del usuario en la UI
    let messageText = userText;
    if (currentFiles.length > 0) {
      messageText += messageText ? `\n[${currentFiles.length} archivo(s) adjunto(s)]` : `[${currentFiles.length} archivo(s) adjunto(s)]`;
    }
    
    const userMessage = { id: Date.now(), text: messageText, sender: 'user' };
    setMessages((prev) => [...prev, userMessage]);
    
    setInput('');
    setFiles([]);

    let batchId = null;

    // Fase 1: Subida de archivos (Webhook A)
    if (currentFiles.length > 0) {
      batchId = `Lote-${Date.now()}`;
      setIsUploading(true);
      
      const uploadMsgId = Date.now() + 1;
      setMessages((prev) => [...prev, { id: uploadMsgId, text: `Preparando subida...`, sender: 'yoko', isLoading: true }]);
      
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

          await fetch('https://hook.us2.make.com/6x3b6hxrufzyy086hyq4kaxbak0386dl', {
            method: 'POST',
            body: formData,
          });
        }
        
        // Quitar mensaje de subida
        setMessages((prev) => prev.filter(msg => msg.id !== uploadMsgId));
        setIsUploading(false);
        
      } catch (error) {
        console.error('Error subiendo archivos:', error);
        setMessages((prev) => prev.map(msg => 
          msg.id === uploadMsgId ? { ...msg, text: 'Hubo un error al subir los archivos.', isLoading: false } : msg
        ));
        setIsUploading(false);
        return; // Detener flujo si falla la subida
      }
    }

    // Fase 2: Procesamiento de IA (Webhook B)
    const loadingId = Date.now() + 2;
    setMessages((prev) => [...prev, { id: loadingId, text: 'Pensando...', sender: 'yoko', isLoading: true }]);

    try {
      const payload = { 
        message: userText,
        has_attachment: batchId !== null
      };
      if (batchId) payload.batchId = batchId;

      const response = await fetch('https://hook.us2.make.com/1dkv51qxgy6ji0b2hne8ixqjyfdbogeq', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error('Error de red al conectar con Make');

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
          <button 
            className="login-btn" 
            onClick={() => setIsLoggedIn(true)}
          >
            Iniciar Sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="chat-wrapper glass-panel">
        {/* Header */}
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

        {/* Messages Area */}
        <main className="messages-area">
          {messages.map((msg) => (
            <div 
              key={msg.id} 
              className={`message-wrapper animate-fade-in ${msg.sender === 'user' ? 'user' : 'yoko'}`}
            >
              <div className="message-bubble" style={{ whiteSpace: 'pre-wrap' }}>
                {msg.text}
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

        {/* Input Area */}
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
              disabled={( !input.trim() && files.length === 0 ) || isUploading}
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
