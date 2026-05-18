import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { API, postJsonAuth, postFormAuth, getJsonAuth } from '../../shared/api';

// Backend conversacional: openai (legacy) | managed_agents (Anthropic).
// Antes era una constante a load-time (env var VITE_YOKO_BACKEND). Ahora
// el usuario puede alternar desde el header del chat (BackendSwitch), así
// que la decisión vive en state runtime + localStorage. El env var sigue
// siendo el default si el usuario nunca tocó el switch.
//
// Cada request lleva un header HTTP `X-Yoko-Backend` que el backend usa
// para decidir el cerebro — el body queda inalterado.
const DEFAULT_BACKEND = (import.meta.env.VITE_YOKO_BACKEND || 'openai').toLowerCase();
const BACKEND_STORAGE_KEY = 'yoko_backend_preference';

function readInitialBackend() {
  try {
    const stored = localStorage.getItem(BACKEND_STORAGE_KEY);
    if (stored === 'managed_agents' || stored === 'openai') return stored;
  } catch {
    // localStorage no disponible (incognito strict, etc.) → fallback al default.
  }
  return DEFAULT_BACKEND === 'managed_agents' ? 'managed_agents' : 'openai';
}

// Vercel impone un hard limit de 4.5MB por request body. 1 PDF promedio
// pesa ~750KB después de base64 inflation, así que 4 archivos ~3MB cabe
// holgado bajo ese límite. Si el usuario suelta más, los partimos en
// chunks de a 4 y los posteamos secuencialmente — el carrito server-side
// los acumula y el agent confirma cada chunk con su contador propio.
const CHUNK_SIZE = 4;

