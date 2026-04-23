// Registro central de módulos. Para agregar uno nuevo:
// 1) crea la carpeta src/features/modules/<nombre>/ con su Screen.jsx
// 2) agrega un registro aquí (path único + icono de lucide-react)
// 3) engancha la ruta en src/App.jsx
import { CheckSquare, ShieldAlert, CreditCard, Wallet, Receipt } from 'lucide-react';

export const MODULES = [
  {
    id: 'aprobaciones',
    path: '/modulos/aprobaciones',
    name: 'Módulo aprobaciones',
    Icon: CheckSquare,
    iconClass: 'approvals',
    badge: 'Nuevo',
  },
  {
    id: 'solicitud-caja-chica',
    path: '/modulos/solicitud-caja-chica',
    name: 'Solicitud de caja chica',
    Icon: Receipt,
    iconClass: 'request',
  },
  {
    id: 'alerta-segura',
    path: '/modulos/alerta-segura',
    name: 'Alerta segura',
    Icon: ShieldAlert,
    iconClass: 'alert',
  },
  {
    id: 'cuenta-bancaria',
    path: '/modulos/cuenta-bancaria',
    name: 'Añadir cuenta bancaria',
    Icon: CreditCard,
    iconClass: 'banking',
  },
  {
    id: 'caja-chica',
    path: '/modulos/caja-chica',
    name: 'Seguimiento caja chica',
    Icon: Wallet,
    iconClass: 'cash',
  },
];
