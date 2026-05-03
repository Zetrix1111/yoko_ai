/**
 * OutboxPoller — cada 2s, busca filas de outbox con sent=false y las envía
 * vía la sesión Baileys del tenant correspondiente.
 *
 * Si la sesión del tenant no está activa en memoria, la fila queda como
 * sent=false y reintenta automáticamente en el siguiente tick (útil para
 * cuando la conexión de WA se restablece después de un corte transitorio).
 */

import * as airtable from "./airtable";
import { SessionManager } from "./session-manager";

export class OutboxPoller {
  manager: SessionManager;
  pollIntervalMs = 2000;
  pollTimer: NodeJS.Timeout | null = null;
  pollInFlight = false;

  constructor(manager: SessionManager) {
    this.manager = manager;
  }

  start(): void {
    this.pollTimer = setInterval(() => {
      this.pollOnce().catch((err) => console.error("[outbox] poll error:", err));
    }, this.pollIntervalMs);
  }

  stop(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  async pollOnce(): Promise<void> {
    if (this.pollInFlight) return;
    this.pollInFlight = true;
    try {
      let rows: airtable.AirtableRecord[] = [];
      try {
        rows = await airtable.getPendingOutbox();
      } catch (err) {
        console.error("[outbox] No se pudo listar outbox:", err);
        return;
      }
      if (rows.length === 0) return;

      for (const row of rows) {
        const empresaId: string = row.fields.empresa_id;
        const phone: string = row.fields.phone;
        const content: string = row.fields.content || "";

        if (!empresaId || !phone || !content) {
          console.warn(`[outbox] Fila ${row.id} mal formada, skip`);
          continue;
        }

        const session = this.manager.sessions.get(empresaId);
        if (!session) {
          // Sin sesión activa para ese tenant → reintenta más tarde
          console.log(`[outbox] ${empresaId}: sin sesión activa, ${row.id} queda pendiente`);
          continue;
        }

        try {
          await session.sendText(phone, content);
          await airtable.markOutboxSent(row.id);
          const preview = content.length > 50 ? content.slice(0, 50) + "..." : content;
          console.log(`[outbox] → ${phone} (${empresaId}): "${preview}"`);
        } catch (err: any) {
          console.error(`[outbox] Error enviando ${row.id}:`, err?.message || err);
          // No marcar sent. Reintenta en el próximo tick.
        }
      }
    } finally {
      this.pollInFlight = false;
    }
  }
}
