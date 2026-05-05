// Enlaces rápidos a Excel compartidos en SharePoint (abren en nueva pestaña).
// Para agregar uno nuevo: agrega un objeto aquí. Si `url` está vacío, el
// botón aparece deshabilitado (sin click).
import { TrendingUp, ClipboardList, ShieldAlert } from 'lucide-react';

export const QUICK_LINKS = [
  {
    id: 'flujo-caja',
    name: 'Flujo de caja',
    url: 'https://cmejiacontratistas-my.sharepoint.com/:x:/g/personal/jechevarria_cmejia_com_pe/IQABRi84qq2FSoA-95Srpsc6AYRATJ5Gmxl037V7gCforhk?e=ujZ6Fe',
    Icon: TrendingUp,
    color: '#107C41', // verde Excel
  },
  {
    id: 'control-ops',
    name: 'Control OPs',
    url: 'https://cmejiacontratistas-my.sharepoint.com/:x:/g/personal/rgiron_cmejia_com_pe/IQD4TOFSecvYToNflozLr6ErAcJJUTsScEDOhyIfJobAu6o?e=mz37aF',
    Icon: ClipboardList,
    color: '#2B7CD3', // azul
  },
  {
    id: 'alerta-segura',
    name: 'Alerta segura',
    url: 'https://alertasegura.luna.com.pe/alerta_segura_cmejia.html',
    Icon: ShieldAlert,
    color: '#B45309', // ámbar
  },
];
