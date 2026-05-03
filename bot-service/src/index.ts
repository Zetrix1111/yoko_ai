/**
 * bot-service — entry point.
 *
 * Carga env, instancia SessionManager + OutboxPoller, queda corriendo.
 * Maneja SIGINT/SIGTERM para shutdown ordenado.
 */

import "dotenv/config";

import { SessionManager } from "./session-manager";
import { OutboxPoller } from "./outbox-poller";

const REQUIRED_ENV = ["AIRTABLE_TOKEN", "AIRTABLE_BASE_ID", "YOKO_BASE_URL"];

async function main(): Promise<void> {
  console.log("════════════════════════════════════════════════");
  console.log("  Yoko bot-baileys — WhatsApp ↔ IA bridge");
  console.log("════════════════════════════════════════════════");

  // Validar env
  const missing = REQUIRED_ENV.filter((k) => !process.env[k]);
  if (missing.length > 0) {
    console.error(`[bot] FALTAN env vars: ${missing.join(", ")}`);
    console.error(`[bot] Copiá .env.example a .env y rellená los valores.`);
    process.exit(1);
  }

  console.log(`[bot] AIRTABLE_BASE_ID = ${process.env.AIRTABLE_BASE_ID}`);
  console.log(`[bot] YOKO_BASE_URL    = ${process.env.YOKO_BASE_URL}`);

  const manager = new SessionManager();
  const outbox = new OutboxPoller(manager);

  await manager.start();
  outbox.start();

  console.log("[bot] LISTO. Polling wa_sessions cada 5s, outbox cada 2s.");
  console.log("[bot] Ctrl+C para cerrar.");
  console.log("");

  const shutdown = async (signal: string) => {
    console.log(`\n[bot] ${signal} recibido. Cerrando...`);
    outbox.stop();
    await manager.stop();
    console.log("[bot] Bye.");
    process.exit(0);
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

main().catch((err) => {
  console.error("[bot] FATAL:", err);
  process.exit(1);
});
