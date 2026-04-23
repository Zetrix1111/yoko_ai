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

function AuthenticatedApp({ user }) {
  const [showMobileModules, setShowMobileModules] = useState(false);
  const openModules = () => setShowMobileModules(true);
  const closeModules = () => setShowMobileModules(false);

  return (
    <div className="app-container">
      <div className="main-layout">
        <Routes>
          <Route
            path="/"
            element={<ChatScreen user={user} onOpenModules={openModules} />}
          />
          <Route
            path="/modulos/aprobaciones"
            element={<AprobacionesScreen user={user} onOpenModules={openModules} />}
          />
          <Route
            path="/modulos/alerta-segura"
            element={<AlertaSeguraScreen user={user} onOpenModules={openModules} />}
          />
          <Route
            path="/modulos/cuenta-bancaria"
            element={<CuentaBancariaScreen user={user} onOpenModules={openModules} />}
          />
          <Route
            path="/modulos/caja-chica"
            element={<CajaChicaScreen user={user} onOpenModules={openModules} />}
          />
          <Route
            path="/modulos/solicitud-caja-chica"
            element={<SolicitudCajaChicaScreen user={user} onOpenModules={openModules} />}
          />
          <Route
            path="*"
            element={<ChatScreen user={user} onOpenModules={openModules} />}
          />
        </Routes>
        <ModulesSidebar show={showMobileModules} onClose={closeModules} />
      </div>
    </div>
  );
}

export default function App() {
  const { user, error, isAuthenticating, login, clearError } = useAuth();

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
      <AuthenticatedApp user={user} />
    </BrowserRouter>
  );
}
