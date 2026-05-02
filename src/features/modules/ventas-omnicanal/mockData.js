// Datos de ejemplo para el módulo Ventas Omnicanal con IA.
// Reemplazar por llamadas reales al backend cuando se integre con Make/Airtable.

export const STATS = {
  totalLeads:           1250,
  conversacionesActivas: 320,
  ventasCerradas:       42500,
  clientesCalientes:    85,
};

export const ACTIVIDAD = [
  { id: 'AC-018', cliente: 'Juan Pérez',    canal: 'whatsapp',  asunto: 'Consulta producto X',         estado: 'interesado',   fecha: '2026-05-02' },
  { id: 'AC-017', cliente: 'María Quispe',  canal: 'instagram', asunto: 'Solicitud de cotización',     estado: 'negociacion',  fecha: '2026-05-02' },
  { id: 'AC-016', cliente: 'Carlos Ruiz',   canal: 'web',       asunto: 'Compra realizada',            estado: 'cerrado',      fecha: '2026-05-02' },
  { id: 'AC-015', cliente: 'Ana Torres',    canal: 'messenger', asunto: 'Pregunta de precios',         estado: 'nuevo',        fecha: '2026-05-01' },
  { id: 'AC-014', cliente: 'Luis Mendoza',  canal: 'whatsapp',  asunto: 'Disponibilidad de stock',     estado: 'interesado',   fecha: '2026-05-01' },
  { id: 'AC-013', cliente: 'Patricia Vega', canal: 'web',       asunto: 'Reclamo post-venta',          estado: 'negociacion',  fecha: '2026-05-01' },
];

export const CANALES = [
  { id: 'whatsapp',  nombre: 'WhatsApp Business', conectado: true,  numero: '+51 987 654 321', mensajesHoy: 142 },
  { id: 'messenger', nombre: 'Facebook Messenger', conectado: true,  numero: 'CMejíaSAC',       mensajesHoy: 38  },
  { id: 'instagram', nombre: 'Instagram DM',       conectado: true,  numero: '@cmejia.oficial', mensajesHoy: 65  },
  { id: 'web',       nombre: 'Web Chat',           conectado: true,  numero: 'cmejia.com.pe',   mensajesHoy: 21  },
  { id: 'telegram',  nombre: 'Telegram',           conectado: false, numero: '—',                mensajesHoy: 0   },
];

export const FLUJO_IA = [
  { id: 'bienvenida',    titulo: 'Mensaje de bienvenida',         descripcion: 'Saludo inicial cuando un nuevo cliente escribe.', activo: true  },
  { id: 'calificacion',  titulo: 'Calificación automática',        descripcion: 'Detecta si el cliente es prospecto, comprador o consulta general.', activo: true  },
  { id: 'intencion',     titulo: 'Detección de intención',         descripcion: 'Distingue entre intención de comprar, consultar o cotizar.', activo: true  },
  { id: 'respuestas',    titulo: 'Respuestas automáticas',         descripcion: 'Responde preguntas frecuentes sin intervención humana.', activo: true  },
  { id: 'escalamiento',  titulo: 'Escalamiento a humano',          descripcion: 'Pasa el chat a un vendedor cuando la IA no puede resolver.', activo: false },
];

export const PRODUCTOS = [
  { id: 1, nombre: 'Banco de condensadores 24kV',     precio: 12500, descripcion: 'Para subestaciones de media tensión',     stock: 8  },
  { id: 2, nombre: 'Transformador 100 kVA',           precio: 18900, descripcion: 'Trifásico, refrigerado en aceite',         stock: 3  },
  { id: 3, nombre: 'Cable XLPE 500m',                 precio: 4250,  descripcion: 'Aislamiento polietileno reticulado',       stock: 24 },
  { id: 4, nombre: 'Servicio mantenimiento',          precio: 3500,  descripcion: 'Inspección anual de subestaciones',        stock: null },
  { id: 5, nombre: 'Tablero de distribución',         precio: 6800,  descripcion: 'Capacidad 200A con interruptores',         stock: 12 },
];

export const PIPELINE_ETAPAS = [
  { id: 'nuevo',       label: 'Nuevo Lead' },
  { id: 'interesado',  label: 'Interesado' },
  { id: 'cotizacion',  label: 'Cotización enviada' },
  { id: 'negociacion', label: 'Negociación' },
  { id: 'cerrado',     label: 'Cerrado' },
];

