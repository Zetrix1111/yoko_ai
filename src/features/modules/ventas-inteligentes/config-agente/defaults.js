// Schema v2 + opciones de selects/dropdowns/chips para el wizard.
// Todos los campos siguen el patrón {activo: bool, valor: ...}.
// Cuando activo:false, el backend cae a defaults universales hardcodeados.

export const DEFAULT_VENTAS_CONFIG_V2 = {
  // CAPA 3 — Voz del vendedor
  nombre_vendedor:        { activo: false, valor: '' },
  tratamiento:            { activo: false, valor: 'tu' },
  vocabulario:            { activo: false, valor: 'neutro' },
  calidez:                { activo: false, valor: 'cordial' },
  localizacion_cultural:  { activo: false, valor: { region: 'neutro_latam', modismos_permitidos: [] } },
  formato_mensaje:        { activo: false, valor: { longitud_preferida: 'corto', preguntas_por_turno: 1, uso_listas: 'solo_si_3_o_mas', puntuacion_enfatica: false } },
  uso_emojis:             { activo: false, valor: 'nunca' },

  // CAPA 5 — Política comercial
  zona_cobertura:         { activo: false, valor: '' },
  tiempo_entrega:         { activo: false, valor: '' },
  metodos_pago:           { activo: false, valor: [] },
  politica_precios:       { activo: false, valor: { igv: 'incluido', comprobantes: 'ambos' } },
  moneda:                 { activo: false, valor: 'PEN' },
  politica_envio:         { activo: false, valor: { modelo: 'fijo', monto_envio_gratis_desde: null, costo_fijo: null, detalle_libre: '' } },
  politica_devoluciones:  { activo: false, valor: { acepta_devolucion: true, plazo_dias: 7, condiciones: '' } },
  garantia:               { activo: false, valor: '' },
  pedido_minimo:          { activo: false, valor: { monto: 0, comentario: '' } },
  descuento_volumen:      { activo: false, valor: { umbral_aplica: 0, instruccion: 'derivar_humano' } },

  // CAPA 6 — Cliente y arco conversacional
  tipo_cliente:               { activo: false, valor: 'mixto' },
  discovery_preguntas:        { activo: false, valor: [] },
  datos_cierre_obligatorios:  { activo: false, valor: ['nombre', 'telefono'] },
  umbral_derivacion_humano:   { activo: false, valor: null },
  criterios_derivacion:       { activo: false, valor: [] },
  asesor_humano:              { activo: false, valor: { nombre: '', telefono: '' } },
  horario_ia:                 { activo: false, valor: '24_7' },

  // CAPA 7 — Conocimiento de marca
  propuesta_valor:        { activo: false, valor: '' },
  diferenciadores:        { activo: false, valor: [] },
  prueba_social:          { activo: false, valor: [] },
  autoridad_tecnica:      { activo: false, valor: [] },
  faq:                    { activo: false, valor: [] },
  promociones_activas:    { activo: false, valor: [] },

  // CAPA 8 — Manejo de objeciones
  objeciones:             { activo: false, valor: [] },

  // CAPA 9 — Límites y prohibiciones
  prohibiciones:           { activo: false, valor: [] },
  alcance_responsabilidad: { activo: false, valor: '' },
};

// ─── CAPA 3 — opciones ────────────────────────────────────────────────

export const TRATAMIENTO_OPCIONES = [
  { id: 'tu',                  label: 'Tú',                       preview: 'Hola, ¿qué necesitas?' },
  { id: 'vos',                 label: 'Vos',                      preview: 'Hola, ¿qué necesitás?' },
  { id: 'usted',               label: 'Usted',                    preview: 'Hola, ¿qué necesita?' },
  { id: 'mixto_segun_cliente', label: 'Mixto según cliente',      preview: 'Adapta tú/usted al cliente' },
];

export const VOCABULARIO_OPCIONES = [
  { id: 'tecnico',     label: 'Técnico',     hint: 'Especializado del rubro' },
  { id: 'neutro',      label: 'Neutro',      hint: 'Claro, sin tecnicismos' },
  { id: 'coloquial',   label: 'Coloquial',   hint: 'Cercano, expresiones cotidianas' },
  { id: 'corporativo', label: 'Corporativo', hint: 'Profesional, sin modismos' },
];

