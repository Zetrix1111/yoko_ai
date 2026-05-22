import { Info, Download, ArrowRight, History } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import '../fi-sections.css';

/**
 * Sección "Exportaciones" del módulo Facturas Inteligentes.
 *
 * MAQUETA — el backend aún no rastrea las descargas de Excel. Esta
 * vista existe para mostrar el layout final cuando el tracking esté
 * disponible. Solo la acción "Ver proceso origen" navega; el resto
 * queda deshabilitado con tooltip "Próximamente".
 */

const FILAS_MOCK = [
  {
    id: 'exp-001',
    archivo: 'registro_compras_concar_2026-05.xlsx',
    proceso_id: 'proc-0a1b2c',
    tipo: 'Compras',
    sistema: 'CONCAR',
    version: 1,
    fecha: '21/05/2026 14:32',
    usuario: 'John Echevarría',
  },
  {
    id: 'exp-002',
    archivo: 'registro_ventas_sire_2026-05.txt',
    proceso_id: 'proc-9z8y7x',
    tipo: 'Ventas',
    sistema: 'SIRE',
    version: 2,
    fecha: '20/05/2026 11:08',
    usuario: 'John Echevarría',
  },
  {
    id: 'exp-003',
    archivo: 'registro_compras_concar_2026-04.xlsx',
    proceso_id: 'proc-3l4k5j',
    tipo: 'Compras',
    sistema: 'CONCAR',
    version: 1,
    fecha: '30/04/2026 16:51',
    usuario: 'John Echevarría',
  },
];

export default function ExportacionesSection() {
  const navigate = useNavigate();

  return (
    <div className="fi-section">
      <header className="fi-section-header">
        <div>
          <h1 className="fi-section-title">Exportaciones</h1>
          <p className="fi-section-subtitle">
            Historial de Excels y archivos contables generados por los procesos.
          </p>
        </div>
      </header>

      <div className="fi-alert fi-alert-info">
        <Info size={16} />
        <span>
          Las exportaciones aún no se rastrean en backend. Esta vista está en modo
          maqueta y se habilitará cuando se agregue el tracking de descargas.
        </span>
      </div>

      <div className="fi-table-wrap">
        <table className="fi-table">
          <thead>
            <tr>
              <th>Archivo</th>
              <th>Proceso origen</th>
              <th>Tipo</th>
              <th>Sistema contable</th>
              <th className="num">Versión</th>
              <th>Fecha</th>
              <th>Usuario</th>
              <th aria-label="Acciones" />
            </tr>
          </thead>
          <tbody>
            {FILAS_MOCK.map((f) => (
              <tr key={f.id}>
                <td className="fi-cell-mono">{f.archivo}</td>
                <td className="fi-cell-mono">{f.proceso_id}</td>
                <td>{f.tipo}</td>
                <td>
                  <span className="fi-badge fi-badge-info">{f.sistema}</span>
                </td>
                <td className="num">v{f.version}</td>
                <td>{f.fecha}</td>
                <td>{f.usuario}</td>
                <td className="fi-cell-actions">
                  <button
                    type="button"
                    className="fi-btn fi-btn-ghost"
                    disabled
                    title="Próximamente"
                  >
                    <Download size={14} />
                  </button>
                  <button
                    type="button"
                    className="fi-btn fi-btn-ghost"
                    disabled
                    title="Próximamente"
                  >
                    <History size={14} />
                  </button>
                  <button
                    type="button"
                    className="fi-btn fi-btn-link"
                    onClick={() =>
                      navigate(
                        `/modulos/facturas-inteligentes?section=revision&proceso_id=${encodeURIComponent(f.proceso_id)}`
                      )
                    }
                    title="Ver proceso origen"
                  >
                    Ver origen <ArrowRight size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