// Polling del task async cuando el backend devuelve `task_id`.
const POLL_INTERVAL_MS = 1500;
const MAX_POLLS = 200;  // 200 × 1.5s = 300s techo (5 min, igual que el worker)

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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

  const [messages, setMessages] = useState(() => []);
  const [isUploading, setIsUploading] = useState(false);
  const [currentBackend, setCurrentBackend] = useState(readInitialBackend);
  const isManaged = currentBackend === 'managed_agents';

  // Los módulos con tools conversacionales de extracción mandan attachments
  // en base64. El backend los acumula en carrito server-side y la tool del
  // skill decide cuándo procesarlos.
  const _modulos = (user?.empresa?.modulos) || [];
  const isFacturas = _modulos.includes('facturas-inteligentes');
  const isGestionCaja = _modulos.includes('gestion-caja');
  const useAttachmentsPath = isManaged || isFacturas || isGestionCaja;

  // Cambia el cerebro activo. Si ya hubo conversación, pide confirmación
  // porque el reset descarta el contexto visible. La session vieja del
  // backend anterior queda colgada server-side y expira sola por el TTL
  // de KV (4 hrs).
  const switchBackend = useCallback((next) => {
    if (next !== 'managed_agents' && next !== 'openai') return;
    if (next === currentBackend) return;

    const hasConversation = messages.length > 0;
    if (hasConversation) {
      const proceed = window.confirm(
        'Cambiar de cerebro reseteará la conversación actual. ¿Continuar?'
      );
      if (!proceed) return;
    }

    try {
      localStorage.setItem(BACKEND_STORAGE_KEY, next);
    } catch {
      // ignoramos errores de localStorage (storage lleno, modo strict, etc.)
    }
    setCurrentBackend(next);
    setMessages([]);
  }, [currentBackend, messages.length]);

  // Cuando el usuario vuelve al chat tras descargar el registro contable
  // desde la pantalla de Revisión (`/chat?facturas_done=proc-xxx`),
  // inyectamos un mensaje sintético del bot con el botón de re-descarga
  // listo. Limpiamos el query param para que un reload no re-inyecte.
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

    const next = new URLSearchParams(searchParams);
    next.delete('facturas_done');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  // ───────────────────────────────────────────────────────────────────
  // Polling del task async: pollea GET /api/chat?action=status&task_id=X
  // hasta done/error. Va actualizando el mensaje del bot en vivo (cada
  // poll que ve más texto, lo refresca → streaming UX gratis).
  // ───────────────────────────────────────────────────────────────────
  const pollTaskUntilDone = useCallback(async (taskId, loadingId) => {
    let lastText = '';
    for (let i = 0; i < MAX_POLLS; i++) {
      await sleep(POLL_INTERVAL_MS);
      let res;
      try {
        res = await getJsonAuth(
          `/api/chat?action=status&task_id=${encodeURIComponent(taskId)}`,
          { headers: { 'X-Yoko-Backend': currentBackend } },
        );
      } catch (err) {
        // Errores transitorios de red: seguir polleando hasta el techo.
        console.warn('[chat/status] poll error', err);
        continue;
      }

      // Streaming: si llegó más texto que el último visto, refrescar.
      if (res.text && res.text !== lastText) {
        lastText = res.text;
        setMessages((prev) => prev.map((m) =>
          m.id === loadingId
            ? { ...m, text: res.text, isLoading: false }
            : m
        ));
      }

      if (res.status === 'done') {
        // Asegurar que el render final tenga el texto definitivo.
        setMessages((prev) => prev.map((m) =>
          m.id === loadingId
            ? { ...m, text: res.text || lastText, isLoading: false }
            : m
        ));
        return;
      }
      if (res.status === 'error' || res.status === 'expired') {
        const errMsg = res.error || 'No pude completar la consulta.';
        setMessages((prev) => prev.map((m) =>
          m.id === loadingId
            ? { ...m, text: `⚠️ ${errMsg}`, isLoading: false }
            : m
        ));
        return;
      }
      // pending / running sin texto nuevo: seguir esperando.
    }

    // Si salimos del loop sin done/error → tiempo agotado.
    setMessages((prev) => prev.map((m) =>
      m.id === loadingId
        ? { ...m, text: '⏰ Se agotó el tiempo de espera. Probá de nuevo.', isLoading: false }
        : m
    ));
  }, [currentBackend]);

  // ───────────────────────────────────────────────────────────────────
  // Encoding y POST de UN chunk (o de un mensaje sin archivos).
  // Cuando el backend responde con `task_id`, polleamos hasta done.
  // Cuando responde con `text` directo (openai legacy), renderizamos.
  // ───────────────────────────────────────────────────────────────────
  const sendOneChunk = useCallback(async ({
    text,
    files,
    chunkIndex,    // 1-based
    totalChunks,
    showLoadingBubble,
  }) => {
    let attachmentsForChat = null;
    let camposExtraidos = null;

    if (files.length > 0) {
      setIsUploading(true);
      const uploadMsgId = crypto.randomUUID();
      const chunkLabel = totalChunks > 1
        ? ` (grupo ${chunkIndex} de ${totalChunks})`
        : '';
      setMessages((prev) => [...prev, {
        id: uploadMsgId,
        text: `Subiendo ${files.length} archivo${files.length === 1 ? '' : 's'}${chunkLabel}…`,
        sender: 'yoko',
        isLoading: true,
      }]);

      try {
        if (useAttachmentsPath) {
          // Managed Agents o legacy con módulos que exponen tools de
          // extracción: codificar base64 y mandar como attachments. El
          // backend persiste estos archivos en el carrito KV.
          const encoded = [];
          for (let i = 0; i < files.length; i++) {
            const file = files[i];
            setMessages((prev) => prev.map((msg) =>
              msg.id === uploadMsgId
                ? { ...msg, text: `Cargando archivo ${i + 1} de ${files.length}${chunkLabel}: ${file.name}…` }
                : msg
            ));
            const content_b64 = await fileToBase64(file);
            encoded.push({ filename: file.name, content_b64 });
          }
          attachmentsForChat = encoded;
          setMessages((prev) => prev.filter((msg) => msg.id !== uploadMsgId));
        } else {
          // Legacy openai sin tool conversacional de extracción:
          // pre-procesa cada archivo con parse_file e inyecta los campos
          // extraídos al texto del mensaje.
          const todosLosCampos = [];
          for (let i = 0; i < files.length; i++) {
            const file = files[i];
            setMessages((prev) => prev.map((msg) =>
              msg.id === uploadMsgId
                ? { ...msg, text: `Leyendo archivo ${i + 1} de ${files.length}${chunkLabel}: ${file.name}…` }
                : msg
            ));
            const formData = new FormData();
            formData.append('file', file);
            formData.append('fileName', file.name);
            try {
              const parsed = await postFormAuth(API.PARSE_FILE, formData);
              if (parsed && parsed.campos) todosLosCampos.push(parsed.campos);
            } catch (parseErr) {
              console.warn('parse_file falló para', file.name, parseErr);
            }
          }
          if (todosLosCampos.length > 0) {
            camposExtraidos = todosLosCampos.reduce((acc, cur) => {
              Object.keys(cur).forEach((k) => {
                if (!acc[k] && cur[k] !== null && cur[k] !== undefined) acc[k] = cur[k];
              });
              return acc;
            }, {});
          }
          setMessages((prev) => prev.filter((msg) => msg.id !== uploadMsgId));
        }
      } catch (err) {
        console.error('Error procesando archivos:', err);
        setMessages((prev) => prev.map((msg) =>
          msg.id === uploadMsgId
            ? { ...msg, text: '⚠️ Hubo un error al analizar los archivos.', isLoading: false }
            : msg
        ));
        setIsUploading(false);
        return;
      }
      setIsUploading(false);
    }

    // Burbuja "loading" del bot. Solo en chunks que requieran respuesta.
    let loadingId = null;
    if (showLoadingBubble) {
      loadingId = crypto.randomUUID();
      setMessages((prev) => [...prev, {
        id: loadingId,
        text: '',
        sender: 'yoko',
        isLoading: true,
      }]);
    }

    try {
      let mensajeConContexto = text;
      if (camposExtraidos) {
        const camposStr = Object.entries(camposExtraidos)
          .filter(([k, v]) => k !== 'confianza' && v !== null && v !== undefined && v !== '')
          .map(([k, v]) => `  - ${k}: ${v}`)
          .join('\n');
        const instruccion = 'INSTRUCCIÓN SISTEMA: Los datos anteriores fueron extraídos automáticamente del archivo adjunto. Tratalos como CONFIRMADOS. NO vuelvas a preguntar por ellos. Identifica qué campos obligatorios faltan (plazo, motivo, moneda, total_general, detalle_gasto, aprobador_id) y pregunta SOLO por los que no estén en la lista de arriba. Si necesitas centro de costo, usa la herramienta disponible para consultar centros de costo; no inventes centros de costo desde contexto.';
        mensajeConContexto = text
          ? `${text}\n\n[Datos extraídos del archivo adjunto:\n${camposStr}]\n\n${instruccion}`
          : `[Datos extraídos del archivo adjunto:\n${camposStr}]\n\n${instruccion}`;
      }

      const lastUserMsg = { role: 'user', content: mensajeConContexto };
      const apiMessages = isManaged
        ? [lastUserMsg]
        : [
            ...messages.filter((m) => !m.isLoading).map((m) => ({
              role: m.sender === 'user' ? 'user' : 'assistant',
              content: m.text,
            })),
            lastUserMsg,
          ];

      const payload = { user: user || {}, messages: apiMessages };
      if (attachmentsForChat) payload.attachments = attachmentsForChat;

      const data = await postJsonAuth(API.CHAT, payload, {
        headers: { 'X-Yoko-Backend': currentBackend },
      });

      // Modo async (managed_agents nuevo): backend devuelve task_id, polleamos.
      if (data && data.task_id) {
        if (loadingId) {
          await pollTaskUntilDone(data.task_id, loadingId);
        }
        return;
      }

      // Modo síncrono (openai legacy): backend devuelve text directo.
      if (!loadingId) return;

      let yokoText = '';
      if (typeof data === 'string') {
        yokoText = data === 'Accepted'
          ? 'He recibido tu mensaje (Make respondió "Accepted"). Recuerda configurar el módulo "Webhook Response".'
          : data;
      } else {
        yokoText = data.text || data.response || data.message || data.respuesta || JSON.stringify(data);
        if (data.action?.type === 'navigate' && data.action.path) {
          const params = data.action.params;
          const qs = params && Object.keys(params).length > 0
            ? '?' + new URLSearchParams(params).toString()
            : '';
          navigate(data.action.path + qs);
        }
      }
      setMessages((prev) => prev.map((m) =>
        m.id === loadingId ? { ...m, text: yokoText, isLoading: false } : m
      ));
    } catch (err) {
      console.error('Error webhook:', err);
      if (loadingId) {
        setMessages((prev) => prev.map((m) =>
          m.id === loadingId
            ? { ...m, text: 'Lo siento, hubo un problema al conectar con el servidor.', isLoading: false }
            : m
        ));
      }
    }
  }, [user, messages, navigate, pollTaskUntilDone, currentBackend, isManaged, useAttachmentsPath]);

  // ───────────────────────────────────────────────────────────────────
  // Entry point: el componente llama esto. Si hay >CHUNK_SIZE archivos,
  // los partimos en chunks y posteamos secuencialmente. Solo el ÚLTIMO
  // chunk lleva el texto del usuario y dispara la respuesta del bot;
  // los anteriores son "Listo (N). ¿Más?" del agent vía carrito.
  // ───────────────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (text, files) => {
    const safeFiles = Array.isArray(files) ? files : [];
    if (!text.trim() && safeFiles.length === 0) return;

    // Burbuja del usuario (1 sola, aunque haya N chunks).
    let displayText = text;
    if (safeFiles.length > 0) {
      const adj = `[${safeFiles.length} archivo(s) adjunto(s)]`;
      displayText = displayText ? `${displayText}\n${adj}` : adj;
    }
    setMessages((prev) => [...prev, {
      id: crypto.randomUUID(),
      text: displayText,
      sender: 'user',
    }]);

    // Auto-chunking aplica para flujos que mandan attachments en base64
    // al body (Managed o legacy con tools de extracción) — base64 infla
    // el payload y Vercel impone 4.5MB por request.
    if (!useAttachmentsPath || safeFiles.length <= CHUNK_SIZE) {
      await sendOneChunk({
        text,
        files: safeFiles,
        chunkIndex: 1,
        totalChunks: 1,
        showLoadingBubble: true,
      });
      return;
    }

    // Auto-chunking: dividir en grupos de CHUNK_SIZE archivos.
    const chunks = [];
    for (let i = 0; i < safeFiles.length; i += CHUNK_SIZE) {
      chunks.push(safeFiles.slice(i, i + CHUNK_SIZE));
    }
    for (let i = 0; i < chunks.length; i++) {
      const isLast = i === chunks.length - 1;
      await sendOneChunk({
        text: isLast ? text : '',          // texto del usuario solo en el último
        files: chunks[i],
        chunkIndex: i + 1,
        totalChunks: chunks.length,
        showLoadingBubble: true,            // cada chunk: bot confirma "Listo (N)"
      });
    }
  }, [sendOneChunk, useAttachmentsPath]);

  return { messages, sendMessage, isUploading, currentBackend, switchBackend };
}
