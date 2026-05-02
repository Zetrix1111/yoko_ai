import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './App.css';

import { useAuth } from './features/auth/useAuth';
import LoginScreen from './features/auth/LoginScreen';
import ChatScreen from './features/chat/ChatScreen';
import ModulesSidebar from './features/modules/ModulesSidebar';
import { MODULES } from './features/modules/modulesConfig';
import { isModuleEnabled } from './tenants';

import AlertaSeguraScreen from './features/modules/alerta-segura/AlertaSeguraScreen';
import ConfiguracionEmpresaScreen from './features/modules/configuracion-empresa/ConfiguracionEmpresaScreen';
import FacturasInteligentesScreen from './features/modules/facturas-inteligentes/FacturasInteligentesScreen';
import GestionCajaChicaScreen from './features/modules/gestion-caja-chica/GestionCajaChicaScreen';
import VentasInteligentesScreen from './features/modules/ventas-inteligentes/VentasInteligentesScreen';

// Mapeo: id de módulo → componente que renderiza su pantalla.
// Para enchufar un módulo nuevo, solo agrega aquí su entrada.
const MODULE_COMPONENTS = {
  'alerta-segura':          AlertaSeguraScreen,
  'configuracion-empresa':  ConfiguracionEmpresaScreen,
  'facturas-inteligentes':  FacturasInteligentesScreen,
  'gestion-caja':           GestionCajaChicaScreen,
  'ventas-inteligentes':    VentasInteligentesScreen,
};

function AuthenticatedApp({ user, onLogout }) {
  const [showMobileModules, setShowMobileModules] = useState(false);
  const openModules = () => setShowMobileModules(true);
  const closeModules = () => setShowMobileModules(false);

  const common = { user, onOpenModules: openModules, onLogout };

  // Solo registramos rutas de los módulos que el tenant tiene habilitados.
  // Si un user va a /modulos/X y X no está habilitado, cae al "*" → ChatScreen.
  const enabledRoutes = MODULES
    .filter((m) => isModuleEnabled(m.id))
    .map((m) => ({ path: m.path, Comp: MODULE_COMPONENTS[m.id], id: m.id }))
    .filter((r) => r.Comp);

  return (
    <div className="app-container">
      <div className="main-layout">
        <Routes>
          <Route path="/" element={<ChatScreen {...common} />} />
          {enabledRoutes.map(({ id, path, Comp }) => (
            <Route key={id} path={path} element={<Comp {...common} />} />
          ))}
          <Route path="*" element={<ChatScreen {...common} />} />
        </Routes>
        <ModulesSidebar show={showMobileModules} onClose={closeModules} />
      </div>
    </div>
  );
}

export default function App() {
  const { user, error, isAuthenticating, login, logout, clearError } = useAuth();

  if (!user) {
    return (
      <LoginScreen
        onLogin={login}
        error={error}
        isAuthenticating={isAuthenticating}
        clearError={clearError}
      />
    );
  }

  return (
    <BrowserRouter>
      <AuthenticatedApp user={user} onLogout={logout} />
    </BrowserRouter>
  );
}
