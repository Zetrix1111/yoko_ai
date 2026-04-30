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
  APROBACIONES: '/api/aprobaciones',
  ALERTA_SEGURA: '/api/alerta_segura',
  CUENTA_BANCARIA: '/api/cuenta_bancaria',
  CAJA_CHICA: '/api/caja_chica',
  SOLICITUD_CAJA_CHICA: '/api/solicitud_caja_chica',
  PAGOS_INTELIGENTES: '/api/pagos_inteligentes',
  FACTURAS_INTELIGENTES: '/api/facturas_inteligentes',
};
