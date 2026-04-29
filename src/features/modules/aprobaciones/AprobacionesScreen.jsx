import ModuleLayout from '../ModuleLayout';

// Módulo: Aprobaciones
// Endpoint backend: POST /api/aprobaciones  (api/aprobaciones.py)
export default function AprobacionesScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Gestión de Solicitudes" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
