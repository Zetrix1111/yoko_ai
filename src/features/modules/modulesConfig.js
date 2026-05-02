// Registro central de módulos. Para agregar uno nuevo:
// 1) crea la carpeta src/features/modules/<nombre>/ con su Screen.jsx
// 2) agrega un registro aquí (path único + icono de lucide-react)
// 3) engancha la ruta en src/App.jsx (MODULE_COMPONENTS)
//
// Submenús (opcional): si un módulo declara `submenus`, la sidebar
// muestra un acordeón. Cada submenú navega a `${path}?section=<id>`.
// La pantalla del módulo lee ?section= con useSearchParams.
//
// externalUrl (opcional): si un módulo o submenú lo declara, en vez
// de navegar internamente, abre esa URL en nueva pestaña.
import {
  ShieldAlert,
  FileText,
  CreditCard,
  PiggyBank,
  LayoutDashboard,
  ShieldCheck,
  Receipt,
  BarChart3,
  Settings,
  Building2,
  Sparkles,
  Package,
  Users,
} from 'lucide-react';

export const MODULES = [
  {
    id: 'gestion-caja',
    path: '/modulos/gestion-caja',
    name: 'Gestión de Caja Chica',
    Icon: PiggyBank,
    iconClass: 'finance',
    submenus: [
      { id: 'inicio', label: 'Dashboard', Icon: LayoutDashboard },
      { id: 'solicitudes', label: 'Solicitudes', Icon: FileText },
      {
        id: 'aprobaciones', label: 'Aprobaciones', Icon: ShieldCheck,
        externalUrl: 'https://aprobaciones.luna.com.pe/'
      },
      { id: 'pagos', label: 'Pagos', Icon: CreditCard },
      { id: 'rendiciones', label: 'Rendiciones', Icon: Receipt },
      { id: 'reportes', label: 'Reportes', Icon: BarChart3 },
      { id: 'configuracion', label: 'Configuración', Icon: Settings },
    ],
  },
  {
    id: 'ventas-inteligentes',
    path: '/modulos/ventas-inteligentes',
    name: 'Ventas Inteligentes',
    Icon: Sparkles,
    iconClass: 'sales',
    submenus: [
      { id: 'inicio',        label: 'Dashboard',     Icon: LayoutDashboard },
      { id: 'clientes',      label: 'Clientes',      Icon: Users },
      { id: 'productos',     label: 'Productos',     Icon: Package },
      { id: 'configuracion', label: 'Configuración', Icon: Settings },
    ],
  },
  {
    id: 'facturas-inteligentes',
    path: '/modulos/facturas-inteligentes',
    name: 'Facturas Inteligentes (BETA)',
    Icon: FileText,
    iconClass: 'invoice',
  },
  {
    id: 'configuracion-empresa',
    path: '/modulos/configuracion-empresa',
    name: 'Configuración',
    Icon: Building2,
    iconClass: 'banking',
  },
  {
    id: 'alerta-segura',
    path: '/modulos/alerta-segura',
    name: 'Notificaciones y alertas',
    Icon: ShieldAlert,
    iconClass: 'alert',
    externalUrl: 'https://alertasegura.luna.com.pe/alerta_segura_cmejia.html',
  },
];
