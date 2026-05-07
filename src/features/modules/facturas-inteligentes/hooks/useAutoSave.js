import { useEffect, useRef } from 'react';
import { apiFetch } from '../../../../shared/api';

const DEBOUNCE_MS = 1000;

/**
 * Auto-save de ediciones del usuario en la tabla de facturas. Cuando el
 * array `facturas` cambia, espera 1s (debounce) y dispara:
 *
 *   1. PUT /api/facturas?action=actualizar  → persiste en SQLite (server)
 *   2. localStorage.setItem(facturas_<id>, ...)  → backup local
 *
 * El backup en localStorage es defensa contra el `/tmp` ephemero de Vercel:
 * si el SQLite se reinicia entre cold starts, el frontend puede recuperar
 * la sesión desde localStorage.
 *
 * Concurrency lock: si ya hay un save en vuelo cuando expira el debounce,
 * se saltea ese ciclo. El próximo edit dispara otro intento, así que no
 * se pierden cambios — solo se evitan PUTs en paralelo.
 *
 * Skip primer render: el efecto no guarda en el primer mount (la carga
 * inicial no es una edición del usuario).
 */
export default function useAutoSave(procesoId, facturas) {
  const timeoutRef = useRef(null);
  const isSavingRef = useRef(false);
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }

    if (!procesoId || !Array.isArray(facturas) || facturas.length === 0) {
      return;
    }

    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    timeoutRef.current = setTimeout(async () => {
      if (isSavingRef.current) {
        // Save anterior aún en vuelo. El próximo edit redisparará el debounce.
        return;
      }
      isSavingRef.current = true;

      // 1) Persistir en backend (SQLite via /api/facturas?action=actualizar).
      try {
        await apiFetch('/api/facturas?action=actualizar', {
          method: 'PUT',
          body: { proceso_id: procesoId, facturas },
        });
      } catch (err) {
        console.error('[useAutoSave] backend:', err);
      }

      // 2) Backup en localStorage — best-effort. Si está lleno o bloqueado,
      //    loggeamos pero no rompemos el flujo.
      try {
        localStorage.setItem(
          `facturas_${procesoId}`,
          JSON.stringify({
            proceso_id: procesoId,
            facturas,
            timestamp: Date.now(),
          })
        );
      } catch (err) {
        console.error('[useAutoSave] localStorage:', err);
      }

      isSavingRef.current = false;
    }, DEBOUNCE_MS);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [procesoId, facturas]);
}
