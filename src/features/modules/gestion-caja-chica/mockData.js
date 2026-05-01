// Datos de ejemplo para el módulo. Reemplazar por llamadas reales al backend
// cuando se integre con Make/Airtable.

export const STATS = {
  totalSolicitado: 28450,
  totalAprobado: 21300,
  totalPagado: 17800,
  pendienteRendir: 8200,
};

export const SOLICITUDES = [
  { id: 'SOL-0142', solicitante: 'Juan Pérez',     area: 'Operaciones', monto: 1200, tipo: 'caja-chica', estado: 'pendiente',  fecha: '2026-04-22', motivo: 'Compra de materiales eléctricos' },
  { id: 'SOL-0141', solicitante: 'María Quispe',   area: 'Logística',   monto: 850,  tipo: 'rendir',     estado: 'aprobada',   fecha: '2026-04-22', motivo: 'Movilidad obra Pucallpa' },
  { id: 'SOL-0140', solicitante: 'Carlos Ruiz',    area: 'Ventas',      monto: 350,  tipo: 'caja-chica', estado: 'pagada',     fecha: '2026-04-21', motivo: 'Refrigerio reunión cliente' },
  { id: 'SOL-0139', solicitante: 'Ana Torres',     area: 'Contabilidad',monto: 500,  tipo: 'caja-chica', estado: 'aprobada',   fecha: '2026-04-21', motivo: 'Útiles de oficina' },
  { id: 'SOL-0138', solicitante: 'Luis Mendoza',   area: 'Operaciones', monto: 2400, tipo: 'rendir',     estado: 'pendiente',  fecha: '2026-04-20', motivo: 'Viaje supervisión' },
  { id: 'SOL-0137', solicitante: 'Patricia Vega',  area: 'RR.HH.',      monto: 180,  tipo: 'caja-chica', estado: 'rechazada',  fecha: '2026-04-20', motivo: 'Trámite documentación' },
  { id: 'SOL-0136', solicitante: 'Roberto Silva',  area: 'Logística',   monto: 1500, tipo: 'rendir',     estado: 'pagada',     fecha: '2026-04-19', motivo: 'Combustible flota' },
];

export const APROBACIONES = [
  { id: 'APR-0058', solicitudId: 'SOL-0142', solicitante: 'Juan Pérez',   area: 'Operaciones', monto: 1200, estado: 'pendiente' },
  { id: 'APR-0057', solicitudId: 'SOL-0138', solicitante: 'Luis Mendoza', area: 'Operaciones', monto: 2400, estado: 'pendiente' },
  { id: 'APR-0056', solicitudId: 'SOL-0141', solicitante: 'María Quispe', area: 'Logística',   monto: 850,  estado: 'aprobada'  },
  { id: 'APR-0055', solicitudId: 'SOL-0139', solicitante: 'Ana Torres',   area: 'Contabilidad',monto: 500,  estado: 'aprobada'  },
];

export const PAGOS = [
  { id: 'PAG-0091', solicitudId: 'SOL-0140', monto: 350,  medio: 'efectivo',     cuenta: 'Caja chica gerencia', estado: 'pagado'    },
  { id: 'PAG-0090', solicitudId: 'SOL-0136', monto: 1500, medio: 'transferencia',cuenta: 'BCP 194-...-0451',    estado: 'pagado'    },
  { id: 'PAG-0089', solicitudId: 'SOL-0141', monto: 850,  medio: 'yape',         cuenta: '987 654 321',         estado: 'pendiente' },
  { id: 'PAG-0088', solicitudId: 'SOL-0139', monto: 500,  medio: 'transferencia',cuenta: 'BBVA 0011-...-2345',  estado: 'pendiente' },
];

export const RENDICIONES = [
  { id: 'REN-0033', usuario: 'Carlos Ruiz',    entregado: 350,  rendido: 350,  diferencia: 0,   estado: 'rendida'   },
  { id: 'REN-0032', usuario: 'Roberto Silva',  entregado: 1500, rendido: 1420, diferencia: 80,  estado: 'parcial'   },
  { id: 'REN-0031', usuario: 'María Quispe',   entregado: 850,  rendido: 0,    diferencia: 850, estado: 'pendiente' },
  { id: 'REN-0030', usuario: 'Luis Mendoza',   entregado: 2400, rendido: 2380, diferencia: 20,  estado: 'parcial'   },
];

export const REPORTE_AREAS = [
  { area: 'Operaciones',  monto: 9800 },
  { area: 'Logística',    monto: 6200 },
  { area: 'Ventas',       monto: 3450 },
  { area: 'Contabilidad', monto: 2100 },
  { area: 'RR.HH.',       monto: 1180 },
];

export const REPORTE_USUARIOS = [
  { usuario: 'Juan Pérez',     monto: 4200 },
  { usuario: 'Luis Mendoza',   monto: 3800 },
  { usuario: 'María Quispe',   monto: 2900 },
  { usuario: 'Roberto Silva',  monto: 2400 },
  { usuario: 'Carlos Ruiz',    monto: 1500 },
];

export const TIPOS_GASTO = [
  { id: 1, nombre: 'Movilidad',    activo: true },
  { id: 2, nombre: 'Materiales',   activo: true },
  { id: 3, nombre: 'Refrigerios',  activo: true },
  { id: 4, nombre: 'Combustible',  activo: true },
  { id: 5, nombre: 'Útiles',       activo: true },
];

export const CENTROS_COSTO = [
  { id: 'CC-001', nombre: 'Obra Pucallpa',     activo: true },
  { id: 'CC-002', nombre: 'Obra Lima Norte',   activo: true },
  { id: 'CC-003', nombre: 'Administración',    activo: true },
  { id: 'CC-004', nombre: 'Comercial',         activo: false },
];

export const USUARIOS = [
  { id: 1, nombre: 'Juan Pérez',     rol: 'Solicitante', area: 'Operaciones'  },
  { id: 2, nombre: 'María Quispe',   rol: 'Solicitante', area: 'Logística'    },
  { id: 3, nombre: 'Ana Torres',     rol: 'Aprobador',   area: 'Contabilidad' },
  { id: 4, nombre: 'Pedro Castro',   rol: 'Tesorería',   area: 'Finanzas'     },
];

export const ROLES = [
  { id: 1, nombre: 'Solicitante', permisos: 'Crear solicitudes, registrar rendiciones' },
  { id: 2, nombre: 'Aprobador',   permisos: 'Aprobar / rechazar solicitudes' },
  { id: 3, nombre: 'Tesorería',   permisos: 'Registrar pagos, ver reportes' },
  { id: 4, nombre: 'Admin',       permisos: 'Configuración del sistema' },
];

export const AREAS = ['Operaciones', 'Logística', 'Ventas', 'Contabilidad', 'RR.HH.', 'Finanzas'];

export const formatPEN = (n) =>
  `S/ ${Number(n).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const formatDate = (iso) => {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
};
