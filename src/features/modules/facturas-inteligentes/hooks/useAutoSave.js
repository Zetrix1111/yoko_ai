import { useEffect, useRef } from 'react';
import { apiFetch } from '../../../../shared/api';

const DEBOUNCE_MS = 1000;

/**
 * Auto-save de ediciones del usuario en la tabla de facturas. Cuando el
 * array `facturas` cambia, espera 1s (debounce) y dispara un PUT al
 * endpoint /api/facturas?action=actualizar con el lote completo.
 *
 * Stub funcional para Fases 4-5. Una versión más robusta puede agregar:
 *   - Indicador de estado (idle / saving / saved / error)
 *   - Retry con backoff
 *   - Diff por fila (hoy manda todas las filas siempre)
 *
 * Nota: no se dispara en el primer render para evitar guardar la carga
 * inicial como si fuera una edición.
 */
export default function useAutoSave(procesoId, facturas) {
  const timerRef = useRef(null);
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }

    if (!procesoId || !Array.isArray(facturas) || facturas.length === 0) {
      return;
    }

    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(async () => {
      try {
        await apiFetch('/api/facturas?action=actualizar', {
          method: 'PUT',
          body: { proceso_id: procesoId, facturas },
        });
      } catch (err) {
        console.error('[useAutoSave]', err);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [procesoId, facturas]);
}
