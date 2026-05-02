import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User } from 'lucide-react';
import { tenantConfig, appLogo } from '../../tenants';

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
          : <img src={appLogo} alt={tenantConfig.agent.name} className="message-logo-image" />}
      </span>
    </div>
  );
}
