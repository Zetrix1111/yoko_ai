import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../../../../shared/api';

/**
 * Detalle de una solicitud por id (recId de Airtable).
 *
 * Devuelve el shape:
 *   { id, numero, tipo, motivo, plazo, moneda, total_general,
 *     centro_costo, estado, editable, nombre, items }
 *
 * `items` ya viene parseado a array (el backend hace el JSON.parse del
 * campo DETALLE_GASTO).
 *
 * `editable` indica si la solicitud está en un estado que permite
 * modificar items (PENDIENTE_*). Si es false, la UI debe deshabilitar
 * los inputs.
 */
export default function useSolicitud(id) {
  const [solicitud, setSolicitud] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSolicitud = useCallback(async () => {
    if (!id) {
      setSolicitud(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch(
        `/api/solicitudes?action=detalle&id=${encodeURIComponent(id)}`,
        { method: 'GET' },
      );
      setSolicitud(data);
    } catch (err) {
      console.error('[useSolicitud] fetch:', err);
      setError(err.message || 'Error al cargar la solicitud');
      setSolicitud(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchSolicitud();
  }, [fetchSolicitud]);

  return { solicitud, loading, error, refetch: fetchSolicitud, setSolicitud };
}
