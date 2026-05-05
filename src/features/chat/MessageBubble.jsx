import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User } from 'lucide-react';
import { APP_NAME, APP_LOGO } from '../../shared/branding';

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
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
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
