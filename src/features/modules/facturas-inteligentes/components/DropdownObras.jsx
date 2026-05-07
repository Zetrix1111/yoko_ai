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
 * Cache de módulo: aunque la tabla tenga 30 facturas, sólo se hace UN
 * fetch — todas las instancias de DropdownObras comparten la lista. Sin
 * esto, montar la tabla con N filas dispararía N requests al backend.
 *
 * Si el fetch falla (red, 5xx), cae a un input text libre para que el
 * usuario pueda ingresar manualmente la obra.
 *
 * Props:
 *   - value:    nombre de la obra seleccionada (string)
 *   - onChange: callback (nuevoNombre: string) => void
 */

let _obrasCache = null;
let _obrasPromise = null;

async function _fetchObrasCached() {
  if (_obrasCache !== null) return _obrasCache;
  if (_obrasPromise) return _obrasPromise;

  _obrasPromise = (async () => {
    try {
      const data = await getJsonAuth(API.CENTROS_COSTO);
      _obrasCache = Array.isArray(data?.centros) ? data.centros : [];
    } catch (err) {
      console.error('[DropdownObras] error cargando obras:', err);
      _obrasCache = [];
      // Re-lanzar para que el componente sepa que hubo error en este intento;
      // el cache queda en [] así otras instancias no re-intentan.
      _obrasPromise = null;
      throw err;
    }
    return _obrasCache;
  })();

  return _obrasPromise;
}

export default function DropdownObras({ value, onChange }) {
  const [obras, setObras] = useState(_obrasCache || []);
  const [loading, setLoading] = useState(_obrasCache === null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    if (_obrasCache !== null) {
      // Cache ya hidratado por otra instancia (ej. rerender con N filas).
      // Sincroniza el state local en un solo setState consolidado.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setObras(_obrasCache);
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
      {obras.map((o) => {
        const label = o.obra ? `${o.obra} - ${o.nombre}` : o.nombre;
        return (
          <option key={o.id} value={o.nombre}>
            {label}
          </option>
        );
      })}
    </select>
  );
}
