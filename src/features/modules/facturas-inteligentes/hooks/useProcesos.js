import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../../../../shared/api';

/**
 * Lista de procesos de Facturas Inteligentes del usuario autenticado.
 *
 * GET /api/facturas?action=listar-procesos. El backend filtra por el
 * `empresa_id` del JWT y devuelve los procesos agrupados con metadata
 * (count, count_baja, count_errores, estado_inferido, etc.).
 *
 * Limitación importante: la SQLite del backend vive en `/tmp` con TTL
 * de 24h. Los procesos viejos no aparecen — la UI debe documentarlo.
 *
 * Patrón modelado sobre `useSolicitudes` del módulo Caja Chica.
 */
export default function useProcesos() {
  const [procesos, setProcesos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchProcesos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch('/api/facturas?action=listar-procesos', { method: 'GET' });
      setProcesos(Array.isArray(data?.procesos) ? data.procesos : []);
    } catch (err) {
      console.error('[useProcesos] fetch:', err);
      setError(err.message || 'Error al cargar procesos');
      setProcesos([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProcesos();
  }, [fetchProcesos]);

  return { procesos, loading, error, refetch: fetchProcesos };
}
