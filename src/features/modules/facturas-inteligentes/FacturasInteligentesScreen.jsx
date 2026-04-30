import ModuleLayout from '../ModuleLayout';

// Módulo: Facturas Inteligentes
// Endpoint backend: POST /api/facturas_inteligentes  (api/facturas_inteligentes.py)
export default function FacturasInteligentesScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Facturas Inteligentes" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
