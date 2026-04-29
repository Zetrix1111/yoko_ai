// Multi-tenant loader.
// El tenant activo se elige con la env var VITE_TENANT_ID en cada Vercel project.
// Si no está definida o el tenant no existe, cae al fallback "cmejia".
//
// Para agregar un cliente nuevo:
//   1) Crear src/tenants/<id>/config.json + logo.png
//   2) Importar el config + logo abajo y registrar la entrada en TENANTS
//   3) En su Vercel project nuevo, setear VITE_TENANT_ID=<id> + sus env vars (Airtable/Make/OpenAI)

import cmejiaConfig from './cmejia/config.json';
import cmejiaLogo from './cmejia/logo.png';

const TENANTS = {
  cmejia: { config: cmejiaConfig, logo: cmejiaLogo },
};

const FALLBACK_ID = 'cmejia';
const requestedId = import.meta.env.VITE_TENANT_ID;
const resolvedId = TENANTS[requestedId] ? requestedId : FALLBACK_ID;

if (requestedId && !TENANTS[requestedId]) {
  console.warn(
    `[tenants] VITE_TENANT_ID="${requestedId}" no existe. Usando fallback "${FALLBACK_ID}".`
  );
}

const active = TENANTS[resolvedId];

export const tenantId      = resolvedId;
export const tenantConfig  = active.config;
export const tenantLogo    = active.logo;
export const tenantModules = new Set(active.config.modules || []);

// Helper para checkear si un módulo está habilitado en este tenant
export function isModuleEnabled(moduleId) {
  return tenantModules.has(moduleId);
}
