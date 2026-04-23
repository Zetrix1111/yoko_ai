import ModuleLayout from '../ModuleLayout';

// Módulo: Añadir cuenta bancaria
// Endpoint backend: POST /api/cuenta_bancaria  (api/cuenta_bancaria.py)
export default function CuentaBancariaScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Añadir cuenta bancaria" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
