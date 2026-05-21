import { useEffect, useRef } from 'react';
import { apiFetch } from '../../../../shared/api';

const DEBOUNCE_MS = 1000;

/**
 * Auto-save de los items editables de una solicitud. Cada vez que cambia el
 * array `items`, espera 1s y dispara:
 *
 *   PUT /api/solicitudes?action=actualizar-items
 *   body: { id, detalle_gasto: items }
 *
 * El backend recalcula TOTAL_GENERAL como suma de los `total` de cada item.
 * Si la solicitud no está editable (estado no PENDIENTE_*), devuelve 409 y
 * el caller no debería haber permitido el cambio.
 *
 * Patrón inspirado en `features/modules/facturas-inteligentes/hooks/useAutoSave.js`:
 * skipea el primer render (carga inicial no es edición), debounce con
 * concurrency lock (si hay save en vuelo, salta este ciclo y deja que el
 * próximo edit redispare).
 *
 * Callbacks opcionales para que el componente refleje el TOTAL_GENERAL
 * recalculado y mostrar/ocultar el indicador "Guardando…".
 */
export default function useAutoSaveItems(
  solicitudId,
  items,
  { enabled = true, onSaved, onError } = {},
) {
  const timeoutRef = useRef(null);
  const isSavingRef = useRef(false);
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }

    if (!enabled || !solicitudId || !Array.isArray(items)) {
      return;
    }

    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    timeoutRef.current = setTimeout(async () => {
      if (isSavingRef.current) return;
      isSavingRef.current = true;

      try {
        const result = await apiFetch('/api/solicitudes?action=actualizar-items', {
          method: 'PUT',
          body: { id: solicitudId, detalle_gasto: items },
        });
        if (onSaved) onSaved(result);
      } catch (err) {
        console.error('[useAutoSaveItems] backend:', err);
        if (onError) onError(err);
      } finally {
        isSavingRef.current = false;
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solicitudId, items, enabled]);
}
