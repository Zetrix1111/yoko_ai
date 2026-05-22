import {
  FileText,
  CheckCircle2,
  CreditCard,
  Receipt,
  Wallet,
  ClipboardList,
  Sparkles,
  TrendingUp,
  Inbox,
  FileCheck,
  Banknote,
} from 'lucide-react';
import { formatSistemaContable } from '../empresa/EmpresaContext';

/**
 * Catálogo de KPIs disponibles. Cada KPI declara su módulo asociado
 * para que `selectKpisForModulos` pueda armar la grilla correcta según
 * los módulos que la empresa tiene contratados.
 *
 * Hoy todos los valores son placeholder `—`. Cuando se conecten a
 * endpoints reales, esta lista podrá evolucionar a un fetcher (un
 * fetch por card o uno agregado a `/api/dashboard/kpis`).
 */

const KPI_CATALOG = {
  // ── Gestión de Caja Chica ────────────────────────────────────────
  'caja-solicitudes-pendientes': {
    id:     'caja-solicitudes-pendientes',
    modulo: 'gestion-caja',
    label:  'Solicitudes pendientes',
    hint:   'Esperando aprobación',
    Icon:   FileText,
  },
  'caja-solicitudes-aprobadas-mes': {
    id:     'caja-solicitudes-aprobadas-mes',
    modulo: 'gestion-caja',
    label:  'Solicitudes aprobadas',
    hint:   'Mes en curso',
    Icon:   CheckCircle2,
  },
  'caja-pagos-procesar': {
    id:     'caja-pagos-procesar',
    modulo: 'gestion-caja',
    label:  'Pagos por procesar',
    hint:   'Tesorería',
    Icon:   CreditCard,
  },
  'caja-egresos-mes': {
    id:     'caja-egresos-mes',
    modulo: 'gestion-caja',
    label:  'Egresos caja chica',
    hint:   'Mes en curso',
    Icon:   Wallet,
    isMoney: true,
  },
  'caja-rendiciones-revisar': {
    id:     'caja-rendiciones-revisar',
    modulo: 'gestion-caja',
    label:  'Rendiciones por revisar',
    hint:   'Comprobantes pendientes',
    Icon:   ClipboardList,
  },
  'caja-rendiciones-generadas-mes': {
    id:     'caja-rendiciones-generadas-mes',
    modulo: 'gestion-caja',
    label:  'Rendiciones generadas',
    hint:   'Mes en curso',
    Icon:   FileCheck,
  },

  // ── Facturas Inteligentes ────────────────────────────────────────
  'facturas-procesadas-mes': {
    id:     'facturas-procesadas-mes',
    modulo: 'facturas-inteligentes',
    label:  'Facturas procesadas',
    hint:   'Mes en curso',
    Icon:   Receipt,
  },
  'facturas-en-cola': {
    id:     'facturas-en-cola',
    modulo: 'facturas-inteligentes',
    label:  'Facturas en cola',
    hint:   'Por procesar',
    Icon:   Inbox,
  },
  'facturas-comprobantes-exportados': {
    id:     'facturas-comprobantes-exportados',
    modulo: 'facturas-inteligentes',
    label:  'Comprobantes exportados',
    // hint dinámico según sistema contable de la empresa
    Icon:   FileText,
  },
  'facturas-total-mes': {
    id:     'facturas-total-mes',
    modulo: 'facturas-inteligentes',
    label:  'Total facturado',
    hint:   'Mes en curso',
    Icon:   Banknote,
    isMoney: true,
  },
  'facturas-igv-mes': {
    id:     'facturas-igv-mes',
    modulo: 'facturas-inteligentes',
    label:  'Total IGV',
    hint:   'Mes en curso',
    Icon:   TrendingUp,
    isMoney: true,
  },

  // ── Cross-módulo ─────────────────────────────────────────────────
  'cross-documentos-ia': {
    id:     'cross-documentos-ia',
    modulo: 'cross',
    label:  'Documentos procesados por IA',
    hint:   'Mes en curso',
    Icon:   Sparkles,
  },
};

/**
 * Devuelve siempre 6 KPIs según los módulos contratados.
 *
 * @param {Set<string>} modulosSet — Set con los IDs de módulos del JWT.
 * @param {string} sistemaContable — slug del sistema contable (sire/concar/...).
 * @returns {Array<KpiCard>} con 6 cards listos para renderizar.
 */
export function selectKpisForModulos(modulosSet, sistemaContable) {
  const has = (mod) => modulosSet instanceof Set && modulosSet.has(mod);
  const sistemaUpper = formatSistemaContable(sistemaContable);

  let ids = [];

  const hasCaja     = has('gestion-caja');
  const hasFacturas = has('facturas-inteligentes');

  if (hasCaja && hasFacturas) {
    // Mezcla 3 caja + 2 facturas + 1 cross
    ids = [
      'caja-solicitudes-pendientes',
      'caja-solicitudes-aprobadas-mes',
      'caja-egresos-mes',
      'facturas-procesadas-mes',
      'facturas-total-mes',
      'cross-documentos-ia',
    ];
  } else if (hasCaja) {
    ids = [
      'caja-solicitudes-pendientes',
      'caja-solicitudes-aprobadas-mes',
      'caja-pagos-procesar',
      'caja-egresos-mes',
      'caja-rendiciones-revisar',
      'caja-rendiciones-generadas-mes',
    ];
  } else if (hasFacturas) {
    ids = [
      'facturas-procesadas-mes',
      'facturas-en-cola',
      'facturas-comprobantes-exportados',
      'facturas-total-mes',
      'facturas-igv-mes',
      'cross-documentos-ia',
    ];
  } else {
    // Sin módulos operativos: dejamos el catálogo cross + caja para que
    // al menos se vea algo. El upsell del Dashboard explica el resto.
    ids = [
      'cross-documentos-ia',
      'caja-solicitudes-pendientes',
      'caja-egresos-mes',
      'facturas-procesadas-mes',
      'facturas-total-mes',
      'facturas-igv-mes',
    ];
  }

  return ids.map((id) => {
    const k = KPI_CATALOG[id];
    // El hint del card "Comprobantes exportados" depende del sistema contable.
    const hint = id === 'facturas-comprobantes-exportados'
      ? `Hacia ${sistemaUpper}`
      : k.hint;
    return {
      id:     k.id,
      label:  k.label,
      hint,
      Icon:   k.Icon,
      value:  k.isMoney ? 'S/ —' : '—',
    };
  });
}
