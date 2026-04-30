import ModuleLayout from '../ModuleLayout';

// Módulo: Alerta Segura
// Endpoint backend: POST /api/alerta_segura  (api/alerta_segura.py)
export default function AlertaSeguraScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Solicitudes y alertas" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
