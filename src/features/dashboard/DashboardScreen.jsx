import {
  FileText,
  CheckCircle2,
  CreditCard,
  Receipt,
  Wallet,
  ClipboardList,
} from 'lucide-react';
import './DashboardScreen.css';

/**
 * Pantalla de inicio del workspace (ruta `/`). Maqueta con 6 KPI cards
 * sin lógica — los números son `—` placeholder. Se conectan a fetches
 * reales en un plan futuro.
 *
 * Cada card lleva un ícono pequeño, un valor grande y un label.
 */
export default function DashboardScreen({ user }) {
  const nombre = (user?.nombre || '').split(' ')[0] || 'usuario';

  const cards = [
    {
      id: 'solicitudes-pendientes',
      label: 'Solicitudes pendientes',
      value: '—',
      Icon: FileText,
      hint: 'Esperando aprobación',
    },
    {
      id: 'aprobaciones-pendientes',
      label: 'Aprobaciones pendientes',
      value: '—',
      Icon: CheckCircle2,
      hint: 'En tu cola',
    },
    {
      id: 'pagos-por-procesar',
      label: 'Pagos por procesar',
      value: '—',
      Icon: CreditCard,
      hint: 'Tesorería',
    },
    {
      id: 'facturas-mes',
      label: 'Facturas del mes',
      value: '—',
      Icon: Receipt,
      hint: 'Mes en curso',
    },
    {
      id: 'egresos-cc',
      label: 'Egresos caja chica',
      value: 'S/ —',
      Icon: Wallet,
      hint: 'Mes en curso',
    },
    {
      id: 'rendiciones-revisar',
      label: 'Rendiciones por revisar',
      value: '—',
      Icon: ClipboardList,
      hint: 'Comprobantes pendientes',
    },
  ];

  return (
    <div className="erp-dashboard">
      <header className="erp-dashboard-header">
        <h1>Hola, {nombre} 👋</h1>
        <p>Acá tenés un resumen de tu operación. Los datos se llenan automáticamente.</p>
      </header>

      <section className="erp-dashboard-grid" aria-label="KPIs">
        {cards.map((card) => (
          <article key={card.id} className="erp-kpi-card">
            <div className="erp-kpi-card-top">
              <span className="erp-kpi-icon">
                <card.Icon size={18} />
              </span>
              <span className="erp-kpi-hint">{card.hint}</span>
            </div>
            <div className="erp-kpi-value">{card.value}</div>
            <div className="erp-kpi-label">{card.label}</div>
          </article>
        ))}
      </section>

      <p className="erp-dashboard-note">
        ℹ️ Los indicadores aún están en modo maqueta. La conexión con los datos reales se
        habilitará en próximas iteraciones.
      </p>
    </div>
  );
}
