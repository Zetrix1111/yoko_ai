// Cliente HTTP compartido. Todas las llamadas a /api/* pasan por aquí.
// En desarrollo, Vite hace proxy a https://yokochat.vercel.app (ver vite.config.js).
//
// Dos familias de funciones:
//   • Sin auth: postJson, getJson, postForm, patchJson, deleteJson.
//     Para endpoints que no requieren JWT (ej. /api/login, /api/parse_file
//     mientras no esté detrás de auth).
//   • Con auth: apiFetch / postJsonAuth / getJsonAuth.
//     Inyectan `Authorization: Bearer <token>` desde localStorage y, si la
//     respuesta es 401, disparan `yoko:auth-expired` para que useAuth
//     haga logout automático sin que cada caller tenga que manejarlo.

const AUTH_STORAGE_KEY = 'yoko_auth';

/**
 * Devuelve el JWT guardado en localStorage[yoko_auth].token, o null si
 * no hay sesión activa. NO valida expiración — eso lo hace useAuth.
 */
export function getAuthToken() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.token || null;
  } catch {
    return null;
  }
}

/**
 * Wrapper de fetch que inyecta el Bearer token desde localStorage y
 * normaliza el manejo de 401 (auth expirado / inválido).
 *
 * Comportamiento:
 *   • Si hay token, agrega `Authorization: Bearer <token>`.
 *   • Si la respuesta es 401, dispara `window` event 'yoko:auth-expired'
 *     y rechaza con un Error('HTTP 401'). useAuth escucha ese evento
 *     y hace logout — los callers no necesitan manejar 401 a mano.
 *   • Otros !ok → throw `Error('HTTP <code>')`.
 *   • Body JSON → devuelve objeto parseado. Otro Content-Type → text.
 *   • Body vacío con status 204 → devuelve null.
 */
export async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getAuthToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  // Si el body es objeto plano, asumimos JSON (matching postJson). FormData,
  // Blob, ArrayBuffer y typed arrays se mandan crudos.
  let body = options.body;
  const isRawBytes = body instanceof FormData
    || body instanceof Blob
    || body instanceof ArrayBuffer
    || (typeof ArrayBuffer !== 'undefined' && ArrayBuffer.isView(body));
  if (body && typeof body === 'object' && !isRawBytes) {
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    body = JSON.stringify(body);
  }

  const res = await fetch(url, { ...options, headers, body });

  if (res.status === 401) {
    // Auth expirado / inválido. Avisamos a quien escuche para que limpie sesión.
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('yoko:auth-expired'));
    }
    throw new Error('HTTP 401');
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) return res.json();
  return res.text();
}

export async function postJsonAuth(url, body) {
  return apiFetch(url, { method: 'POST', body });
}

export async function getJsonAuth(url) {
  return apiFetch(url, { method: 'GET' });
}

export async function patchJsonAuth(url, body) {
  return apiFetch(url, { method: 'PATCH', body });
}

export async function deleteJsonAuth(url) {
  return apiFetch(url, { method: 'DELETE' });
}

/**
 * POST de FormData con Bearer token. Para endpoints que reciben multipart
 * (parse_file, facturas_procesar). El browser pone el Content-Type con
 * boundary correcto si dejamos `body: FormData` sin sobrescribir headers.
 */
export async function postFormAuth(url, formData) {
  return apiFetch(url, { method: 'POST', body: formData });
}

/**
 * POST de bytes crudos (Blob / ArrayBuffer / typed array) con Bearer token.
 * Útil para endpoints que reciben audio sin envoltorio multipart, como
 * /api/transcribe.
 */
export async function postBytesAuth(url, bytes, contentType) {
  return apiFetch(url, {
    method: 'POST',
    headers: contentType ? { 'Content-Type': contentType } : {},
    body: bytes,
  });
}

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
  TRANSCRIBE: '/api/transcribe',
  PARSE_FILE: '/api/parse_file',
  FACTURAS_PROCESAR: '/api/facturas_procesar',
  FACTURAS_CONCAR: '/api/facturas_concar',
  CENTROS_COSTO: '/api/centros_costo',
  CONFIG:         '/api/config',
  PRODUCTOS: '/api/productos',
  // Ventas Inteligentes — endpoints consolidados en /api/ventas?resource=...
  // (Vercel Hobby plan limita a 12 funciones serverless)
  WA:                  '/api/ventas?resource=wa',
  CONVERSACIONES:      '/api/ventas?resource=conversaciones',
  MENSAJES:            '/api/ventas?resource=mensajes',
  CONVERSACIONES_MODO: '/api/ventas?resource=conversaciones_modo',
  SALES_CHAT:          '/api/ventas?resource=sales_chat',
  SALES_PROMPT_PREVIEW: '/api/ventas?resource=prompt_preview',
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
