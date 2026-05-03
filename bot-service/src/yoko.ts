/**
 * Cliente HTTP para llamar a /api/sales_chat en Yoko (Vercel).
 * Es la única dependencia HTTP del bot — todo lo demás va por Airtable.
 */

import axios from "axios";

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SalesChatArgs {
  empresaId: string;
  phone:     string;
  nombre:    string;
  history:   ChatHistoryMessage[];
}

/**
 * POST /api/sales_chat → devuelve la respuesta de la IA.
 * Ya tiene contexto del catálogo del tenant cargado del lado servidor.
 */
export async function getSalesChatReply(args: SalesChatArgs): Promise<string> {
  const baseUrl = process.env.YOKO_BASE_URL;
  if (!baseUrl) {
    throw new Error("Falta YOKO_BASE_URL en env.");
  }
  // Endpoint consolidado en /api/ventas?resource=sales_chat (Vercel Hobby
  // limita a 12 funciones serverless; ventas.py centraliza todos los endpoints).
  const url = `${baseUrl.replace(/\/$/, "")}/api/ventas?resource=sales_chat`;

  const res = await axios.post(
    url,
    {
      empresa_id: args.empresaId,
      phone:      args.phone,
      nombre:     args.nombre,
      history:    args.history,
    },
    {
      timeout: 30000,  // ~mismo techo que Vercel maxDuration
      headers: { "Content-Type": "application/json" },
    },
  );

  const reply = (res.data?.reply || "").trim();
  return reply;
}
