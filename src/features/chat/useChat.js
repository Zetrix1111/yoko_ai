import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { postJson, postForm, API } from '../../shared/api';
import { tenantConfig } from '../../tenants';

export function useChat(user) {
  const navigate = useNavigate();
  const agentName = tenantConfig.agent.name;
  const greeting = user?.nombre
    ? `¡Hola, ${user.nombre}! Soy tu asistente inteligente. Puedo ayudarte a ejecutar procesos como rendiciones, caja chica y pagos. ¿Qué deseas hacer hoy?`
    : `¡Hola! Soy tu asistente inteligente. Puedo ayudarte a ejecutar procesos como rendiciones, caja chica y pagos. ¿Qué deseas hacer hoy?`;

  const [messages, setMessages] = useState([{
    id: crypto.randomUUID(),
    text: greeting,
    sender: 'yoko',
  }]);
  const [isUploading, setIsUploading] = useState(false);

  const sendMessage = useCallback(async (text, files) => {
    if (!text.trim() && files.length === 0) return;

    let displayText = text;
    if (files.length > 0) {
      displayText += displayText
        ? `\n[${files.length} archivo(s) adjunto(s)]`
        : `[${files.length} archivo(s) adjunto(s)]`;
    }

    setMessages((prev) => [...prev, {
      id: crypto.randomUUID(),
      text: displayText,
      sender: 'user',
    }]);

    // Un ID único por turno (mensaje). Todos los archivos de ESTE envío
    // comparten este ID. Make lo usa para matchear: los files que llegan
    // al webhook de uploads vs. el mensaje que llega al webhook del chat.
    const messageId = crypto.randomUUID();
    let batchId = null;

    // Fase 1: subida de archivos
    if (files.length > 0) {
      batchId = messageId;
      setIsUploading(true);

      const uploadMsgId = crypto.randomUUID();
      setMessages((prev) => [...prev, {
        id: uploadMsgId,
        text: 'Preparando subida...',
        sender: 'yoko',
        isLoading: true,
      }]);

      try {
        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          const formData = new FormData();
          formData.append('file', file);
          formData.append('batchId', batchId);
          formData.append('fileName', file.name);

          setMessages((prev) => prev.map(msg =>
            msg.id === uploadMsgId
              ? { ...msg, text: `Subiendo archivo ${i + 1} de ${files.length}...` }
              : msg
          ));

          await postForm(API.UPLOAD, formData);
        }
        setMessages((prev) => prev.filter(msg => msg.id !== uploadMsgId));
      } catch (err) {
        console.error('Error subiendo archivos:', err);
        setMessages((prev) => prev.map(msg =>
          msg.id === uploadMsgId
            ? { ...msg, text: 'Hubo un error al subir los archivos.', isLoading: false }
            : msg
        ));
        setIsUploading(false);
        return;
      }
      setIsUploading(false);
    }

    // Fase 2: IA
    const loadingId = crypto.randomUUID();
    setMessages((prev) => [...prev, {
      id: loadingId,
      text: '',
      sender: 'yoko',
      isLoading: true,
    }]);

    try {
      const apiMessages = [...messages, { id: 'temp', text, sender: 'user' }]
        .filter(m => !m.isLoading)
        .map(m => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.text
        }));

      const payload = {
        user: user || {},
        messages: apiMessages
      };

      const data = await postJson(API.CHAT, payload);
      
      let yokoText = '';
      if (typeof data === 'string') {
        yokoText = data;
        if (yokoText === 'Accepted') {
          yokoText = 'He recibido tu mensaje (Make respondió "Accepted"). Recuerda configurar el módulo "Webhook Response".';
        }
      } else {
        yokoText = data.text || data.response || data.message || data.respuesta || JSON.stringify(data);
        
        // Handle navigation action from OpenAI backend
        if (data.action?.type === 'navigate' && data.action.path) {
          navigate(data.action.path);
        }
      }

      setMessages((prev) => prev.map(msg =>
        msg.id === loadingId ? { ...msg, text: yokoText, isLoading: false } : msg
      ));
    } catch (err) {
      console.error('Error webhook:', err);
      setMessages((prev) => prev.map(msg =>
        msg.id === loadingId
          ? { ...msg, text: 'Lo siento, hubo un problema al conectar con el servidor.', isLoading: false }
          : msg
      ));
    }
  }, [user, messages, navigate]);

  return { messages, sendMessage, isUploading };
}
