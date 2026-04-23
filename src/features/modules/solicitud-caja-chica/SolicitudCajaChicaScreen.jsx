import ModuleLayout from '../ModuleLayout';

// Módulo: Solicitud de caja chica
// Endpoint backend: POST /api/solicitud_caja_chica  (api/solicitud_caja_chica.py)
export default function SolicitudCajaChicaScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Solicitud de caja chica" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
