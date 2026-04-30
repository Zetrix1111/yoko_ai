// Registro central de módulos. Para agregar uno nuevo:
// 1) crea la carpeta src/features/modules/<nombre>/ con su Screen.jsx
// 2) agrega un registro aquí (path único + icono de lucide-react)
// 3) engancha la ruta en src/App.jsx (MODULE_COMPONENTS)
import {
  ShieldAlert,
  CheckSquare,
  Wallet,
  Receipt,
  Banknote,
  FileText,
  CreditCard,
} from 'lucide-react';

export const MODULES = [
  {
    id: 'alerta-segura',
    path: '/modulos/alerta-segura',
    name: 'Solicitudes y alertas',
    Icon: ShieldAlert,
    iconClass: 'alert',
  },
  {
    id: 'aprobaciones',
    path: '/modulos/aprobaciones',
    name: 'Gestión de Solicitudes',
    Icon: CheckSquare,
    iconClass: 'approvals',
    badge: 'Nuevo',
  },
  {
    id: 'caja-chica',
    path: '/modulos/caja-chica',
    name: 'Caja Chica Inteligente',
    Icon: Wallet,
    iconClass: 'cash',
  },
  {
    id: 'solicitud-caja-chica',
    path: '/modulos/solicitud-caja-chica',
    name: 'Rendición de Gastos Inteligente',
    Icon: Receipt,
    iconClass: 'request',
  },
  {
    id: 'pagos-inteligentes',
    path: '/modulos/pagos-inteligentes',
    name: 'Pagos Inteligentes',
    Icon: Banknote,
    iconClass: 'payment',
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
