// 5 plantillas de vertical para el onboarding del wizard.
// Cada plantilla pre-llena 10-15 de los 24 campos con valores razonables
// para esa industria. El cliente puede seguir editando todo después.

import { DEFAULT_VENTAS_CONFIG_V2, PLANTILLAS_OBJECIONES } from './defaults';

// Helper para crear un campo activo con un valor.
const on = (valor) => ({ activo: true, valor });

// ── EPP / Seguridad industrial ─────────────────────────────────────
const EPP_CONFIG = {
  ...DEFAULT_VENTAS_CONFIG_V2,

  tratamiento:        on('tu'),
  vocabulario:        on('tecnico'),
  calidez:            on('cordial'),
  uso_emojis:         on('nunca'),
  formato_mensaje:    on({
    longitud_preferida: 'corto', preguntas_por_turno: 1,
    uso_listas: 'solo_si_3_o_mas', puntuacion_enfatica: false,
  }),

  metodos_pago:       on(['yape_plin', 'transferencia', 'efectivo', 'contra_entrega']),
  politica_precios:   on({ igv: 'incluido', comprobantes: 'ambos' }),
  moneda:             on('PEN'),

  tipo_cliente:       on('mixto'),
  datos_cierre_obligatorios: on(['nombre', 'telefono', 'direccion', 'ruc']),
  criterios_derivacion: on([
    'cotizacion_formal', 'descuento_negociacion', 'queja_reclamo',
    'intencion_compra', 'fuera_catalogo',
  ]),

  prohibiciones: on([
    'No hago evaluaciones técnicas que requieran un especialista en seguridad industrial',
  ]),
  objeciones: on([...PLANTILLAS_OBJECIONES]),
};

// ── Cosmética / Belleza ────────────────────────────────────────────
const COSMETICA_CONFIG = {
  ...DEFAULT_VENTAS_CONFIG_V2,

  tratamiento:     on('tu'),
  vocabulario:     on('coloquial'),
  calidez:         on('calida_cercana'),
  uso_emojis:      on('ocasional_solo_calidez'),
  formato_mensaje: on({
    longitud_preferida: 'corto', preguntas_por_turno: 1,
    uso_listas: 'solo_si_3_o_mas', puntuacion_enfatica: false,
  }),

  metodos_pago:           on(['yape_plin', 'tarjeta_online', 'transferencia']),
  politica_precios:       on({ igv: 'incluido', comprobantes: 'ambos' }),
  moneda:                 on('PEN'),
  politica_devoluciones:  on({ acepta_devolucion: true, plazo_dias: 7, condiciones: 'Producto sin abrir y en empaque original' }),

  tipo_cliente:           on('b2c'),
  datos_cierre_obligatorios: on(['nombre', 'telefono', 'direccion']),
  criterios_derivacion:   on(['queja_reclamo', 'intencion_compra']),
  objeciones:             on([PLANTILLAS_OBJECIONES[0], PLANTILLAS_OBJECIONES[1]]),
};

// ── Restaurante / Delivery ─────────────────────────────────────────
const RESTAURANTE_CONFIG = {
  ...DEFAULT_VENTAS_CONFIG_V2,

  tratamiento:     on('tu'),
  vocabulario:     on('coloquial'),
  calidez:         on('calida_cercana'),
  uso_emojis:      on('ocasional_solo_calidez'),
  formato_mensaje: on({
    longitud_preferida: 'muy_corto', preguntas_por_turno: 1,
    uso_listas: 'solo_si_3_o_mas', puntuacion_enfatica: false,
  }),

  metodos_pago:    on(['yape_plin', 'efectivo', 'tarjeta_pos']),
  moneda:          on('PEN'),
  politica_envio:  on({ modelo: 'por_distrito', monto_envio_gratis_desde: null, costo_fijo: null, detalle_libre: '' }),
  pedido_minimo:   on({ monto: 20, comentario: 'Pedido mínimo S/ 20 para delivery' }),

  tipo_cliente:    on('b2c'),
  datos_cierre_obligatorios: on(['nombre', 'telefono', 'direccion']),
  criterios_derivacion: on(['queja_reclamo', 'modificar_pedido']),
};

// ── Servicios profesionales (legal/contable/asesoría) ──────────────
const SERVICIOS_CONFIG = {
  ...DEFAULT_VENTAS_CONFIG_V2,

  tratamiento:     on('usted'),
  vocabulario:     on('corporativo'),
  calidez:         on('neutra_profesional'),
  uso_emojis:      on('nunca'),
  formato_mensaje: on({
    longitud_preferida: 'medio', preguntas_por_turno: 1,
    uso_listas: 'solo_si_3_o_mas', puntuacion_enfatica: false,
  }),

  politica_precios: on({ igv: 'no_incluido', comprobantes: 'factura' }),
  moneda:           on('PEN'),

  tipo_cliente:        on('b2b'),
  datos_cierre_obligatorios: on(['nombre', 'telefono', 'email', 'ruc', 'razon_social']),
  // Servicios profesionales: forzar siempre derivación al humano para cierre.
  criterios_derivacion: on([
    'intencion_compra', 'conversacion_larga', 'cotizacion_formal',
    'descuento_negociacion', 'queja_reclamo',
  ]),

  alcance_responsabilidad: on(
    'Soy un asistente para resolver dudas iniciales. Para cualquier asesoría formal, ' +
    'cotización o contratación, derivo siempre al asesor humano.'
  ),
};

// ─── Catálogo final exportado ─────────────────────────────────────

export const PLANTILLAS_VERTICAL = [
  {
    id:    'generico',
    label: 'Empezar de cero',
    emoji: '⚙️',
    descripcion: 'Sin valores pre-cargados. Configurás todo desde cero.',
    config: DEFAULT_VENTAS_CONFIG_V2,
  },
  {
    id:    'epp_seguridad_industrial',
    label: 'EPP / Seguridad industrial',
    emoji: '🦺',
    descripcion: 'Catálogo técnico, B2B/B2C mixto, comprobantes ambos, derivación a humano para cotizaciones.',
    config: EPP_CONFIG,
  },
  {
    id:    'cosmetica_belleza',
    label: 'Cosmética / Belleza',
    emoji: '💄',
    descripcion: 'B2C cálido, vocabulario coloquial, política de devoluciones de 7 días, emojis ocasionales.',
    config: COSMETICA_CONFIG,
  },
  {
    id:    'restaurante_delivery',
    label: 'Restaurante / Delivery',
    emoji: '🍔',
    descripcion: 'Mensajes muy cortos, envío por distrito, pedido mínimo S/ 20, métodos de pago locales.',
    config: RESTAURANTE_CONFIG,
  },
  {
    id:    'servicios_profesionales',
    label: 'Servicios profesionales',
    emoji: '📋',
    descripcion: 'B2B formal, tratamiento de usted, factura con IGV, siempre deriva al asesor humano para cierre.',
    config: SERVICIOS_CONFIG,
  },
];
