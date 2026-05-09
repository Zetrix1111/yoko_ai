import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { API, postJsonAuth, postFormAuth } from '../../shared/api';

// Backend conversacional: openai (legacy) | managed_agents (Anthropic).
// Tiene que coincidir con la env var YOKO_BACKEND del backend; si no, los
// archivos se procesan dos veces (parse_file + skill yoko-facturas) o ninguna.
const YOKO_BACKEND = (import.meta.env.VITE_YOKO_BACKEND || 'openai').toLowerCase();
const IS_MANAGED_AGENTS = YOKO_BACKEND === 'managed_agents';

// Lee un File del browser y devuelve su contenido en base64 (sin el prefijo
// "data:<mime>;base64,"). Pensado para mandar adjuntos al backend Managed
// Agents que los reenvía al tool `yoko_procesar_archivos`.
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result || '';
      const idx = typeof dataUrl === 'string' ? dataUrl.indexOf(',') : -1;
      resolve(idx >= 0 ? dataUrl.slice(idx + 1) : '');
    };
    reader.onerror = () => reject(reader.error || new Error('FileReader error'));
    reader.readAsDataURL(file);
  });
}

export function useChat(user) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const greeting = user?.nombre
    ? `¡Hola, ${user.nombre}! Soy tu asistente inteligente. Puedo ayudarte a ejecutar procesos como rendiciones, caja chica y pagos. ¿Qué deseas hacer hoy?`
    : `¡Hola! Soy tu asistente inteligente. Puedo ayudarte a ejecutar procesos como rendiciones, caja chica y pagos. ¿Qué deseas hacer hoy?`;

  const [messages, setMessages] = useState([{
    id: crypto.randomUUID(),
    text: greeting,
    sender: 'yoko',
  }]);
  const [isUploading, setIsUploading] = useState(false);

  // Cuando el usuario vuelve al chat tras descargar el registro contable
  // desde la pantalla de Revisión (`/chat?facturas_done=proc-xxx`),
  // inyectamos un mensaje sintético del bot con el botón de re-descarga
  // listo. NO hacemos round-trip al backend: la descarga ya pasó, el
  // botón es solo para que el usuario tenga el registro a mano si lo
  // pierde. Limpiamos el query param para que un reload no re-inyecte.
  const facturasDoneHandledRef = useRef(false);
  useEffect(() => {
    const procesoId = searchParams.get('facturas_done');
    if (!procesoId) return;
    if (facturasDoneHandledRef.current) return;
    facturasDoneHandledRef.current = true;

    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        sender: 'yoko',
        text:
          '✅ Listo. Descargaste el registro contable del proceso `' +
          procesoId + '`. Si necesitás bajarlo otra vez:\n\n' +
          '[DESCARGAR_REGISTRO:' + procesoId + ']',
      },
    ]);

    // Limpiar el query param sin agregar entrada al history.
    const next = new URLSearchParams(searchParams);
    next.delete('facturas_done');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

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

    // Fase 1: procesar archivos.
    //   - Backend "managed_agents": codifica los archivos a base64 y los manda
    //     como attachments dentro del payload del chat. El agent activa el
    //     skill correspondiente (yoko-facturas) y llama el tool con los archivos.
    //   - Backend "openai" (legacy): pre-procesa cada archivo con parse_file
    //     para extraer campos y los inyecta como contexto en el mensaje.
    let camposExtraidos = null;
    let attachmentsForChat = null;

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
        if (IS_MANAGED_AGENTS) {
          // Codificar todos los archivos a base64. El agent decide qué hacer.
          const encoded = [];
          for (let i = 0; i < files.length; i++) {
            const file = files[i];
            setMessages((prev) => prev.map(msg =>
              msg.id === uploadMsgId
                ? { ...msg, text: `Cargando archivo ${i + 1} de ${files.length}: ${file.name}...` }
                : msg
            ));
            const content_b64 = await fileToBase64(file);
            encoded.push({ filename: file.name, content_b64 });
          }
          attachmentsForChat = encoded;
          setMessages((prev) => prev.filter(msg => msg.id !== uploadMsgId));
        } else {
          // OpenAI legacy: parse_file por archivo, consolidar campos extraídos.
          const todosLosCampos = [];
          for (let i = 0; i < files.length; i++) {
            const file = files[i];
            setMessages((prev) => prev.map(msg =>
              msg.id === uploadMsgId
                ? { ...msg, text: `Leyendo archivo ${i + 1} de ${files.length}: ${file.name}...` }
                : msg
            ));

            const formData = new FormData();
            formData.append('file', file);
            formData.append('fileName', file.name);

            try {
              const parsed = await postFormAuth(API.PARSE_FILE, formData);
              if (parsed && parsed.campos) {
                todosLosCampos.push(parsed.campos);
              }
            } catch (parseErr) {
              console.warn('parse_file falló para', file.name, parseErr);
            }
          }

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
        }
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

      // En modo managed_agents, Anthropic persiste el historial server-side,
      // así que solo mandamos el último mensaje del usuario. En modo openai
      // legacy, mandamos el array completo (necesario para el tool-calling loop).
      const lastUserMsg = { role: 'user', content: mensajeConContexto };
      const apiMessages = IS_MANAGED_AGENTS
        ? [lastUserMsg]
        : [
            ...messages.filter(m => !m.isLoading).map(m => ({
              role: m.sender === 'user' ? 'user' : 'assistant',
              content: m.text,
            })),
            lastUserMsg,
          ];

      const payload = {
        user: user || {},
        messages: apiMessages,
      };
      if (attachmentsForChat) {
        payload.attachments = attachmentsForChat;
      }

      const data = await postJsonAuth(API.CHAT, payload);
      
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
