import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './App.css';

import { useAuth } from './features/auth/useAuth';
import LoginScreen from './features/auth/LoginScreen';
import ChatScreen from './features/chat/ChatScreen';
import ModulesSidebar from './features/modules/ModulesSidebar';
import AprobacionesScreen from './features/modules/aprobaciones/AprobacionesScreen';
import AlertaSeguraScreen from './features/modules/alerta-segura/AlertaSeguraScreen';
import CuentaBancariaScreen from './features/modules/cuenta-bancaria/CuentaBancariaScreen';
import CajaChicaScreen from './features/modules/caja-chica/CajaChicaScreen';
import SolicitudCajaChicaScreen from './features/modules/solicitud-caja-chica/SolicitudCajaChicaScreen';

function AuthenticatedApp({ user, onLogout }) {
  const [showMobileModules, setShowMobileModules] = useState(false);
  const openModules = () => setShowMobileModules(true);
  const closeModules = () => setShowMobileModules(false);

  const common = { user, onOpenModules: openModules, onLogout };

  return (
    <div className="app-container">
      <div className="main-layout">
        <Routes>
          <Route path="/"                                   element={<ChatScreen {...common} />} />
          <Route path="/modulos/aprobaciones"               element={<AprobacionesScreen {...common} />} />
          <Route path="/modulos/alerta-segura"              element={<AlertaSeguraScreen {...common} />} />
          <Route path="/modulos/cuenta-bancaria"            element={<CuentaBancariaScreen {...common} />} />
          <Route path="/modulos/caja-chica"                 element={<CajaChicaScreen {...common} />} />
          <Route path="/modulos/solicitud-caja-chica"       element={<SolicitudCajaChicaScreen {...common} />} />
          <Route path="*"                                   element={<ChatScreen {...common} />} />
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
