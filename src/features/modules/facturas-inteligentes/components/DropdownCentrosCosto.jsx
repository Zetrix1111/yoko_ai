import { useEffect, useState } from 'react';
import { API, getJsonAuth } from '../../../../shared/api';

/**
 * Dropdown de Centros de Costo del tenant.
 *
 * Consume /api/config?tipo=centros_costo (definido en api/config.py),
 * que ya filtra por empresa_id del JWT y devuelve registros de centros
 * de costo. Shape recibido:
 *
 *   { centros: [{ id, centro_costo, nombre, constituyen }] }
 *
 * Donde:
 *   - `centro_costo` = código corto (ej. "CC-001")
 *   - `nombre`       = descripción del centro de costo
 *
 * Cache module-level KEYED por empresa_id: si la tabla tiene 30 facturas
 * y todas montan DropdownCentrosCosto, sólo se hace UN fetch para ese tenant.
 * Pero si el usuario cierra sesión y entra con otro tenant, la key del
 * cache cambia y se refetchea automáticamente — sin esto, el cache del
 * tenant anterior contaminaba la sesión nueva.
 *
 * La promesa en vuelo además dedupea fetches para que N dropdowns
 * montados al mismo tiempo no disparen N requests concurrentes.
 *
 * Si el fetch falla (red, 5xx), cae a un input text libre para que el
 * usuario pueda ingresar manualmente el centro de costo.
 *
 * Props:
 *   - value:    código de centro de costo seleccionado (string)
 *   - onChange: callback (nuevoCentroCosto: string) => void
 */

let _cache = { empresaId: null, centros: null };
let _inFlightPromise = null;

/**
 * Decodifica el JWT del localStorage para extraer empresa_id sin tener
 * que pasarlo como prop a DropdownCentrosCosto. Si algo falla, devuelve null
 * (el cache nunca matchea con null y siempre refetchea — comportamiento
 * conservador y seguro).
 */
function _readEmpresaIdFromToken() {
  try {
    const raw = localStorage.getItem('yoko_auth');
    if (!raw) return null;
    const auth = JSON.parse(raw);
    const token = auth?.token;
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded));
    return payload?.empresa_id || null;
  } catch {
    return null;
  }
}

async function _fetchCentrosCached() {
  const currentEmpresa = _readEmpresaIdFromToken();

  // Cache HIT solo si el empresa_id coincide con la sesión activa.
  if (_cache.empresaId === currentEmpresa && _cache.centros !== null) {
    return _cache.centros;
  }

  // Hay un fetch en vuelo para este (o cualquier) tenant — esperar ese.
  // No tiene sentido lanzar otro request en paralelo.
  if (_inFlightPromise) return _inFlightPromise;

  _inFlightPromise = (async () => {
    try {
      const data = await getJsonAuth(API.CENTROS_COSTO);
      const centros = Array.isArray(data?.centros) ? data.centros : [];
      _cache = { empresaId: currentEmpresa, centros };
      return centros;
    } catch (err) {
      console.error('[DropdownCentrosCosto] error cargando centros de costo:', err);
      // No persistimos error en el cache → próximo render reintenta.
      throw err;
    } finally {
      _inFlightPromise = null;
    }
  })();

  return _inFlightPromise;
}

export default function DropdownCentrosCosto({ value, onChange }) {
  // Helper para chequear si el cache aplica a la sesión actual sin
  // duplicar la lógica de _readEmpresaIdFromToken en cada render.
  const _cacheValidForCurrentSession = () => (
    _cache.centros !== null && _cache.empresaId === _readEmpresaIdFromToken()
  );

  const [centros, setCentros] = useState(() =>
    _cacheValidForCurrentSession() ? _cache.centros : []
  );
  const [loading, setLoading] = useState(() => !_cacheValidForCurrentSession());
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    if (_cacheValidForCurrentSession()) {
      // Cache ya hidratado por otra instancia con el mismo empresa_id.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCentros(_cache.centros);
      setLoading(false);
      return;
    }

    _fetchCentrosCached()
      .then((list) => {
        if (cancelled) return;
        setCentros(list);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <select className="cell-select" disabled>
        <option>Cargando centros de costo...</option>
      </select>
    );
  }

  // Fallback: si falló el fetch, dar input libre para no bloquear al usuario.
  if (error) {
    return (
      <input
        type="text"
        className="cell-input"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Ingresar centro de costo..."
      />
    );
  }

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className="cell-select"
    >
      <option value="">Seleccionar centro de costo...</option>
      {centros.map((c) => (
        <option key={c.id} value={c.id} title={c.nombre || ''}>
          {c.centro_costo}
        </option>
      ))}
    </select>
  );
}