export const PIPELINE_CLIENTES = [
  { id: 'L-201', nombre: 'Juan Pérez',     monto: 8500,   etapa: 'nuevo',       canal: 'whatsapp' },
  { id: 'L-202', nombre: 'María Quispe',   monto: 15200,  etapa: 'cotizacion',  canal: 'instagram' },
  { id: 'L-203', nombre: 'Carlos Ruiz',    monto: 4500,   etapa: 'cerrado',     canal: 'web' },
  { id: 'L-204', nombre: 'Ana Torres',     monto: 2300,   etapa: 'interesado',  canal: 'messenger' },
  { id: 'L-205', nombre: 'Luis Mendoza',   monto: 19800,  etapa: 'negociacion', canal: 'whatsapp' },
  { id: 'L-206', nombre: 'Patricia Vega',  monto: 3200,   etapa: 'interesado',  canal: 'web' },
  { id: 'L-207', nombre: 'Roberto Silva',  monto: 11500,  etapa: 'nuevo',       canal: 'whatsapp' },
  { id: 'L-208', nombre: 'Diana Castillo', monto: 6700,   etapa: 'negociacion', canal: 'instagram' },
  { id: 'L-209', nombre: 'Gabriel Ramos',  monto: 9200,   etapa: 'cotizacion',  canal: 'web' },
  { id: 'L-210', nombre: 'Sofía Morales',  monto: 5400,   etapa: 'cerrado',     canal: 'whatsapp' },
];

export const AUTOMATIZACIONES = [
  { id: 1, nombre: 'Enviar cotización automática',        descripcion: 'Cuando el cliente pide precios, la IA arma y envía la cotización en PDF.', activa: true  },
  { id: 2, nombre: 'Seguimiento automático a 24h',         descripcion: 'Si el lead no responde, envía un recordatorio amable al día siguiente.', activa: true  },
  { id: 3, nombre: 'Notificación al vendedor',             descripcion: 'Avisa por email/Slack al vendedor cuando un lead pasa a "negociación".', activa: true  },
  { id: 4, nombre: 'Registro en sistema contable',         descripcion: 'Cuando una venta se cierra, crea el comprobante en CONCAR automáticamente.', activa: false },
  { id: 5, nombre: 'Reactivación de lead frío',            descripcion: 'Después de 7 días sin actividad, reabre la conversación con una promo.', activa: false },
];

export const TRAINING = [
  { id: 'faq',         titulo: 'Preguntas frecuentes',     items: 24, ultimaEdicion: '2026-04-28' },
  { id: 'objeciones',  titulo: 'Objeciones de clientes',   items: 12, ultimaEdicion: '2026-04-22' },
  { id: 'scripts',     titulo: 'Scripts de venta',         items: 8,  ultimaEdicion: '2026-04-15' },
  { id: 'tono',        titulo: 'Tono de comunicación',     items: 1,  ultimaEdicion: '2026-04-10' },
];

export const CLIENTES = [
  { id: 'CL-1024', nombre: 'Juan Pérez',     canal: 'whatsapp',  estado: 'interesado',   ultimaInteraccion: '2026-05-02', email: 'juan.perez@gmail.com' },
  { id: 'CL-1023', nombre: 'María Quispe',   canal: 'instagram', estado: 'negociacion',  ultimaInteraccion: '2026-05-02', email: 'mquispe@hotmail.com' },
  { id: 'CL-1022', nombre: 'Carlos Ruiz',    canal: 'web',       estado: 'cerrado',      ultimaInteraccion: '2026-05-02', email: 'cruiz@empresa.com' },
  { id: 'CL-1021', nombre: 'Ana Torres',     canal: 'messenger', estado: 'nuevo',        ultimaInteraccion: '2026-05-01', email: 'atorres@gmail.com' },
  { id: 'CL-1020', nombre: 'Luis Mendoza',   canal: 'whatsapp',  estado: 'interesado',   ultimaInteraccion: '2026-05-01', email: 'lmendoza@yahoo.com' },
  { id: 'CL-1019', nombre: 'Patricia Vega',  canal: 'web',       estado: 'negociacion',  ultimaInteraccion: '2026-05-01', email: 'pvega@gmail.com' },
  { id: 'CL-1018', nombre: 'Roberto Silva',  canal: 'whatsapp',  estado: 'frio',         ultimaInteraccion: '2026-04-25', email: 'rsilva@gmail.com' },
];

export const NOTIFICACIONES = [
  { id: 'N-301', tipo: 'lead',      mensaje: 'Nuevo lead recibido por WhatsApp: Juan Pérez',                fecha: '2026-05-02 14:32' },
  { id: 'N-300', tipo: 'caliente',  mensaje: 'María Quispe pasó a "negociación" — listo para cerrar',        fecha: '2026-05-02 13:15' },
  { id: 'N-299', tipo: 'venta',     mensaje: 'Venta cerrada: Carlos Ruiz por S/ 4,500',                       fecha: '2026-05-02 11:48' },
  { id: 'N-298', tipo: 'lead',      mensaje: 'Nuevo lead recibido por Instagram: Diana Castillo',             fecha: '2026-05-02 10:22' },
  { id: 'N-297', tipo: 'caliente',  mensaje: 'Luis Mendoza pidió cotización formal — atender hoy',            fecha: '2026-05-02 09:05' },
];

export const CANAL_LABELS = {
  whatsapp:  'WhatsApp',
  messenger: 'Messenger',
  instagram: 'Instagram',
  web:       'Web Chat',
  telegram:  'Telegram',
};

export const ESTADO_LABELS = {
  nuevo:       'Nuevo lead',
  interesado:  'Interesado',
  cotizacion:  'Cotización',
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
