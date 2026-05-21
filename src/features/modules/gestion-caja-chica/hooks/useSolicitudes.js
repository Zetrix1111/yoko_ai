import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../../../../shared/api';

/**
 * Lista de solicitudes del usuario autenticado.
 *
 * El backend filtra por el email del JWT (vía lookup `EMAIL (from SOLICITANTE)`
 * en Airtable), así que no hace falta pasar el DNI desde el frontend.
 *
 * Devuelve `solicitudes` ordenadas más recientes primero (orden lo decide el
 * backend usando NUMERO desc).
 */
export default function useSolicitudes() {
  const [solicitudes, setSolicitudes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSolicitudes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch('/api/solicitudes?action=listar', { method: 'GET' });
      setSolicitudes(Array.isArray(data?.solicitudes) ? data.solicitudes : []);
    } catch (err) {
      console.error('[useSolicitudes] fetch:', err);
      setError(err.message || 'Error al cargar solicitudes');
      setSolicitudes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSolicitudes();
  }, [fetchSolicitudes]);

  return { solicitudes, loading, error, refetch: fetchSolicitudes };
}
