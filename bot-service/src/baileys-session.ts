/**
 * WaSession — encapsula UN socket Baileys para un tenant.
 *
 * Lecciones aplicadas (CRÍTICAS, no quitar sin entender):
 *   1. fetchLatestBaileysVersion() — sin esto, code 405 (versión vieja).
 *   2. Browsers.macOS('Desktop') — sin esto, code 440 en loop.
 *   3. NO usar printQRInTerminal (deprecated).
 *   4. State machine estricta de connection.update.
 *   5. Backoff 15s para code 440, 5s para otros.
 *   6. sock.end() antes de reconectar (cleanup).
 *   7. Filter fromMe / grupos / no-1:1.
 *   8. Mapping role 'human' → 'assistant' al armar el historial para el LLM.
 */

import makeWASocket, {
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  Browsers,
  DisconnectReason,
  type WASocket,
  type ConnectionState,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import pino from "pino";
import qrTerminal from "qrcode-terminal";
import path from "node:path";
import fs from "node:fs";

import * as airtable from "./airtable";
import * as yoko from "./yoko";

const AUTH_BASE = path.resolve(process.cwd(), "auth");

const logger = pino({ level: process.env.LOG_LEVEL || "silent" });

export class WaSession {
  empresaId: string;
  authDir: string;
  sock: WASocket | null = null;
  reconnectTimer: NodeJS.Timeout | null = null;
  shuttingDown = false;
  // Recibe el SessionManager para que lo invoquemos cuando la sesión se
  // suicide (loggedOut) sin que el manager tenga que adivinar.
  onSelfTerminate?: () => void;

  constructor(empresaId: string) {
    this.empresaId = empresaId;
    this.authDir = path.join(AUTH_BASE, sanitize(empresaId));
  }

  // ── Lifecycle ────────────────────────────────────────────────────────

  async start(): Promise<void> {
    fs.mkdirSync(this.authDir, { recursive: true });

    const { state, saveCreds } = await useMultiFileAuthState(this.authDir);

    let version: [number, number, number] | undefined;
    try {
      const fetched = await fetchLatestBaileysVersion();
      version = fetched.version;
    } catch (err) {
      console.warn(`[${this.empresaId}] No se pudo obtener última versión Baileys:`, err);
    }

    this.sock = makeWASocket({
      version,
      auth: state,
      logger,
      browser: Browsers.macOS("Desktop"),  // ← sin esto: code 440
      // markOnlineOnConnect: true es CRÍTICO. Si está en false, los mensajes
      // entrantes llegan con msg.message = null (no se desencriptan). El bot
      // tiene que aparecer "online" para que WhatsApp negocie correctamente
      // las claves Signal con cada contacto que le escribe.
      markOnlineOnConnect: true,
      syncFullHistory: false,
      // getMessage: callback que Baileys usa cuando WhatsApp pide
      // retransmisión de un mensaje saliente. Sin esto las fallas de
      // entrega temporales se vuelven permanentes. Devolvemos undefined
      // porque no tenemos un store local — Baileys re-pide al server.
      getMessage: async () => undefined,
    });

    this.sock.ev.on("creds.update", saveCreds);
    this.sock.ev.on("connection.update", (u) => this.handleConnectionUpdate(u));
    this.sock.ev.on("messages.upsert", (m) => {
      console.log(`[${this.empresaId}] DEBUG messages.upsert type=${m.type} count=${m.messages?.length || 0}`);
      for (const msg of m.messages || []) {
        const remote = msg.key?.remoteJid;
        const fromMe = msg.key?.fromMe;
        const types = Object.keys(msg.message || {}).join(",") || "(no-message)";
        const text = extractText(msg);
        const txtPreview = (text || "(no-text)").slice(0, 40);
        // messageStubType: cuando Baileys no puede desencriptar o el mensaje
        // es un evento del sistema (cambio de avatar, mensaje borrado, etc.)
        // pone aquí el código. Útil para diagnosticar fallas de @lid.
        const stub = (msg as any).messageStubType
          ? ` stub=${(msg as any).messageStubType}`
          : "";
        console.log(`[${this.empresaId}] DEBUG   msg from=${remote} fromMe=${fromMe} types=[${types}] text="${txtPreview}"${stub}`);
      }
      this.handleMessagesUpsert(m);
    });

    // messages.update: cuando un mensaje viene cifrado y Baileys logra
    // desencriptarlo en un segundo intento, llega vía este evento. Sin
    // listener aquí, las re-decryptions se pierden silenciosamente.
    this.sock.ev.on("messages.update", (updates) => {
      for (const u of updates) {
        const msg = u.update;
        if (msg?.message) {
          console.log(`[${this.empresaId}] DEBUG messages.update con message → re-procesando`);
          // Re-procesar como si fuera nuevo
          this.handleMessagesUpsert({ messages: [{ key: u.key, message: msg.message, pushName: (msg as any).pushName } as any], type: "notify" } as any);
        }
      }
    });
  }

  async shutdown(): Promise<void> {
    this.shuttingDown = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.sock) {
      try { await this.sock.logout(); } catch { /* ignore */ }
      try { this.sock.end(undefined); } catch { /* ignore */ }
      this.sock = null;
    }
    // Borrar carpeta auth para que la próxima vinculación pida QR
    try { fs.rmSync(this.authDir, { recursive: true, force: true }); } catch { /* ignore */ }
  }

  // ── Connection state machine ─────────────────────────────────────────

  private async handleConnectionUpdate(update: Partial<ConnectionState>): Promise<void> {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log(`[${this.empresaId}] QR generado, esperando escaneo...`);
      // Mostrar también en terminal como debugging fallback
      qrTerminal.generate(qr, { small: true });
      try {
        await airtable.touchWaSession(this.empresaId, {
          status:    "qr",
          qr_string: qr,
          phone:     "",
        });
      } catch (err) {
        console.error(`[${this.empresaId}] No se pudo persistir QR en Airtable:`, err);
      }
    }

    if (connection === "connecting") {
      // Solo log; NO degradamos status si ya está en 'qr' o 'connected'
      console.log(`[${this.empresaId}] Conectando...`);
    }

    if (connection === "open") {
      const rawId = this.sock?.user?.id || "";
      // Format esperado: "5491123456789:N@s.whatsapp.net"
      const numeric = rawId.split(":")[0]?.split("@")[0] || "";
      const phone = numeric ? `+${numeric}` : "";
      console.log(`[${this.empresaId}] CONECTADO: ${phone}`);
      try {
        await airtable.touchWaSession(this.empresaId, {
          status:       "connected",
          qr_string:    "",
          phone,
          // El campo Airtable es "Date" sin hora → mandamos solo YYYY-MM-DD.
          connected_at: todayISODate(),
        });
      } catch (err) {
        console.error(`[${this.empresaId}] No se pudo persistir 'connected':`, err);
      }
    }

    if (connection === "close") {
      const code = (lastDisconnect?.error as Boom | undefined)?.output?.statusCode;
      console.log(`[${this.empresaId}] Conexión cerrada (code=${code})`);

      if (code === DisconnectReason.loggedOut) {
        // El usuario cerró sesión desde su WhatsApp → estado terminal, no reconectar
        try {
          await airtable.touchWaSession(this.empresaId, {
            status:    "disconnected",
            qr_string: "",
            phone:     "",
          });
        } catch { /* ignore */ }
        try { fs.rmSync(this.authDir, { recursive: true, force: true }); } catch { /* ignore */ }
        // Avisamos al manager para que nos saque del Map sin esperar al próximo poll
        if (this.onSelfTerminate) this.onSelfTerminate();
        return;
      }

      // Cualquier otro code: reconectar transparentemente sin tocar status
      // (mientras estábamos 'connected', queremos seguir mostrando 'connected'
      // en el dashboard durante reconexiones efímeras).
      if (this.shuttingDown) return;
      const delay = code === 440 ? 15000 : 5000;
      this.scheduleReconnect(delay);
    }
  }

  private scheduleReconnect(delayMs: number): void {
    if (this.reconnectTimer) return;
    console.log(`[${this.empresaId}] Reintento en ${delayMs}ms`);
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      // Cleanup del socket viejo antes de levantar uno nuevo
      if (this.sock) {
        try { this.sock.end(undefined); } catch { /* ignore */ }
        this.sock = null;
      }
      if (this.shuttingDown) return;
      try {
        await this.start();
      } catch (err) {
        console.error(`[${this.empresaId}] Error al reconectar:`, err);
        // Reintentar más tarde
        this.scheduleReconnect(delayMs);
      }
    }, delayMs);
  }

  // ── Mensajes entrantes ────────────────────────────────────────────────

  private async handleMessagesUpsert(payload: { messages: any[]; type: string }): Promise<void> {
    if (payload.type !== "notify") return;
    for (const msg of payload.messages) {
      try {
        await this.processMessage(msg);
      } catch (err) {
        console.error(`[${this.empresaId}] Error procesando mensaje:`, err);
      }
    }
  }

  private async processMessage(msg: any): Promise<void> {
    if (msg.key?.fromMe) return;  // mensajes propios desde el teléfono del cliente
    const remoteJid: string = msg.key?.remoteJid || "";
    if (!remoteJid) return;
    if (remoteJid.endsWith("@g.us")) return;  // grupos fuera de scope v1

    // Aceptamos chats 1:1 con cualquiera de los dos formatos:
    //   • @s.whatsapp.net → JID clásico, el local part es el número de teléfono
    //   • @lid            → Linked Identity (WhatsApp 2024+, privacy-aware).
    //                       El local part NO es un número de teléfono, es un
    //                       ID interno opaco. Igual lo guardamos para poder
    //                       responder al mismo JID después.
    const isWA  = remoteJid.endsWith("@s.whatsapp.net");
    const isLID = remoteJid.endsWith("@lid");
    if (!isWA && !isLID) return;

    // Extraemos texto desde varios tipos de mensaje. Si no hay texto plano
    // pero llegó un audio/imagen/sticker, devolvemos un placeholder explícito
    // en vez de descartar. Sin esto, los clientes que mandan audio o foto
    // quedan invisibles en el dashboard y la conversación parece muerta.
    const text = extractText(msg);
    if (!text) return;

    // Para @s.whatsapp.net guardamos formato bonito "+51999...". Para @lid
    // guardamos el JID completo ("268114...@lid") porque NO es un número real.
    const phone = isWA
      ? "+" + remoteJid.split("@")[0]
      : remoteJid;
    const nombre = msg.pushName || phone;

    console.log(`[${this.empresaId}] ← ${nombre} (${phone}): "${text}"`);

    // 1) upsert conversación
    const conv = await airtable.findOrCreateConversacion(this.empresaId, phone, nombre);

    // 2) persistir el mensaje del cliente
    await airtable.insertMensaje(conv.id, this.empresaId, "user", text);

    // 3) re-leer la conversación: el modo pudo haber cambiado entre la creación y este check
    const fresh = await airtable.getConversacionById(conv.id);
    const modo = fresh?.fields?.modo || "AI";
    if (modo !== "AI") {
      console.log(`[${this.empresaId}] modo=${modo} → no respondo IA, queda para humano`);
      return;
    }

    // 4) armar history para el LLM (mapping 'human' → 'assistant')
    const historial = await airtable.getMensajesByConv(conv.id, 20);
    const history = historial.map((m) => {
      const role = m.fields.role === "human" ? "assistant" : (m.fields.role || "user");
      return { role: role as "user" | "assistant", content: String(m.fields.content || "") };
    });

    // 5) call /api/sales_chat
    const t0 = Date.now();
    let reply = "";
    try {
      reply = await yoko.getSalesChatReply({
        empresaId: this.empresaId,
        phone,
        nombre,
        history,
      });
    } catch (err: any) {
      console.error(`[${this.empresaId}] /api/sales_chat falló:`, err?.message || err);
      return;  // sin reply, dejamos el mensaje en mensajes; el humano podrá ver y responder
    }
    console.log(`[${this.empresaId}] LLM respondió en ${Date.now() - t0}ms`);

    if (!reply) return;

    // 6) persistir + enviar
    await airtable.insertMensaje(conv.id, this.empresaId, "assistant", reply);
    try {
      await this.sendText(phone, reply);
      console.log(`[${this.empresaId}] → ${phone}: respuesta enviada`);
    } catch (err) {
      console.error(`[${this.empresaId}] Error enviando reply:`, err);
    }
  }

  // ── Envío ─────────────────────────────────────────────────────────────

  async sendText(phone: string, text: string): Promise<void> {
    if (!this.sock) {
      throw new Error(`[${this.empresaId}] socket no listo, no se puede enviar`);
    }
    const jid = phoneToJid(phone);
    await this.sock.sendMessage(jid, { text });
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────

function sanitize(s: string): string {
  // Por seguridad al crear carpetas: solo alfanumérico, guion bajo y guion
  return s.replace(/[^a-zA-Z0-9_-]/g, "_");
}

/**
 * Extrae texto utilizable de un mensaje de Baileys cubriendo los tipos más
 * comunes que mandan los clientes en WhatsApp:
 *
 *  • conversation        → texto plano simple
 *  • extendedTextMessage → texto con quote/formato/preview de link
 *  • imageMessage        → caption de la imagen
 *  • videoMessage        → caption del video
 *  • documentMessage     → caption (o el filename si no hay caption)
 *  • audioMessage / pttMessage → placeholder explícito ("[El cliente envió audio]")
 *  • stickerMessage      → placeholder ("[El cliente envió un sticker]")
 *  • locationMessage     → placeholder ("[El cliente envió ubicación]")
 *
 * Para tipos sin contenido textual relevante (reactionMessage, protocolMessage,
 * pollUpdateMessage), devolvemos "" para que el caller los descarte.
 *
 * El placeholder hace que la conversación sea visible en el dashboard incluso
 * cuando llegan medios — el operador puede pasar a modo HUMAN y responder.
 */
function extractText(msg: any): string {
  const m = msg?.message;
  if (!m) return "";

  // Algunos clientes envían el mensaje envuelto (forwarded, ephemeral).
  const inner =
    m.ephemeralMessage?.message ||
    m.viewOnceMessage?.message ||
    m.viewOnceMessageV2?.message ||
    m.documentWithCaptionMessage?.message ||
    m;

  if (inner.conversation) return String(inner.conversation);
  if (inner.extendedTextMessage?.text) return String(inner.extendedTextMessage.text);

  // Imagen/video/documento con caption
  const cap =
    inner.imageMessage?.caption ||
    inner.videoMessage?.caption ||
    inner.documentMessage?.caption;
  if (cap) return String(cap);

  // Documento sin caption: usar el filename para que el operador sepa qué llegó
  if (inner.documentMessage?.fileName) {
    return `[Documento: ${inner.documentMessage.fileName}]`;
  }
  if (inner.imageMessage)    return "[El cliente envió una imagen]";
  if (inner.videoMessage)    return "[El cliente envió un video]";
  if (inner.audioMessage || inner.pttMessage) return "[El cliente envió un audio]";
  if (inner.stickerMessage)  return "[El cliente envió un sticker]";
  if (inner.locationMessage || inner.liveLocationMessage) return "[El cliente envió una ubicación]";
  if (inner.contactMessage || inner.contactsArrayMessage) return "[El cliente envió un contacto]";

  // Reacciones, protocolos internos, polls → ignorar
  return "";
}

function phoneToJid(phone: string): string {
  // Si ya viene como JID completo (ej. "268114...@lid"), lo usamos tal cual.
  if (phone.includes("@")) return phone;
  // Si es un teléfono "+51 987 654 321" → "51987654321@s.whatsapp.net"
  const digits = phone.replace(/\D/g, "");
  return `${digits}@s.whatsapp.net`;
}

function todayISODate(): string {
  // YYYY-MM-DD en UTC. Compatible con campos Airtable de tipo "Date" (sin hora).
  return new Date().toISOString().slice(0, 10);
}