export const CALIDEZ_OPCIONES = [
  { id: 'calida_cercana',     label: 'Cálida y cercana',     hint: 'Interés genuino por el cliente' },
  { id: 'cordial',            label: 'Cordial',              hint: 'Respetuoso, profesional sin ser frío' },
  { id: 'neutra_profesional', label: 'Neutra profesional',   hint: 'Foco en información clara' },
  { id: 'directa_seca',       label: 'Directa',              hint: 'Sin rodeos, al punto' },
];

export const REGION_OPCIONES = [
  { id: 'peru',         label: 'Perú' },
  { id: 'neutro_latam', label: 'Neutro LatAm' },
  { id: 'mexico',       label: 'México' },
  { id: 'argentina',    label: 'Argentina' },
  { id: 'espana',       label: 'España' },
];

export const LONGITUD_OPCIONES = [
  { id: 'muy_corto', label: 'Muy corto', hint: '1-2 líneas, ~30 palabras' },
  { id: 'corto',     label: 'Corto',     hint: '2-4 líneas, ~60 palabras' },
  { id: 'medio',     label: 'Medio',     hint: '4-8 líneas, hasta 120 palabras' },
  { id: 'extenso',   label: 'Extenso',   hint: 'Hasta 200 palabras' },
];

export const USO_LISTAS_OPCIONES = [
  { id: 'nunca',           label: 'Nunca' },
  { id: 'solo_si_3_o_mas', label: 'Si son 3+ ítems' },
  { id: 'frecuente',       label: 'Frecuente' },
];

export const EMOJIS_OPCIONES = [
  { id: 'nunca',                  label: 'Nunca',     hint: 'Sin emojis' },
  { id: 'ocasional_solo_calidez', label: 'Ocasional', hint: '1 emoji para calidez (👋, ✅)' },
  { id: 'frecuente_tematico',     label: 'Frecuente', hint: 'Hasta 2-3 emojis temáticos' },
];

// ─── CAPA 5 — opciones ────────────────────────────────────────────────

export const METODOS_PAGO_OPCIONES = [
  { id: 'efectivo',             label: 'Efectivo' },
  { id: 'yape_plin',            label: 'Yape / Plin' },
  { id: 'transferencia',        label: 'Transferencia bancaria' },
  { id: 'tarjeta_pos',          label: 'Tarjeta POS' },
  { id: 'tarjeta_online',       label: 'Tarjeta online' },
  { id: 'credito_empresarial',  label: 'Crédito empresarial' },
  { id: 'contra_entrega',       label: 'Contra-entrega' },
];

export const IGV_OPCIONES = [
  { id: 'incluido',    label: 'Incluido en el precio' },
  { id: 'no_incluido', label: 'NO incluido (se agrega)' },
  { id: 'referencial', label: 'Referencial (se confirma)' },
];

export const COMPROBANTES_OPCIONES = [
  { id: 'boleta',  label: 'Solo boleta' },
  { id: 'factura', label: 'Solo factura' },
  { id: 'ambos',   label: 'Boleta o factura' },
];

export const MONEDA_OPCIONES = [
  { id: 'PEN',   label: 'Soles (S/)' },
  { id: 'USD',   label: 'Dólares (US$)' },
  { id: 'EUR',   label: 'Euros (€)' },
  { id: 'multi', label: 'Múltiples' },
];

export const MODELO_ENVIO_OPCIONES = [
  { id: 'gratis',                label: 'Envío gratis' },
  { id: 'fijo',                  label: 'Costo fijo' },
  { id: 'por_distrito',          label: 'Por distrito' },
  { id: 'calculado_caso_a_caso', label: 'Caso por caso' },
];

export const DESCUENTO_VOLUMEN_OPCIONES = [
  { id: 'derivar_humano',  label: 'Derivar al asesor humano' },
  { id: 'porcentaje_fijo', label: 'Porcentaje fijo (configurado)' },
  { id: 'tabla_escalonada', label: 'Tabla escalonada (configurada)' },
];

