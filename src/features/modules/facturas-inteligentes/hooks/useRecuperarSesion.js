import { useEffect, useRef } from 'react';
import { apiFetch } from '../../../../shared/api';

/**
 * Detecta sesiones anteriores guardadas en localStorage (por useAutoSave)
 * y propone al usuario continuar donde quedó.
 *
 * Flujo:
 *   1. Busca entradas con prefijo `facturas_` en localStorage.
 *   2. Toma la más reciente por timestamp.
 *   3. Valida con backend: GET /api/facturas?action=recuperar.
 *      - 404 → sesión expiró en server (Vercel /tmp se reinició);
 *        purga la entrada de localStorage y termina silenciosamente.
 *      - red caída u otro error → ofrece restaurar desde la copia local.
 *   4. Si responde OK, muestra confirm() al usuario.
 *   5. Si acepta, llama onRecover(proceso, facturas) — el caller decide
 *      cómo aplicar los datos (típicamente: setProceso, setFacturas,
 *      setStage(VALIDATING)).
 *
 * Solo se dispara UNA vez al primer mount, con un pequeño delay para
 * no chocar contra el render inicial. `onRecover` se lee desde un ref
 * para que cambios de identidad de la callback no re-disparen el efecto.
 */
export default function useRecuperarSesion(onRecover) {
  const hasRunRef = useRef(false);
  const onRecoverRef = useRef(onRecover);

  // Mantener el ref con la última callback sin re-disparar el efecto principal.
  useEffect(() => {
    onRecoverRef.current = onRecover;
  }, [onRecover]);

  useEffect(() => {
    if (hasRunRef.current) return;
    hasRunRef.current = true;

    const timer = setTimeout(async () => {
      try {
        // 1) Buscar entradas en localStorage
        const keys = Object.keys(localStorage).filter((k) => k.startsWith('facturas_'));
        if (keys.length === 0) return;

        // 2) Tomar la más reciente
        let mostRecent = null;
        let mostRecentTs = 0;
        for (const key of keys) {
          try {
            const raw = localStorage.getItem(key);
            if (!raw) continue;
            const data = JSON.parse(raw);
            if (typeof data.timestamp === 'number' && data.timestamp > mostRecentTs) {
              mostRecentTs = data.timestamp;
              mostRecent = { key, data };
            }
          } catch {
            // Entrada corrupta — purgar.
            try { localStorage.removeItem(key); } catch { /* ignore */ }
          }
        }
        if (!mostRecent) return;

        const { data, key } = mostRecent;
        const procesoId = data.proceso_id;
        const numFacturas = Array.isArray(data.facturas) ? data.facturas.length : 0;
        if (!procesoId || numFacturas === 0) return;

        // 3) Validar con backend
        let backendData = null;
        try {
          backendData = await apiFetch(
            `/api/facturas?action=recuperar&proceso_id=${encodeURIComponent(procesoId)}`,
            { method: 'GET' }
          );
        } catch (err) {
          const msg = String(err?.message || err);
          if (msg.includes('HTTP 404')) {
            // Sesión expirada en server — purgar localStorage también.
            try { localStorage.removeItem(key); } catch { /* ignore */ }
            return;
          }
          // Otra falla (red, 5xx) — ofrecer fallback local.
          if (window.confirm(
            'Hay una sesión local guardada pero no se pudo validar con el servidor.\n' +
            '¿Restaurar desde la copia local?'
          )) {
            onRecoverRef.current(
              {
                proceso_id: procesoId,
                empresa_id: data.empresa_id || '',
                timestamp:  data.timestamp,
              },
              data.facturas
            );
          }
          return;
        }

        // 4) Sesión válida — preguntar al usuario
        const fechaStr = new Date(data.timestamp).toLocaleString('es-PE');
        const confirmMsg = (
          `Se encontró una sesión anterior con ${numFacturas} ` +
          `factura${numFacturas !== 1 ? 's' : ''}.\n\n` +
          `Guardada: ${fechaStr}\n` +
          `Proceso: ${procesoId}\n\n` +
          `¿Continuar con esta sesión?`
        );
        if (!window.confirm(confirmMsg)) return;

        // 5) Restaurar — backend gana sobre localStorage si difieren.
        onRecoverRef.current(
          {
            proceso_id: procesoId,
            empresa_id: backendData.empresa_id || data.empresa_id || '',
            timestamp:  backendData.timestamp || data.timestamp,
          },
          backendData.facturas || data.facturas
        );
      } catch (err) {
        console.error('[useRecuperarSesion]', err);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, []);
}
