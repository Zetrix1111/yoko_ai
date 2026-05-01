// Registro central de módulos. Para agregar uno nuevo:
// 1) crea la carpeta src/features/modules/<nombre>/ con su Screen.jsx
// 2) agrega un registro aquí (path único + icono de lucide-react)
// 3) engancha la ruta en src/App.jsx (MODULE_COMPONENTS)
//
// Submenús (opcional): si un módulo declara `submenus`, la sidebar
// muestra un acordeón. Cada submenú navega a `${path}?section=<id>`.
// La pantalla del módulo lee ?section= con useSearchParams.
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
} from 'lucide-react';

export const MODULES = [
  {
    id: 'alerta-segura',
    path: '/modulos/alerta-segura',
    name: 'Notificaciones y alertas',
    Icon: ShieldAlert,
    iconClass: 'alert',
  },
  {
    id: 'gestion-caja',
    path: '/modulos/gestion-caja',
    name: 'Gestión de Caja Chica',
    Icon: PiggyBank,
    iconClass: 'finance',
    submenus: [
      { id: 'inicio',        label: 'Inicio',        Icon: LayoutDashboard },
      { id: 'solicitudes',   label: 'Solicitudes',   Icon: FileText        },
      { id: 'aprobaciones',  label: 'Aprobaciones',  Icon: ShieldCheck     },
      { id: 'pagos',         label: 'Pagos',         Icon: CreditCard      },
      { id: 'rendiciones',   label: 'Rendiciones',   Icon: Receipt         },
      { id: 'reportes',      label: 'Reportes',      Icon: BarChart3       },
      { id: 'configuracion', label: 'Configuración', Icon: Settings        },
    ],
  },
  {
    id: 'facturas-inteligentes',
    path: '/modulos/facturas-inteligentes',
    name: 'Facturas Inteligentes',
    Icon: FileText,
    iconClass: 'invoice',
  },
  {
    id: 'cuenta-bancaria',
    path: '/modulos/cuenta-bancaria',
    name: 'Configuración Contable',
    Icon: CreditCard,
    iconClass: 'banking',
  },
];
