// Branding global de la app (multi-tenant). Igual para todos los clientes.
// Si en el futuro se decide rebrand por cliente, este archivo se reemplaza
// por una resolución dinámica desde Airtable o desde el JWT — pero por
// ahora todos los tenants ven la misma marca "Yoko".

import logo from '../assets/logo.png';

export const APP_NAME = 'Yoko';
export const APP_LOGO = logo;
