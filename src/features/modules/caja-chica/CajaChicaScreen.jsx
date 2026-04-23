import ModuleLayout from '../ModuleLayout';

// Módulo: Seguimiento caja chica
// Endpoint backend: POST /api/caja_chica  (api/caja_chica.py)
export default function CajaChicaScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Seguimiento caja chica" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
