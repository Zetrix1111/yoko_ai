import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './App.css';

import { useAuth } from './features/auth/useAuth';
import LoginScreen from './features/auth/LoginScreen';
import ErpShell from './features/shell/ErpShell';
import DashboardScreen from './features/dashboard/DashboardScreen';
import { MODULES } from './features/modules/modulesConfig';

import ConfiguracionEmpresaScreen from './features/modules/configuracion-empresa/ConfiguracionEmpresaScreen';
import FacturasInteligentesScreen from './features/modules/facturas-inteligentes/FacturasInteligentesScreen';
import GestionCajaChicaScreen from './features/modules/gestion-caja-chica/GestionCajaChicaScreen';
import VentasInteligentesScreen from './features/modules/ventas-inteligentes/VentasInteligentesScreen';

// Mapeo: id de módulo → componente que renderiza su pantalla.
// Para enchufar un módulo nuevo, solo agrega aquí su entrada.
const MODULE_COMPONENTS = {
  'configuracion-empresa':  ConfiguracionEmpresaScreen,
  'facturas-inteligentes':  FacturasInteligentesScreen,
  'gestion-caja':           GestionCajaChicaScreen,
  'ventas-inteligentes':    VentasInteligentesScreen,
};

function AuthenticatedApp({ user, onLogout }) {
  // Las pantallas de módulo ya no necesitan `onOpenModules` ni `onLogout`
  // como props — el shell provee navegación y logout. Solo les pasamos
  // `user`. (Los props extra que se sigan pasando son ignorados por React.)
  const common = { user };

  // Solo registramos rutas de los módulos que la empresa del usuario logueado
  // tiene habilitados (user.empresa.modulos viene del JWT/login response).
  // Si un user va a /modulos/X y X no está habilitado, cae al "*" → Dashboard.
  const enabledModulos = new Set(user?.empresa?.modulos || []);
  const enabledRoutes = MODULES
    .filter((m) => enabledModulos.has(m.id))
    .map((m) => ({ path: m.path, Comp: MODULE_COMPONENTS[m.id], id: m.id }))
    .filter((r) => r.Comp);

  return (
    <ErpShell user={user} onLogout={onLogout}>
      <Routes>
        <Route path="/" element={<DashboardScreen user={user} />} />
        {enabledRoutes.map(({ id, path, Comp }) => (
          <Route key={id} path={path} element={<Comp {...common} />} />
        ))}
        <Route path="*" element={<DashboardScreen user={user} />} />
      </Routes>
    </ErpShell>
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
