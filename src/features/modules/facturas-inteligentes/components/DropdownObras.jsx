import { useEffect, useState } from 'react';
import { API, getJsonAuth } from '../../../../shared/api';

/**
 * Dropdown de Obras / Centros de Costo del tenant.
 *
 * Consume /api/config?tipo=centros_costo (definido en api/config.py),
 * que ya filtra por empresa_id del JWT y devuelve registros de la tabla
 * Airtable `obras`. Shape recibido:
 *
 *   { centros: [{ id, obra, nombre, constituyen }] }
 *
 * Donde:
 *   - `obra`   = código corto (ej. "OBR-001")
 *   - `nombre` = razón / descripción de la obra
 *
 * Cache module-level KEYED por empresa_id: si la tabla tiene 30 facturas
 * y todas montan DropdownObras, sólo se hace UN fetch para ese tenant.
 * Pero si el usuario cierra sesión y entra con otro tenant, la key del
 * cache cambia y se refetchea automáticamente — sin esto, el cache del
 * tenant anterior contaminaba la sesión nueva.
 *
 * `_obrasPromise` además dedupea fetches en vuelo para que N dropdowns
 * montados al mismo tiempo no disparen N requests concurrentes.
 *
 * Si el fetch falla (red, 5xx), cae a un input text libre para que el
 * usuario pueda ingresar manualmente la obra.
 *
 * Props:
 *   - value:    nombre de la obra seleccionada (string)
 *   - onChange: callback (nuevoNombre: string) => void
 */

let _cache = { empresaId: null, obras: null };
let _inFlightPromise = null;

/**
 * Decodifica el JWT del localStorage para extraer empresa_id sin tener
 * que pasarlo como prop a DropdownObras. Si algo falla, devuelve null
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

async function _fetchObrasCached() {
  const currentEmpresa = _readEmpresaIdFromToken();

  // Cache HIT solo si el empresa_id coincide con la sesión activa.
  if (_cache.empresaId === currentEmpresa && _cache.obras !== null) {
    return _cache.obras;
  }

  // Hay un fetch en vuelo para este (o cualquier) tenant — esperar ese.
  // No tiene sentido lanzar otro request en paralelo.
  if (_inFlightPromise) return _inFlightPromise;

  _inFlightPromise = (async () => {
    try {
      const data = await getJsonAuth(API.CENTROS_COSTO);
      const obras = Array.isArray(data?.centros) ? data.centros : [];
      _cache = { empresaId: currentEmpresa, obras };
      return obras;
    } catch (err) {
      console.error('[DropdownObras] error cargando obras:', err);
      // No persistimos error en el cache → próximo render reintenta.
      throw err;
    } finally {
      _inFlightPromise = null;
    }
  })();

  return _inFlightPromise;
}

export default function DropdownObras({ value, onChange }) {
  // Helper para chequear si el cache aplica a la sesión actual sin
  // duplicar la lógica de _readEmpresaIdFromToken en cada render.
  const _cacheValidForCurrentSession = () => (
    _cache.obras !== null && _cache.empresaId === _readEmpresaIdFromToken()
  );

  const [obras, setObras] = useState(() =>
    _cacheValidForCurrentSession() ? _cache.obras : []
  );
  const [loading, setLoading] = useState(() => !_cacheValidForCurrentSession());
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    if (_cacheValidForCurrentSession()) {
      // Cache ya hidratado por otra instancia con el mismo empresa_id.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setObras(_cache.obras);
      setLoading(false);
      return;
    }

    _fetchObrasCached()
      .then((list) => {
        if (cancelled) return;
        setObras(list);
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
        <option>Cargando obras...</option>
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
        placeholder="Ingresar obra manualmente..."
      />
    );
  }

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className="cell-select"
    >
      <option value="">Seleccionar obra...</option>
      {obras.map((o) => (
        // El `value` que persiste es el ID (ej. "CC-53", "9000") — sirve
        // como código de centro de costo para el siguiente paso (CONCAR).
        // El label visible en la UI es el campo OBRA (ej. "SATIPO").
        // El campo NOMBRE OBRA (la descripción larga) lo dejamos como
        // tooltip para que el usuario pueda confirmar al pasar el mouse.
        <option key={o.id} value={o.id} title={o.nombre || ''}>
          {o.obra}
        </option>
      ))}
    </select>
  );
}
