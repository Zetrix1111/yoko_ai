/**
 * src/features/chat/BackendSwitch.jsx
 *
 * Segmented control con dos opciones (Managed | Tradicional) para que el
 * usuario alterne entre los dos cerebros del chat por request. Vive en el
 * header del ChatScreen, al lado del estado "Yoko • En línea".
 *
 * Valor sigue la misma convención que el resto del repo:
 *   - "managed_agents" → Anthropic Claude Managed Agents (con skills + tools).
 *   - "openai"         → flujo legacy con GPT-4.1-mini.
 *
 * El click invoca `onChange(next)` del parent (useChat.switchBackend), que
 * resuelve confirmación (si hay conversación en curso), reset de mensajes,
 * y persistencia en localStorage.
 */
export default function BackendSwitch({ value, onChange }) {
  return (
    <div className="chat-backend-switch" role="radiogroup" aria-label="Cerebro IA">
      <button
        type="button"
        role="radio"
        aria-checked={value === 'managed_agents'}
        className={`cbs-option ${value === 'managed_agents' ? 'active' : ''}`}
        onClick={() => onChange('managed_agents')}
        title="Claude Managed Agents (con skills y custom tools)"
      >
        Managed
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={value === 'openai'}
        className={`cbs-option ${value === 'openai' ? 'active' : ''}`}
        onClick={() => onChange('openai')}
        title="OpenAI tradicional (GPT-4.1-mini, legacy)"
      >
        Tradicional
      </button>
    </div>
  );
}
