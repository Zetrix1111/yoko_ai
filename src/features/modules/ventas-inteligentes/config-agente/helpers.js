// Utilidades del wizard de configuración del agente IA.

import { DEFAULT_VENTAS_CONFIG_V2 } from './defaults';

/**
 * Combina la config que viene del backend con DEFAULT_VENTAS_CONFIG_V2.
 * Los campos que ya existen en el backend (incluso si vienen del schema viejo
 * y siguen siendo válidos en v2) sobreviven. Los que no existen aún se llenan
 * con su default `{activo:false, valor:...}`. Los campos legacy que ya no
 * existen en v2 (estilo_vendedor, info_adicional) simplemente se ignoran al
 * guardar — el siguiente save los borra.
 */
export function mergeWithDefault(backendConfig) {
  const out = {};
  for (const key of Object.keys(DEFAULT_VENTAS_CONFIG_V2)) {
    const def = DEFAULT_VENTAS_CONFIG_V2[key];
    const back = backendConfig?.[key];
    if (!back || typeof back !== 'object') {
      out[key] = def;
      continue;
    }
    // Para campos con valor objeto, mergear sub-keys también
    if (typeof def.valor === 'object' && def.valor !== null && !Array.isArray(def.valor)) {
      out[key] = {
        activo: !!back.activo,
        valor: { ...def.valor, ...(back.valor || {}) },
      };
    } else {
      out[key] = {
        activo: !!back.activo,
        valor: back.valor !== undefined ? back.valor : def.valor,
      };
    }
  }
  return out;
}

/**
 * Conserva solo los campos válidos del schema v2 al guardar — drop legacy.
 */
export function projectToV2(config) {
  const out = {};
  for (const key of Object.keys(DEFAULT_VENTAS_CONFIG_V2)) {
    out[key] = config[key] ?? DEFAULT_VENTAS_CONFIG_V2[key];
  }
  return out;
}

/**
 * Helper para actualizar un campo {activo, valor} dentro del state global.
 */
export function setCampoEn(config, key, partial) {
  return { ...config, [key]: { ...config[key], ...partial } };
}

/**
 * Helper para actualizar una sub-key dentro del valor de un campo objeto.
 */
export function setValorSubkey(config, key, subkey, valor) {
  return {
    ...config,
    [key]: {
      ...config[key],
      valor: { ...config[key].valor, [subkey]: valor },
    },
  };
}

/**
 * Comparación shallow-deep para detectar dirty state. Suficiente para
 * config plana de ~24 campos con valores simples u objetos chicos.
 */
export function isEqualConfig(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * Cuenta cuántos campos están activos en una capa específica. Útil para
 * mostrar badges "X campos personalizados" en la barra de progreso.
 */
export function contarActivosEnCapa(config, capaKeys) {
  return capaKeys.filter((k) => config[k]?.activo).length;
}

// ─── Llaves agrupadas por capa (para indicadores y validación) ───────

export const CAPA_KEYS = {
  voz: [
    'nombre_vendedor', 'tratamiento', 'vocabulario', 'calidez',
    'localizacion_cultural', 'formato_mensaje', 'uso_emojis',
  ],
  politica: [
    'zona_cobertura', 'tiempo_entrega', 'metodos_pago', 'politica_precios',
    'moneda', 'politica_envio', 'politica_devoluciones', 'garantia',
    'pedido_minimo', 'descuento_volumen',
  ],
  cliente: [
    'tipo_cliente', 'discovery_preguntas', 'datos_cierre_obligatorios',
    'umbral_derivacion_humano', 'criterios_derivacion', 'asesor_humano',
    'horario_ia',
  ],
  marca: [
    'propuesta_valor', 'diferenciadores', 'prueba_social',
    'autoridad_tecnica', 'faq', 'promociones_activas',
  ],
  limites: [
    'objeciones', 'prohibiciones', 'alcance_responsabilidad',
  ],
};
