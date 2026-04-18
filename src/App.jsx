import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MoreVertical } from 'lucide-react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { id: 1, text: '¡Hola! Soy Yoko, tu asistente personal de IA. ¿En qué puedo ayudarte hoy?', sender: 'yoko' }
  ]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { id: Date.now(), text: input, sender: 'user' };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    // Simulate Yoko's response
    setTimeout(() => {
      const yokoResponse = { 
        id: Date.now() + 1, 
        text: 'Estoy procesando tu solicitud. Por ahora esto es una simulación de mi respuesta.', 
        sender: 'yoko' 
      };
      setMessages((prev) => [...prev, yokoResponse]);
    }, 1000);
  };

  return (
    <div className="app-container">
      <div className="chat-wrapper glass-panel">
        {/* Header */}
        <header className="chat-header border-b">
          <div className="header-info">
            <div className="avatar yoko-avatar">
              <Bot size={24} />
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
              <div className="message-bubble">
                {msg.text}
              </div>
              <span className="message-icon">
                {msg.sender === 'user' ? <User size={14} /> : <Bot size={14} />}
              </span>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </main>

        {/* Input Area */}
        <footer className="chat-footer border-t">
          <form onSubmit={handleSend} className="input-form">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Escribe tu mensaje a Yoko..."
              className="chat-input"
            />
            <button 
              type="submit" 
              className="send-button"
              disabled={!input.trim()}
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
