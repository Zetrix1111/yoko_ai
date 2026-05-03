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

    // Fase 1: procesar archivos (extraer campos + subir si aplica)
    let camposExtraidos = null;

    if (files.length > 0) {
      setIsUploading(true);

      const uploadMsgId = crypto.randomUUID();
      setMessages((prev) => [...prev, {
        id: uploadMsgId,
        text: `Analizando ${files.length > 1 ? files.length + ' archivos' : files[0].name}...`,
        sender: 'yoko',
        isLoading: true,
      }]);

      try {
        // Procesar cada archivo: primero parse_file para extraer campos
        const todosLosCampos = [];
        for (let i = 0; i < files.length; i++) {
          const file = files[i];

          // Actualizar estado visual
          setMessages((prev) => prev.map(msg =>
            msg.id === uploadMsgId
              ? { ...msg, text: `Leyendo archivo ${i + 1} de ${files.length}: ${file.name}...` }
              : msg
          ));

          // Llamar a parse_file para extraer campos con IA
          const formData = new FormData();
          formData.append('file', file);
          formData.append('fileName', file.name);

          try {
            const res = await fetch(API.PARSE_FILE, { method: 'POST', body: formData });
            if (res.ok) {
              const parsed = await res.json();
              if (parsed.campos) {
                todosLosCampos.push(parsed.campos);
              }
            }
          } catch (parseErr) {
            console.warn('parse_file falló para', file.name, parseErr);
          }
        }

        // Consolidar campos extraídos (usar el primero con valor no-null)
        if (todosLosCampos.length > 0) {
          camposExtraidos = todosLosCampos.reduce((acc, cur) => {
            Object.keys(cur).forEach(k => {
              if (!acc[k] && cur[k] !== null && cur[k] !== undefined) {
                acc[k] = cur[k];
              }
            });
            return acc;
          }, {});
        }

        setMessages((prev) => prev.filter(msg => msg.id !== uploadMsgId));
      } catch (err) {
        console.error('Error procesando archivos:', err);
        setMessages((prev) => prev.map(msg =>
          msg.id === uploadMsgId
            ? { ...msg, text: 'Hubo un error al analizar el archivo.', isLoading: false }
            : msg
        ));
        setIsUploading(false);
        return;
      }
      setIsUploading(false);
    }

    // Fase 2: enviar a la IA con los campos extraídos como contexto adicional
    const loadingId = crypto.randomUUID();
    setMessages((prev) => [...prev, {
      id: loadingId,
      text: '',
      sender: 'yoko',
      isLoading: true,
    }]);

    try {
      // Si se extrajeron campos del archivo, los incluimos en el mensaje del usuario
      let mensajeConContexto = text;
      if (camposExtraidos) {
        const camposStr = Object.entries(camposExtraidos)
          .filter(([k, v]) => k !== 'confianza' && v !== null && v !== undefined && v !== '')
          .map(([k, v]) => `  - ${k}: ${v}`)
          .join('\n');

        const instruccion = 'INSTRUCCIÓN SISTEMA: Los datos anteriores fueron extraídos automáticamente del archivo adjunto. Tratalos como CONFIRMADOS. NO vuelvas a preguntar por ellos. Identifica qué campos obligatorios faltan (plazo, motivo, moneda, obra, total_general, tipo_gasto, detalle_gasto, aprobador_id) y pregunta SOLO por los que no estén en la lista de arriba.';
        
        mensajeConContexto = text
          ? `${text}\n\n[Datos extraídos del archivo adjunto:\n${camposStr}]\n\n${instruccion}`
          : `[Datos extraídos del archivo adjunto:\n${camposStr}]\n\n${instruccion}`;
      }

      const apiMessages = [
        ...messages,
        { id: 'temp', text: mensajeConContexto, sender: 'user' }
      ]
        .filter(m => !m.isLoading)
        .map(m => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.text
        }));

      const payload = {
        user: user || {},
        messages: apiMessages,
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
          const params = data.action.params;
          const queryString = params && Object.keys(params).length > 0
            ? '?' + new URLSearchParams(params).toString()
            : '';
          navigate(data.action.path + queryString);
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
