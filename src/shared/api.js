// Cliente HTTP compartido. Todas las llamadas a /api/* pasan por aquí.
// En desarrollo, Vite hace proxy a https://yokochat.vercel.app (ver vite.config.js).

export async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

export async function postForm(url, formData) {
  const res = await fetch(url, { method: 'POST', body: formData });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res;
}

export const API = {
  LOGIN: '/api/login',
  CHAT: '/api/chat',
  UPLOAD: '/api/upload',
  PARSE_FILE: '/api/parse_file',
  ALERTA_SEGURA: '/api/alerta_segura',
  FACTURAS_PROCESAR: '/api/facturas_procesar',
  FACTURAS_CONCAR: '/api/facturas_concar',
  CENTROS_COSTO: '/api/centros_costo',
  PRODUCTOS: '/api/productos',
  // Ventas Inteligentes
  WA: '/api/wa',
  CONVERSACIONES: '/api/conversaciones',
  MENSAJES: '/api/mensajes',
  CONVERSACIONES_MODO: '/api/conversaciones_modo',
  SALES_CHAT: '/api/sales_chat',
};

export async function getJson(url) {
  const res = await fetch(url, { method: 'GET' });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

export async function patchJson(url, body) {
  const res = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteJson(url) {
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}
