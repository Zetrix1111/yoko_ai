import {
  FileUp,
  Brain,
  AlertTriangle,
  Edit3,
  FileSpreadsheet,
  CheckCircle2,
  Eye,
  X,
} from 'lucide-react';
import '../fi-sections.css';

/**
 * Add-ons visuales para la sección Revisión.
 *
 * Todo es maqueta — la tabla editable y el auto-save NO se tocan,
 * solo agregamos elementos visuales encima/al costado:
 *
 *   1. Timeline horizontal de los pasos del proceso.
 *   2. Filtros pills (Todas / Solo errores / Solo baja confianza / Pendientes).
 *      Hoy solo "Todas" funciona; los demás están como placeholder.
 *   3. Acciones masivas (Confirmar todo / etc.). Disabled excepto
 *      "Descargar Excel" si se pasa onDescargar.
 *   4. (Opcional) Panel lateral con preview del comprobante cuando
 *      hay una fila seleccionada — se renderiza por separado debajo
 *      como `DetallePanel`.
 *
 * El padre (RevisionSection) decide cuándo mostrar cada parte. Los
 * componentes son puramente presentacionales para evitar acoplar la
 * lógica de la tabla.
 */

const TIMELINE_STEPS = [
  { id: 'recibido',  label: 'PDF recibido',       Icon: FileUp,         etapas: ['UPLOAD', 'VALIDATING', 'CONFIRMING', 'DONE'] },
  { id: 'procesado', label: 'IA procesó',         Icon: Brain,          etapas: ['VALIDATING', 'CONFIRMING', 'DONE'] },
  { id: 'alertas',   label: 'Alertas detectadas', Icon: AlertTriangle,  etapas: ['CONFIRMING', 'DONE'] },
  { id: 'corrigio',  label: 'Usuario corrigiendo', Icon: Edit3,         etapas: ['CONFIRMING', 'DONE'] },
  { id: 'excel',     label: 'Excel generado',     Icon: FileSpreadsheet, etapas: ['DONE'] },
  { id: 'exportado', label: 'Exportado',          Icon: CheckCircle2,   etapas: [] /* aún no rastreado */ },
];

export function ProcessTimeline({ etapa = 'UPLOAD' }) {
  return (
    <ol className="fi-timeline" aria-label="Estado del proceso">
      {TIMELINE_STEPS.map((step, idx) => {
        const completado = step.etapas.includes(etapa);
        return (
          <li
            key={step.id}
            className={`fi-timeline-step ${completado ? 'is-done' : ''}`}
          >
            <div className="fi-timeline-dot">
              <step.Icon size={14} />
            </div>
            <span className="fi-timeline-label">{step.label}</span>
            {idx < TIMELINE_STEPS.length - 1 && (
              <span className="fi-timeline-bar" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

const FILTROS_REVISION = [
  { id: 'todas',         label: 'Todas',             enabled: true },
  { id: 'errores',       label: 'Solo errores',      enabled: false },
  { id: 'baja',          label: 'Solo baja confianza', enabled: false },
  { id: 'pendientes',    label: 'Pendientes',        enabled: false },
];

export function FiltrosRevision({ filtro = 'todas', onChange }) {
  return (
    <nav className="fi-filter-pills" aria-label="Filtrar facturas">
      {FILTROS_REVISION.map((f) => (
        <button
          key={f.id}
          type="button"
          className={`fi-pill ${filtro === f.id ? 'is-active' : ''}`}
          onClick={() => f.enabled && onChange && onChange(f.id)}
          disabled={!f.enabled}
          title={f.enabled ? f.label : 'Próximamente'}
        >
          {f.label}
        </button>
      ))}
    </nav>
  );
}

export function AccionesMasivas({ onDescargar, downloading = false }) {
  return (
    <div className="fi-bulk-actions">
      <button type="button" className="fi-btn fi-btn-ghost" disabled title="Próximamente">
        Confirmar todo
      </button>
      <button type="button" className="fi-btn fi-btn-ghost" disabled title="Próximamente">
        Solo errores
      </button>
      <button type="button" className="fi-btn fi-btn-ghost" disabled title="Próximamente">
        Solo baja confianza
      </button>
      <button type="button" className="fi-btn fi-btn-ghost" disabled title="Próximamente">
        Exportar CONCAR
      </button>
      <button
        type="button"
        className="fi-btn fi-btn-primary"
        onClick={onDescargar}
        disabled={!onDescargar || downloading}
        title="Descargar Excel del registro"
      >
        <FileSpreadsheet size={14} />
        {downloading ? 'Descargando…' : 'Descargar Excel'}
      </button>
    </div>
  );
}

/**
 * Panel lateral con detalle del comprobante seleccionado. Si no hay
 * selección, se renderiza un estado vacío indicando al usuario qué
 * pasa al seleccionar una fila.
 *
 * Maqueta: los datos vienen de la propia fila (factura), pero NO
 * mostramos preview del PDF (no tenemos el binario en el frontend).
 */
export function DetallePanel({ factura, onClose }) {
  if (!factura) {
    return (
      <aside className="fi-detail-panel fi-detail-panel-empty">
        <Eye size={20} />
        <p>Selecciona una fila para ver detalles, OCR e historial de cambios.</p>
      </aside>
    );
  }

  const rawText = factura.raw_text || '';

  return (
    <aside className="fi-detail-panel">
      <header className="fi-detail-panel-header">
        <div>
          <h3>Detalle del comprobante</h3>
          <p className="fi-detail-panel-id">{factura.id || '—'}</p>
        </div>
        <button
          type="button"
          className="fi-btn fi-btn-ghost"
          onClick={onClose}
          aria-label="Cerrar panel"
        >
          <X size={16} />
        </button>
      </header>

      <section className="fi-detail-block">
        <h4>Preview del comprobante</h4>
        <div className="fi-detail-pdf-placeholder">
          Preview del PDF disponible próximamente
        </div>
      </section>

      <section className="fi-detail-block">
        <h4>OCR detectado</h4>
        {rawText ? (
          <pre className="fi-detail-ocr">{rawText.slice(0, 600)}{rawText.length > 600 ? '…' : ''}</pre>
        ) : (
          <p className="fi-detail-empty">Sin texto OCR disponible para este comprobante.</p>
        )}
      </section>

      <section className="fi-detail-block">
        <h4>Observaciones IA</h4>
        <p className="fi-detail-empty">Aún no hay observaciones IA.</p>
      </section>

      <section className="fi-detail-block">
        <h4>Historial de cambios</h4>
        <p className="fi-detail-empty">El historial se habilitará próximamente.</p>
      </section>
    </aside>
  );
}
