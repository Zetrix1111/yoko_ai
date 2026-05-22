import { useMemo } from 'react';
import { useEmpresa, formatSistemaContable } from '../empresa/EmpresaContext';
import { selectKpisForModulos } from './dashboardKpis';
import UpsellCards from './UpsellCards';
import './DashboardScreen.css';

/**
 * Pantalla de inicio del workspace (ruta `/`).
 *
 * Layout:
 *   1. Header de empresa: razón social + RUC + badge contable + tagline.
 *   2. Grid de 6 KPI cards dinámicos según los módulos contratados.
 *   3. Sección "Sumá más capacidades a Yoko" con cards ghost de módulos
 *      no contratados.
 *
 * Sin saludo personal — el panel IA derecho cumple ese rol. El Dashboard
 * es un tablero corporativo que entra directo al contexto de la empresa.
 */
export default function DashboardScreen({ user }) {
  const { basicos, loading } = useEmpresa();

  const modulosSet = useMemo(() => new Set(user?.empresa?.modulos || []), [user]);
  const sistemaUpper = formatSistemaContable(basicos?.sistema_contable);

  const cards = useMemo(
    () => selectKpisForModulos(modulosSet, basicos?.sistema_contable),
    [modulosSet, basicos?.sistema_contable]
  );

  const tagline = basicos?.sistema_contable
    ? `Yoko es la capa inteligente que opera sobre su ${sistemaUpper} y reduce el tiempo operativo de su equipo.`
    : 'Yoko es la capa inteligente que reduce el tiempo operativo de su equipo.';

  return (
    <div className="erp-dashboard">
      <header className="erp-dashboard-header">
        <div className="erp-dashboard-empresa">
          <div className="erp-dashboard-empresa-text">
            {loading ? (
              <>
                <div className="erp-dashboard-skeleton erp-dashboard-skeleton-title" />
                <div className="erp-dashboard-skeleton erp-dashboard-skeleton-ruc" />
              </>
            ) : (
              <>
                <h1 className="erp-dashboard-razon">
                  {basicos?.razon_social || basicos?.name || 'Tu organización'}
                </h1>
                {basicos?.ruc && (
                  <p className="erp-dashboard-ruc">
                    <span className="erp-dashboard-ruc-label">RUC</span> {basicos.ruc}
                  </p>
                )}
              </>
            )}
          </div>
          {!loading && basicos?.sistema_contable && (
            <div className="erp-dashboard-badge-contable">
              <span className="erp-dashboard-badge-contable-label">Sistema contable</span>
              <span className="erp-dashboard-badge-contable-value">{sistemaUpper}</span>
            </div>
          )}
        </div>
        <p className="erp-dashboard-tagline">{tagline}</p>
      </header>

      <section className="erp-dashboard-grid" aria-label="Indicadores">
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

      <UpsellCards
        modulosSet={modulosSet}
        sistemaContable={basicos?.sistema_contable}
      />
    </div>
  );
}
