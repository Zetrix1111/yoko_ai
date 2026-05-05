// Hook compartido que envuelve GET/POST /api/config?tipo=<tipo>.
// Consolida la lectura/escritura de Config_Empresa y Config_Ventas para
// que las pantallas se concentren en su shape y no en fetch boilerplate.
//
// Uso:
//   const { data, loading, saving, error, save, reload } = useEmpresaConfig('empresa');
//   const { data, save } = useEmpresaConfig('ventas');
//
// `data` es el JSON tal como vive en la columna `data` de Airtable, o
// `null` si la fila aún no existe. Al guardar, el hook hace optimistic
// update local de `data` para que la UI vea los cambios sin esperar reload.

import { useCallback, useEffect, useState } from 'react';
import { API, getJsonAuth, postJsonAuth } from './api';

export function useEmpresaConfig(tipo) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await getJsonAuth(`${API.CONFIG}?tipo=${tipo}`);
      setData(resp?.data ?? null);
    } catch (e) {
      console.error(`[useEmpresaConfig:${tipo}] reload:`, e);
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [tipo]);

  useEffect(() => { reload(); }, [reload]);

  const save = useCallback(async (newData) => {
    setSaving(true);
    setError(null);
    try {
      await postJsonAuth(`${API.CONFIG}?tipo=${tipo}`, { data: newData });
      // Optimistic update: la próxima request al chat ya verá esto en
      // Airtable porque /api/config invalidó el cache.
      setData(newData);
      return true;
    } catch (e) {
      console.error(`[useEmpresaConfig:${tipo}] save:`, e);
      setError(e?.message || String(e));
      return false;
    } finally {
      setSaving(false);
    }
  }, [tipo]);

  return { data, loading, saving, error, save, reload };
}
