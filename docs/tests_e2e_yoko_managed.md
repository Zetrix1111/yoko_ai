# Tests E2E — Yoko + Anthropic Managed Agents (chat web)

Checklist manual que se corre **una vez** después de provisionar el agent y
antes de prender `YOKO_BACKEND=managed_agents` en Production.

Empresa de prueba: **cmejia**.

---

## Pre-requisitos

Antes de empezar, confirmar que:

- [ ] `provision_agent.py` corrió OK contra el agent `agent_017xab...`. La
  Console de Anthropic muestra el agent con: 3 tools (`yoko_procesar_archivos`,
  `yoko_generar_registro_contable`, `yoko_recuperar_proceso`), 1 skill (`facturas-inteligentes`),
  system prompt actualizado.
- [ ] En Vercel → Project Settings → Environment Variables → **Preview**:
  - `YOKO_BACKEND=managed_agents`
  - `VITE_YOKO_BACKEND=managed_agents`
  - `KV_REST_API_URL` y `KV_REST_API_TOKEN` (auto-inyectados por Upstash).
  - `ANTHROPIC_API_KEY`, `YOKO_AGENT_ID`, `YOKO_ENVIRONMENT_ID`,
    `YOKO_VAULT_ID_CMEJIA`, `YOKO_MEMORY_STORE_ID_CMEJIA`.
- [ ] Push a una branch que dispare un Preview deployment. Anotar la URL
  (ej. `https://yoko-chat-git-managed-agents-zetrix1111.vercel.app`).
- [ ] Tener a mano 3 PDFs de facturas reales de cmejia para los tests T3-T6.
- [ ] Production sigue con `YOKO_BACKEND=openai`. **No tocar todavía.**

---

## Tests

> Convención: ✅ pasa, ⚠️ pasa con observación, ❌ falla.

### T1 — Saludo personalizado y módulos correctos

**Input**: login en el Preview con María (cmejia) → mandar "Hola" en el chat.

**Esperado**:
- Yoko saluda usando el nombre o un cierre cordial (no formulario robótico).
- Si pregunta por capacidades, menciona los módulos activos de cmejia
  (caja-chica, facturas-inteligentes, ventas-inteligentes, etc.) — NO
  inventa módulos como "fianzas" o "compras".
- En logs Vercel: `[chat/managed] session NUEVA sess_... para cmejia/<dni>`.

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T2 — Módulo no activo

**Input**: "¿Cómo está mi fianza con BBVA?"

**Esperado**:
- Yoko responde que el módulo de fianzas **no está activo** para esta empresa.
- NO inventa datos de fianzas. NO inventa nombres de bancos.
- Tono cordial — sugiere contactar al administrador o pasa a otro tema.

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T3 — Subir 1 PDF de factura

**Input**: adjuntar 1 PDF de factura real → enviar.

**Esperado**:
- Yoko confirma recepción con frase tipo "Listo (1). ¿Más comprobantes?".
- En logs: el frontend mandó `attachments` con base64 del PDF (no llamó
  `parse_file`).
- En logs Vercel: el handler `[chat/managed]` recibe la request y manda
  el adjunto a la session.
- El agent NO procesa todavía — espera que el usuario diga "es todo".

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T4 — Acumular 2 PDFs más

**Input**: en el mismo chat, adjuntar 2 PDFs más en mensajes separados.

**Esperado**:
- Yoko alterna verbos de confirmación: "Recibido (2)", "Anotado (3)".
- Mantiene "¿Más comprobantes?" estable.
- El contador `(N)` refleja el total acumulado.

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T5 — Cierre del carrito + propuesta tipo+mes

**Input**: "ya está, procesa".

**Esperado**:
- Yoko propone procesar como "Registro de compras" del **mes actual**.
- Pide confirmación antes de procesar.
- Mensaje incluye `Tipo: Registro de compras` y `Mes: <mes_actual> <año>`.

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T6 — Confirmar y procesar

**Input**: "ok".

**Esperado**:
- Yoko llama el tool `yoko_procesar_archivos` con los 3 archivos.
- En logs Vercel: `[chat/managed] tool yoko_procesar_archivos` → POST
  `/api/facturas?action=procesar-chat` con el JWT del usuario reenviado.
- El endpoint procesa los 3 PDFs (logs `[facturas/procesar-chat]`) y
  devuelve `proceso_id` + array de facturas.
- Yoko devuelve un resumen al usuario (cuántas facturas procesadas, totales)
  y le indica que puede editarlas en la pantalla "Facturas Inteligentes"
  o pedir el Excel directo en el chat.
- El proceso queda persistido en SQLite (`/tmp/facturas.db` en Vercel).

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T6.1 — Generar Excel via chat (extensión opcional)

**Input** (después de T6 OK): "mándame el excel".

**Esperado**:
- Yoko llama `yoko_generar_registro_contable` con el `proceso_id` de T6.
- El handler `download-chat` devuelve el `.xlsx` en base64.
- Yoko devuelve un link de descarga o confirma que el archivo está listo
  (la UI puede no mostrar el binario directamente — está OK si el agent
  solo confirma "listo" y el usuario va a descargarlo desde la pantalla).

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T7 — Persistencia de session entre logins

