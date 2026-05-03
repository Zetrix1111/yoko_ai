/**
 * SessionManager — administra N WaSession en memoria, una por tenant.
 *
 * Reconciliación basada en wa_sessions (Airtable):
 *   • status='qr' | 'connecting' | 'connected'  → debe haber sesión activa
 *   • status='disconnected'                     → NO debe haber sesión activa
 *
 * Polling cada 5s:
 *   - row deseada activa + sesión NO en map  → start()
 *   - row deseada inactiva + sesión SÍ en map → shutdown() + remove
 *
 * Convención clave (acordada con wa.py):
 *   - El usuario clickea "Vincular" → wa.py setea status='qr' y qr_string=''.
 *     El bot ve eso y arranca un WaSession; el WaSession llena qr_string
 *     cuando Baileys emite el QR raw.
 *   - El usuario clickea "Desconectar" → wa.py setea status='disconnected'.
 *     El bot lo detecta y mata la sesión.
 */

import { WaSession } from "./baileys-session";
import * as airtable from "./airtable";

const ACTIVE_STATUSES = new Set(["qr", "connecting", "connected"]);

export class SessionManager {
  sessions = new Map<string, WaSession>();
  pollIntervalMs = 5000;
  heartbeatIntervalMs = 30000;
  pollTimer: NodeJS.Timeout | null = null;
  heartbeatTimer: NodeJS.Timeout | null = null;
  pollInFlight = false;

  async start(): Promise<void> {
    console.log("[manager] Iniciando session manager...");
    await this.pollOnce();
    this.pollTimer = setInterval(() => {
      this.pollOnce().catch((err) => console.error("[manager] poll error:", err));
    }, this.pollIntervalMs);
    this.heartbeatTimer = setInterval(() => {
      this.heartbeat().catch((err) => console.error("[manager] heartbeat error:", err));
    }, this.heartbeatIntervalMs);
  }

  async stop(): Promise<void> {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    const promises: Promise<void>[] = [];
    for (const session of this.sessions.values()) {
      promises.push(session.shutdown().catch(() => {}));
    }
    await Promise.all(promises);
    this.sessions.clear();
  }

  /** Reconcilia el estado deseado (Airtable) vs el estado actual (memoria). */
  async pollOnce(): Promise<void> {
    if (this.pollInFlight) return;
    this.pollInFlight = true;
    try {
      let rows: airtable.AirtableRecord[] = [];
      try {
        rows = await airtable.listWaSessions();
      } catch (err) {
        console.error("[manager] No se pudo listar wa_sessions:", err);
        return;
      }

      const seenInAirtable = new Set<string>();

      for (const row of rows) {
        const empresaId: string = row.fields.empresa_id;
        const status: string = row.fields.status || "disconnected";
        if (!empresaId) continue;
        seenInAirtable.add(empresaId);

        const inMap = this.sessions.has(empresaId);
        const shouldBeActive = ACTIVE_STATUSES.has(status);

        if (shouldBeActive && !inMap) {
          await this.startSession(empresaId);
        } else if (!shouldBeActive && inMap) {
          await this.stopSession(empresaId);
        }
      }

      // Matar sesiones zombie: rows borradas en Airtable mientras la sesión seguía
      // en memoria. Sin esto, una row borrada por el usuario se recrea por el
      // heartbeat y nunca termina la sesión.
      for (const empresaId of Array.from(this.sessions.keys())) {
        if (!seenInAirtable.has(empresaId)) {
          console.log(`[manager] Row borrada en Airtable para ${empresaId} → cerrando sesión zombie`);
          await this.stopSession(empresaId);
        }
      }
    } finally {
      this.pollInFlight = false;
    }
  }

  private async startSession(empresaId: string): Promise<void> {
    console.log(`[manager] Iniciando sesión para tenant=${empresaId}`);
    const session = new WaSession(empresaId);
    session.onSelfTerminate = () => {
      this.sessions.delete(empresaId);
      console.log(`[manager] Sesión ${empresaId} se autoterminó (loggedOut)`);
    };
    this.sessions.set(empresaId, session);
    try {
      await session.start();
    } catch (err) {
      console.error(`[manager] Error iniciando ${empresaId}:`, err);
      this.sessions.delete(empresaId);
    }
  }

  private async stopSession(empresaId: string): Promise<void> {
    const session = this.sessions.get(empresaId);
    if (!session) return;
    console.log(`[manager] Cerrando sesión para tenant=${empresaId}`);
    try {
      await session.shutdown();
    } catch (err) {
      console.error(`[manager] Error cerrando ${empresaId}:`, err);
    }
    this.sessions.delete(empresaId);
  }

  /**
   * Heartbeat: actualiza last_seen_at en Airtable para sesiones activas.
   * Usa touchWaSession (NO upsert) — si el usuario borró la row, no la
   * recreamos. El próximo pollOnce detectará la ausencia y matará la sesión.
   */
  private async heartbeat(): Promise<void> {
    const now = new Date().toISOString();
    for (const empresaId of this.sessions.keys()) {
      try {
        await airtable.touchWaSession(empresaId, { last_seen_at: now });
      } catch {
        // No bloqueante.
      }
    }
  }
}
