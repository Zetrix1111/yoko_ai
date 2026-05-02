// Datos de ejemplo para el módulo Ventas Omnicanal con IA.
// Reemplazar por llamadas reales al backend cuando se integre con Make/Airtable.

export const STATS = {
  totalLeads:           1250,
  conversacionesActivas: 320,
  ventasCerradas:       42500,
  clientesCalientes:    85,
};

// Mini embudo para el dashboard. 3 etapas simplificadas.
export const FUNNEL = [
  { id: 'nuevos',      label: 'Nuevos',      count: 524, variant: 'info' },
  { id: 'interesados', label: 'Interesados', count: 382, variant: 'warning' },
  { id: 'cerrados',    label: 'Cerrados',    count: 142, variant: 'success' },
];

export const ACTIVIDAD = [
  { id: 'AC-018', cliente: 'Juan Pérez',    canal: 'whatsapp',  asunto: 'Consulta producto X',     estado: 'interesado',   fecha: '2026-05-02' },
  { id: 'AC-017', cliente: 'María Quispe',  canal: 'instagram', asunto: 'Solicitud de cotización', estado: 'negociacion',  fecha: '2026-05-02' },
  { id: 'AC-016', cliente: 'Carlos Ruiz',   canal: 'web',       asunto: 'Compra realizada',        estado: 'cerrado',      fecha: '2026-05-02' },
  { id: 'AC-015', cliente: 'Ana Torres',    canal: 'messenger', asunto: 'Pregunta de precios',     estado: 'nuevo',        fecha: '2026-05-01' },
  { id: 'AC-014', cliente: 'Luis Mendoza',  canal: 'whatsapp',  asunto: 'Disponibilidad de stock', estado: 'interesado',   fecha: '2026-05-01' },
];

export const CANALES = [
  { id: 'whatsapp',  nombre: 'WhatsApp Business',  conectado: true,  numero: '+51 987 654 321', mensajesHoy: 142 },
  { id: 'facebook',  nombre: 'Facebook',           conectado: true,  numero: 'CMejíaSAC',       mensajesHoy: 38  },
  { id: 'instagram', nombre: 'Instagram',          conectado: true,  numero: '@cmejia.oficial', mensajesHoy: 65  },
  { id: 'linkedin',  nombre: 'LinkedIn',           conectado: false, numero: '—',                mensajesHoy: 0   },
];

export const PRODUCTOS = [
  { id: 1, nombre: 'Banco de condensadores 24kV', precio: 12500, descripcion: 'Para subestaciones de media tensión' },
  { id: 2, nombre: 'Transformador 100 kVA',       precio: 18900, descripcion: 'Trifásico, refrigerado en aceite' },
  { id: 3, nombre: 'Cable XLPE 500m',             precio: 4250,  descripcion: 'Aislamiento polietileno reticulado' },
  { id: 4, nombre: 'Servicio mantenimiento',      precio: 3500,  descripcion: 'Inspección anual de subestaciones' },
  { id: 5, nombre: 'Tablero de distribución',     precio: 6800,  descripcion: 'Capacidad 200A con interruptores' },
  { id: 6, nombre: 'Asesoría técnica',            precio: 1200,  descripcion: 'Consultoría especializada por hora' },
];

export const CLIENTES = [
  { id: 'CL-1024', nombre: 'Juan Pérez',     canal: 'whatsapp',  estado: 'interesado',   ultimoMensaje: 'Me interesan más detalles del producto…',   fecha: '2026-05-02' },
  { id: 'CL-1023', nombre: 'María Quispe',   canal: 'instagram', estado: 'negociacion',  ultimoMensaje: '¿Tienen descuento por volumen?',           fecha: '2026-05-02' },
  { id: 'CL-1022', nombre: 'Carlos Ruiz',    canal: 'web',       estado: 'cerrado',      ultimoMensaje: '¡Gracias! Recibí el comprobante.',         fecha: '2026-05-02' },
  { id: 'CL-1021', nombre: 'Ana Torres',     canal: 'messenger', estado: 'nuevo',        ultimoMensaje: 'Hola, quería preguntar precios…',          fecha: '2026-05-01' },
  { id: 'CL-1020', nombre: 'Luis Mendoza',   canal: 'whatsapp',  estado: 'interesado',   ultimoMensaje: 'Confirmo, mándame la cotización formal.',  fecha: '2026-05-01' },
  { id: 'CL-1019', nombre: 'Patricia Vega',  canal: 'web',       estado: 'negociacion',  ultimoMensaje: 'Estamos coordinando con el área técnica.', fecha: '2026-05-01' },
  { id: 'CL-1018', nombre: 'Roberto Silva',  canal: 'whatsapp',  estado: 'frio',         ultimoMensaje: 'Lo voy a pensar, te aviso.',                fecha: '2026-04-25' },
];

export const CANAL_LABELS = {
  whatsapp:  'WhatsApp',
  facebook:  'Facebook',
  instagram: 'Instagram',
  linkedin:  'LinkedIn',
  messenger: 'Messenger',
  web:       'Web Chat',
};

export const ESTADO_LABELS = {
  nuevo:       'Nuevo',
  interesado:  'Interesado',
  negociacion: 'Negociación',
  cerrado:     'Cerrado',
  frio:        'Frío',
};

export const formatPEN = (n) =>
  `S/ ${Number(n).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const formatNum = (n) => Number(n).toLocaleString('es-PE');

export const formatDate = (iso) => {
  if (!iso) return '';
  const [y, m, d] = iso.split(' ')[0].split('-');
  return `${d}/${m}/${y}`;
};
