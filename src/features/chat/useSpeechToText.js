import { useState, useRef, useCallback } from 'react';
import { postBytesAuth } from '../../shared/api';

// Hook: graba audio con MediaRecorder y lo manda a /api/transcribe (OpenAI).
// Retorna el texto transcrito — NO envía mensaje. El usuario revisa y envía.
//
// Estados:
//   'idle'       → listo para grabar
//   'recording'  → grabando (mostrar pulso)
//   'processing' → enviando al servidor + esperando transcripción
export function useSpeechToText() {
  const [state, setState] = useState('idle');
  const [error, setError] = useState('');
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  const cleanupStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  const start = useCallback(async () => {
    setError('');
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Tu navegador no soporta grabación de audio.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data?.size > 0) chunksRef.current.push(e.data);
      };
      recorderRef.current = recorder;
      recorder.start();
      setState('recording');
    } catch (err) {
      console.error('Mic access error:', err);
      setError('No se pudo acceder al micrófono. Verifica los permisos.');
      setState('idle');
    }
  }, []);

  const stopAndTranscribe = useCallback(() => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || state !== 'recording') {
        resolve('');
        return;
      }

      recorder.onstop = async () => {
        cleanupStream();
        const mimeType = recorder.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: mimeType });

        if (blob.size === 0) {
          setState('idle');
          resolve('');
          return;
        }

        setState('processing');
        try {
          const data = await postBytesAuth('/api/transcribe', blob, mimeType);
          setState('idle');
          resolve(((data && data.text) || '').trim());
        } catch (err) {
          console.error('Transcribe error:', err);
          setError('Error al transcribir. Intenta de nuevo.');
          setState('idle');
          resolve('');
        }
      };

      recorder.stop();
    });
  }, [state]);

  const cancel = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && state === 'recording') {
      recorder.onstop = null;
      try { recorder.stop(); } catch { /* ignore */ }
    }
    cleanupStream();
    chunksRef.current = [];
    setState('idle');
  }, [state]);

  return { state, error, start, stopAndTranscribe, cancel };
}