**Input**:
1. Tomar nota del `session_id` de los logs (T1).
2. Cerrar sesión en Yoko (logout en el frontend).
3. Volver a hacer login con el mismo usuario (mismo DNI).
4. Mandar "¿qué hicimos antes?".

**Esperado**:
- En los logs Vercel del paso 4, NO aparece `session NUEVA` — el handler
  reusa el `session_id` cacheado en KV (TTL de 4 hrs).
- Yoko recuerda el contexto de la conversación previa (que se procesaron
  3 facturas, el `proceso_id`, etc.).

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

### T8 — Expiración por inactividad (4 hrs)

**Input** (largo, idealmente al día siguiente):
1. Esperar más de 4 hrs sin actividad en el chat para ese usuario.
2. Mandar un mensaje cualquiera.

**Esperado**:
- En logs: la cache key `yoko:session:cmejia:<dni>` expiró → handler
  registra `session NUEVA sess_... para cmejia/<dni>`.
- Yoko NO recuerda el contexto previo de T6 — empieza limpio.
- El system prompt se re-inyecta con el bloque `<contexto_empresa>`.

Resultado: [ ] ✅ / [ ] ⚠️ obs: ___ / [ ] ❌

---

## Métricas a registrar

Para cada test, anotar (de Anthropic Dashboard + Vercel logs):

| Test | Input tokens | Output tokens | Latencia (s) | Costo aprox. ($) |
|------|--------------|---------------|--------------|------------------|
| T1   |              |               |              |                  |
| T2   |              |               |              |                  |
| T3   |              |               |              |                  |
| T4   |              |               |              |                  |
| T5   |              |               |              |                  |
| T6   |              |               |              |                  |
| T6.1 |              |               |              |                  |
| T7   |              |               |              |                  |

**Esperado**: costo total de la corrida completa entre **$0.05 y $0.30**
(ver proyección en `api/PLAN_YOKO_MANAGED_AGENTS.md`). Si supera $0.50,
revisar si el system prompt + skill quedaron muy pesados o si el agent
está re-loopeando innecesariamente sobre tools.

---

## Errores comunes

| Síntoma | Causa probable | Fix |
|---------|----------------|-----|
| `400 No hay mensaje del usuario.` | Frontend mandó `messages` vacío | Verificar que `useChat.js` está en branch `managed_agents` y `VITE_YOKO_BACKEND` quedó horneado al bundle |
| `502 Error iniciando la conversación.` | `create_session` falló contra Anthropic | Revisar logs `[managed_agents]`. Si dice "vault sin credenciales" → ver "Vault vacía" abajo |
| `500 Empresa no habilitada para el backend Managed Agents.` | empresa_id del JWT no está en `_VAULT_ENV_BY_EMPRESA` | Hoy solo `cmejia` está habilitada. Para sumar empresa nueva: agregar entry al dict en `handler_managed.py` + Vault y MemoryStore en Anthropic + env vars en Vercel |
| Yoko no llama el tool `yoko_procesar_archivos` aunque hay archivos | Skill no está cargado en el agent O system prompt no menciona el skill | Correr `python scripts/sync_skills_to_anthropic.py --dry-run` para ver el diff |
| `KV_REST_API_URL` no encontrada en runtime | Integración Upstash no quedó vinculada | Vercel Dashboard → Storage → vincular KV al proyecto |
| Tools llaman pero responden con error de auth (401) | El JWT del usuario no llegó a la action `*-chat` | Confirmar que `useChat.js` manda `Authorization` header. Patrón es `postJsonAuth` que ya lo incluye |

### Vault vacía

Si Anthropic rechaza `create_session` porque la Vault no tiene credenciales:

**Opción A — Hacer el `vault_id` opcional**:
En `api/_lib/managed_agents_client.py::create_session`, dejar de mandar
`vault_id` en el body si no aplica. (Cambio de 2 líneas.)

**Opción B — Credencial dummy en la Vault**:
En Claude Console → Bóvedas → yoko-cmejia → Añadir credencial:
- Tipo: Token Bearer
- Nombre: "placeholder-no-usado"
- MCP Server: `https://example.com`
- Token: cualquier string

(El agent no la usa porque no tiene un tool MCP configurado, pero la Vault
queda con ≥1 credencial.)

---

## Pasaje a producción

Solo después de que **todos** los tests T1-T8 pasen ✅:

1. Vercel → Production env vars:
   - Cambiar `YOKO_BACKEND` de `openai` → `managed_agents`.
   - Agregar `VITE_YOKO_BACKEND=managed_agents`.
2. Hacer un deploy a Production (`git push main` o "Promote to Production"
   desde Vercel UI).
3. Monitorear logs durante las primeras 24-48 hrs.
4. Si algo se descompone: cambiar `YOKO_BACKEND` de vuelta a `openai`.
   Rollback en <1 minuto, sin redeploy (la lectura es por-request).

NO eliminar la lógica legacy de OpenAI durante 30 días — queda como
fallback hasta confirmar estabilidad.
