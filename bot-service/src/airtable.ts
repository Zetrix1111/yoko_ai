/**
 * Cliente Airtable mínimo para el bot-baileys.
 * Mismo token y base que Yoko (AIRTABLE_BASE_ID).
 *
 * Tablas usadas:
 *   • wa_sessions       - lectura + actualización del estado de sesión
 *   • conversaciones    - upsert por (empresa_id, phone)
 *   • mensajes          - insert (role: user | assistant | human)
 *   • outbox            - lectura pendientes + marcar enviado
 */

import axios, { type AxiosInstance } from "axios";

const AIRTABLE_API = "https://api.airtable.com/v0";

let _client: AxiosInstance | null = null;

function getClient(): AxiosInstance {
  if (_client) return _client;
  const token = process.env.AIRTABLE_TOKEN;
  const base = process.env.AIRTABLE_BASE_ID;
  if (!token || !base) {
    throw new Error("Falta AIRTABLE_TOKEN o AIRTABLE_BASE_ID en env.");
  }
  _client = axios.create({
    baseURL: `${AIRTABLE_API}/${base}`,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    timeout: 15000,
  });
  // Interceptor: convierte errores de Airtable en mensajes legibles. Sin esto
  // el log de Node trunca el body y solo vemos "[Object]".
  _client.interceptors.response.use(
    (res) => res,
    (err) => {
      const status = err?.response?.status;
      const data = err?.response?.data;
      const msg =
        data?.error?.message ||
        data?.error?.type ||
        (typeof data === "string" ? data : JSON.stringify(data || {}));
      const url = err?.config?.url;
      const method = err?.config?.method?.toUpperCase();
      err.airtableMessage = `[Airtable ${status}] ${method} ${url} → ${msg}`;
      err.message = err.airtableMessage;
      return Promise.reject(err);
    },
  );
  return _client;
}

export interface AirtableRecord {
  id: string;
  fields: Record<string, any>;
  createdTime?: string;
}

async function listRecords(table: string, params: Record<string, any> = {}): Promise<AirtableRecord[]> {
  const client = getClient();
  const res = await client.get(`/${encodeURIComponent(table)}`, { params });
  return res.data?.records || [];
}

async function getRecord(table: string, id: string): Promise<AirtableRecord> {
  const client = getClient();
  const res = await client.get(`/${encodeURIComponent(table)}/${encodeURIComponent(id)}`);
  return res.data;
}

async function createRecord(table: string, fields: Record<string, any>): Promise<AirtableRecord> {
  const client = getClient();
  const res = await client.post(`/${encodeURIComponent(table)}`, { fields });
  return res.data;
}

async function updateRecord(table: string, id: string, fields: Record<string, any>): Promise<AirtableRecord> {
  const client = getClient();
  const res = await client.patch(`/${encodeURIComponent(table)}/${encodeURIComponent(id)}`, { fields });
  return res.data;
}

// ─────────────────────────────────────────────────────────────────────────
// wa_sessions
// ─────────────────────────────────────────────────────────────────────────

export async function listWaSessions(): Promise<AirtableRecord[]> {
  return listRecords("wa_sessions", { maxRecords: 100 });
}

export async function findWaSession(empresaId: string): Promise<AirtableRecord | null> {
  const records = await listRecords("wa_sessions", {
    filterByFormula: `{empresa_id}='${escapeFormula(empresaId)}'`,
    maxRecords: 1,
  });
  return records[0] || null;
}

export async function updateWaSession(empresaId: string, fields: Record<string, any>): Promise<void> {
  const existing = await findWaSession(empresaId);
  if (!existing) {
    await createRecord("wa_sessions", { empresa_id: empresaId, ...fields });
  } else {
    await updateRecord("wa_sessions", existing.id, fields);
  }
}

/**
 * Como updateWaSession pero NO crea la row si no existe.
 * Útil para heartbeat: si el usuario borra la row en Airtable, no la recreamos.
 * El SessionManager se encargará de matar la sesión en memoria en el próximo poll.
 */
export async function touchWaSession(empresaId: string, fields: Record<string, any>): Promise<boolean> {
  const existing = await findWaSession(empresaId);
  if (!existing) return false;
  await updateRecord("wa_sessions", existing.id, fields);
  return true;
}

// ─────────────────────────────────────────────────────────────────────────
// conversaciones
// ─────────────────────────────────────────────────────────────────────────

export async function findOrCreateConversacion(
  empresaId: string,
  phone: string,
  nombre: string,
): Promise<AirtableRecord> {
  const records = await listRecords("conversaciones", {
    filterByFormula: `AND({empresa_id}='${escapeFormula(empresaId)}', {phone}='${escapeFormula(phone)}')`,
    maxRecords: 1,
  });
  const now = new Date().toISOString();
  if (records[0]) {
    // Actualizamos last_message_at; nombre solo si está vacío (no pisar
    // el nombre que el usuario eventualmente cambie en la UI)
    const fields: Record<string, any> = { last_message_at: now };
    if (!records[0].fields.nombre && nombre) fields.nombre = nombre;
    await updateRecord("conversaciones", records[0].id, fields);
    return { ...records[0], fields: { ...records[0].fields, ...fields } };
  }
  return createRecord("conversaciones", {
    empresa_id:      empresaId,
    phone,
    nombre:          nombre || "",
    modo:            "AI",
    last_message_at: now,
    created_at:      now,
  });
}

export async function getConversacionById(id: string): Promise<AirtableRecord | null> {
  try {
    return await getRecord("conversaciones", id);
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────
// mensajes
// ─────────────────────────────────────────────────────────────────────────

export async function insertMensaje(
  conversacionId: string,
  empresaId: string,
  role: "user" | "assistant" | "human",
  content: string,
): Promise<void> {
  await createRecord("mensajes", {
    conversacion_id: [conversacionId],
    empresa_id:      empresaId,
    role,
    content,
    created_at:      new Date().toISOString(),
  });
}

export async function getMensajesByConv(conversacionId: string, limit = 20): Promise<AirtableRecord[]> {
  // Linked records se filtran con FIND sobre ARRAYJOIN
  const records = await listRecords("mensajes", {
    filterByFormula: `FIND('${escapeFormula(conversacionId)}', ARRAYJOIN({conversacion_id}))`,
    maxRecords: limit,
  });
  records.sort((a, b) =>
    String(a.fields.created_at || "").localeCompare(String(b.fields.created_at || "")),
  );
  return records;
}

// ─────────────────────────────────────────────────────────────────────────
// outbox
// ─────────────────────────────────────────────────────────────────────────

export async function getPendingOutbox(): Promise<AirtableRecord[]> {
  return listRecords("outbox", {
    filterByFormula: `NOT({sent})`,
    maxRecords: 50,
  });
}

export async function markOutboxSent(id: string): Promise<void> {
  await updateRecord("outbox", id, { sent: true });
}

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────

/** Escapa comillas simples para uso en filterByFormula. */
function escapeFormula(s: string): string {
  return String(s).replace(/'/g, "\\'");
}
