// Multi-tenant loader.
// El tenant activo se elige con la env var VITE_TENANT_ID en cada Vercel project.
// Si no está definida o el tenant no existe, cae al fallback "cmejia".
//
// Para agregar un cliente nuevo:
//   1) Crear src/tenants/<id>/config.json
//   2) Importar el config abajo y registrar la entrada en TENANTS
//   3) En su Vercel project nuevo, setear VITE_TENANT_ID=<id> + sus env vars (Airtable/Make/OpenAI)
//
// Nota: el logo es único de la app (src/assets/logo.png), ya no es por tenant.

import cmejiaConfig from './cmejia/config.json';
import demoConfig   from './demo/config.json';
import appLogo      from '../assets/logo.png';

const TENANTS = {
  cmejia: { config: cmejiaConfig },
  demo:   { config: demoConfig   },
};

const FALLBACK_ID = 'cmejia';
const DEV_OVERRIDE_KEY = '__yoko_dev_tenant';

function pickTenantId() {
  // En dev (npm run dev) permitimos override por URL: ?tenant=demo
  // Se guarda en sessionStorage para que las navegaciones internas
  // mantengan el tenant elegido (no hace falta repetir el query string).
  // En producción este bloque NO corre — solo la env var del build cuenta.
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get('tenant');
    if (fromUrl && TENANTS[fromUrl]) {
      sessionStorage.setItem(DEV_OVERRIDE_KEY, fromUrl);
      return fromUrl;
    }
    const stored = sessionStorage.getItem(DEV_OVERRIDE_KEY);
    if (stored && TENANTS[stored]) return stored;
  }

  // Build-time: la env var manda (cada Vercel project tiene la suya)
  const fromEnv = import.meta.env.VITE_TENANT_ID;
  if (fromEnv && TENANTS[fromEnv]) return fromEnv;

  if (fromEnv) {
    console.warn(`[tenants] VITE_TENANT_ID="${fromEnv}" no existe. Usando fallback "${FALLBACK_ID}".`);
  }
  return FALLBACK_ID;
}

const resolvedId = pickTenantId();

if (import.meta.env.DEV) {
  console.log(`[tenants] Tenant activo: "${resolvedId}"`);
}

const active = TENANTS[resolvedId];

export const tenantId      = resolvedId;
export const tenantConfig  = active.config;
export const tenantModules = new Set(active.config.modules || []);

// Logo único de la app (no per-tenant)
export { appLogo };

// Helper para checkear si un módulo está habilitado en este tenant
export function isModuleEnabled(moduleId) {
  return tenantModules.has(moduleId);
}
