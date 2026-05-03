import ModuleLayout from '../ModuleLayout';

// Módulo: Alerta Segura
// El módulo se abre como externalUrl en alertasegura.luna.com.pe; este screen
// solo se renderiza si llegan via deep-link.
export default function AlertaSeguraScreen({ user, onOpenModules, onLogout }) {
  return (
    <ModuleLayout title="Notificaciones y alertas" onOpenModules={onOpenModules} onLogout={onLogout}>
      {/* Construye aquí el formulario. */}
    </ModuleLayout>
  );
}
