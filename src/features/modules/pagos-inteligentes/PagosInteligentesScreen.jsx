import ModuleLayout from '../ModuleLayout';

// Módulo: Pagos Inteligentes
// Endpoint backend: POST /api/pagos_inteligentes  (api/pagos_inteligentes.py)
export default function PagosInteligentesScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Pagos Inteligentes" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
