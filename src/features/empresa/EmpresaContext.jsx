import { createContext, useContext, useMemo } from 'react';
import { useEmpresaConfig } from '../../shared/useEmpresaConfig';

/**
 * EmpresaContext — distribuye los datos de `Config_Empresa.data` a
 * todo el árbol autenticado (sidebar, dashboard, módulos, panel IA),
 * con un único fetch por sesión.
 *
 * Sin este Context cada componente que necesitara info de empresa
 * llamaría a `useEmpresaConfig('empresa')` por su cuenta y generaría
 * N requests en paralelo al `/api/config?tipo=empresa`.
 *
 * Shape expuesto vía `useEmpresa()`:
 *   {
 *     basicos:        { name, razon_social, ruc, sistema_contable } | {},
 *     info_extendida: { ... } | {},
 *     proceso:        { caja_chica: { ... } } | {},
 *     loading:        boolean,
 *     error:          string | null,
 *     reload:         () => Promise<void>,
 *   }
 */

const EmpresaContext = createContext(null);

export function EmpresaProvider({ children }) {
  const { data, loading, error, reload } = useEmpresaConfig('empresa');

  // Memoizamos el objeto que va por contexto para no provocar re-renders
  // innecesarios en cada render del provider.
  const value = useMemo(() => {
    const safe = data && typeof data === 'object' ? data : {};
    return {
      basicos:        safe.basicos        || {},
      info_extendida: safe.info_extendida || {},
      proceso:        safe.proceso        || {},
      loading,
      error,
      reload,
    };
  }, [data, loading, error, reload]);

  return (
    <EmpresaContext.Provider value={value}>{children}</EmpresaContext.Provider>
  );
}

export function useEmpresa() {
  const ctx = useContext(EmpresaContext);
  if (ctx === null) {
    throw new Error(
      '[useEmpresa] debe usarse dentro de <EmpresaProvider>. Asegurate de envolver el shell autenticado en el provider.'
    );
  }
  return ctx;
}

/**
 * Mapea el slug del campo `sistema_contable` de Airtable a su display
 * uppercase. Fallback: el slug original en uppercase, o "—" si está vacío.
 */
export function formatSistemaContable(slug) {
  if (!slug || typeof slug !== 'string') return '—';
  const map = {
    sire:     'SIRE',
    concar:   'CONCAR',
    siscont:  'SISCONT',
    starsoft: 'STARSOFT',
  };
  const key = slug.trim().toLowerCase();
  return map[key] || slug.trim().toUpperCase();
}