// ─── CAPA 6 — opciones ────────────────────────────────────────────────

export const TIPO_CLIENTE_OPCIONES = [
  { id: 'b2b',   label: 'B2B (empresas)' },
  { id: 'b2c',   label: 'B2C (consumidor final)' },
  { id: 'mixto', label: 'Mixto' },
];

export const DATOS_CIERRE_OPCIONES = [
  { id: 'nombre',       label: 'Nombre completo' },
  { id: 'telefono',     label: 'Teléfono' },
  { id: 'email',        label: 'Email' },
  { id: 'direccion',    label: 'Dirección' },
  { id: 'ruc',          label: 'RUC' },
  { id: 'razon_social', label: 'Razón social' },
  { id: 'dni',          label: 'DNI' },
  { id: 'metodo_pago',  label: 'Método de pago' },
];

export const CRITERIOS_DERIVACION_OPCIONES = [
  { id: 'cotizacion_formal',     label: 'Pide cotización formal' },
  { id: 'descuento_negociacion', label: 'Pide descuento / negociar' },
  { id: 'modificar_pedido',      label: 'Modifica/cancela pedido' },
  { id: 'queja_reclamo',         label: 'Queja o reclamo' },
  { id: 'fuera_catalogo',        label: 'Pide fuera de catálogo' },
  { id: 'menciona_competencia',  label: 'Menciona competencia' },
  { id: 'intencion_compra',      label: 'Confirma intención de compra' },
  { id: 'conversacion_larga',    label: 'Más de 10 mensajes sin avanzar' },
];

export const HORARIO_IA_OPCIONES = [
  { id: '24_7',                     label: '24/7 (siempre responde)' },
  { id: 'solo_horario_atencion',    label: 'Solo en horario de atención' },
];

// ─── Sugerencias por defecto para listas ──────────────────────────────

export const SUGERENCIAS_DIFERENCIADORES = [
  'Stock inmediato 24h',
  'Asesoría técnica especializada',
  'Despacho mismo día',
  'Garantía extendida',
  'Atención personalizada',
];

export const SUGERENCIAS_PRUEBA_SOCIAL = [
  'Más de 200 clientes en 2025',
  'Atendemos en obras de Lima desde 2020',
  '95% de clientes recomiendan nuestro servicio',
];

export const SUGERENCIAS_AUTORIDAD = [
  '10 años en el rubro',
  'Productos con certificación NTP/ISO',
  'Equipo certificado por fabricantes',
];

export const PLANTILLAS_OBJECIONES = [
  {
    objecion: 'Está caro',
    como_responder: 'Reconocer, no defender. Preguntar con qué lo compara. Resaltar 1 diferenciador concreto. NO bajar precio.',
  },
  {
    objecion: 'Lo voy a pensar',
    como_responder: 'Preguntar qué duda específica tiene. Si insiste, ofrecer info por escrito y agendar follow-up. NO presionar.',
  },
  {
    objecion: 'Tengo otro proveedor',
    como_responder: 'Preguntar qué le gusta y qué no. NO criticar a la competencia. Cerrar con: "cuando quieras comparar, escríbeme."',
  },
];

export const SUGERENCIAS_DISCOVERY_POR_CLIENTE = {
  b2b:   ['¿Para qué empresa o proyecto?', '¿Qué cantidad aproximada?', '¿Para cuándo lo necesitan?'],
  b2c:   ['¿Es para uso personal o regalo?', '¿Cuándo lo necesitas?', '¿Tienes alguna preferencia de marca?'],
  mixto: ['¿Es para una empresa o uso personal?', '¿Para cuándo lo necesitas?', '¿Cuántas unidades?'],
};

// ─── Defaults universales (informativos para PanelInformativo) ────────

export const PROHIBICIONES_UNIVERSALES_TEXTO = [
  'No inventa precios, stock, plazos, características ni promociones',
  'No usa Markdown (asteriscos, almohadillas, listas con guiones)',
  'No promete nada que requiera autorización (descuentos, créditos)',
  'No comparte datos de otros clientes ni info interna',
  'No habla mal de la competencia',
  'No insiste si el cliente dijo "no" o "lo pienso"',
];
