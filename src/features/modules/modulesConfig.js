// Registro central de módulos. Para agregar uno nuevo:
// 1) crea la carpeta src/features/modules/<nombre>/ con su Screen.jsx
// 2) agrega un registro aquí (path único + icono de lucide-react)
// 3) engancha la ruta en src/App.jsx
import { CheckSquare, Wallet, Receipt, CreditCard, ShieldAlert } from 'lucide-react';

export const MODULES = [
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
    id: 'cuenta-bancaria',
    path: '/modulos/cuenta-bancaria',
    name: 'Configuración Contable',
    Icon: CreditCard,
    iconClass: 'banking',
  },
  {
    id: 'alerta-segura',
    path: '/modulos/alerta-segura',
    name: 'Alerta segura',
    Icon: ShieldAlert,
    iconClass: 'alert',
  },
];
