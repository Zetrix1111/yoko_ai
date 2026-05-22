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
  MessageSquareText,
  Smartphone,
  Download,
} from 'lucide-react';

export const MODULES = [
  {
    id: 'ventas-inteligentes',
    path: '/modulos/ventas-inteligentes',
    name: 'Ventas Inteligentes',
    Icon: Sparkles,
    iconClass: 'sales',
    submenus: [
      { id: 'inicio',           label: 'Dashboard',          Icon: LayoutDashboard },
      { id: 'respuestas-ia',    label: 'Respuestas IA',      Icon: MessageSquareText },
      { id: 'clientes',         label: 'Clientes',           Icon: Users },
      { id: 'productos',        label: 'Productos',          Icon: Package },
      { id: 'whatsapp',         label: 'WhatsApp',           Icon: Smartphone },
      { id: 'config-agente',    label: 'Configuración',      Icon: Settings },
    ],
  },
  {
    id: 'gestion-caja',
    path: '/modulos/gestion-caja',
    name: 'Caja Chica',
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
    id: 'facturas-inteligentes',
    path: '/modulos/facturas-inteligentes',
    name: 'Facturas Inteligentes',
    Icon: FileText,
    iconClass: 'invoice',
    submenus: [
      { id: 'inicio',        label: 'Dashboard',     Icon: LayoutDashboard },
      { id: 'procesos',      label: 'Procesos',      Icon: Package },
      { id: 'revision',      label: 'Revisión',      Icon: Receipt },
      { id: 'exportaciones', label: 'Exportaciones', Icon: Download },
    ],
  },
  {
    // Módulo aún no disponible. Se muestra en la sidebar atenuado, con
    // badge "Próximamente", para comunicar la oferta completa del producto.
    // No es clickeable porque no tiene Screen en `MODULE_COMPONENTS`.
    id: 'planilla-inteligente',
    path: '/modulos/planilla-inteligente',
    name: 'Planilla',
    Icon: Users,
    iconClass: 'sales',
    upcoming: true,
  },
  {
    id: 'configuracion-empresa',
    path: '/modulos/configuracion-empresa',
    name: 'Configuración',
    Icon: Building2,
    iconClass: 'banking',
  },
];
