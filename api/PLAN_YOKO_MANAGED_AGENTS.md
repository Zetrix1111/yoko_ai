# Plan de implementación — Yoko con Managed Agents (chat web)

> **Repositorio**: https://github.com/Zetrix1111/yoko_ai
> **Branch base**: `main` (refactor extraction ya aplicado)
> **Estado**: pendiente de implementar
> **Duración estimada**: 25-35 hrs distribuidas en 8 etapas
> **Alcance**: chat web únicamente. WhatsApp queda para Fase 2.
> **Empresa piloto**: cmejia

---

## RESUMEN EJECUTIVO

Integrar Anthropic Managed Agents como nuevo backend conversacional de Yoko. El usuario sigue interactuando desde el chat web actual (`ChatScreen.jsx` + `useChat.js`). En backend, se reemplaza el actual loop OpenAI tool-calling de `api/_yoko/handler.py` por un orquestador que delega en Managed Agents.

**Cero cambios visuales para el usuario final**. La UI sigue idéntica. Lo que cambia es el backend conversacional.

**Cero cambios** en módulos de ventas (`api/_ventas/`, `bot-service/`). Quedan intactos.

WhatsApp queda fuera de scope de este plan — se aborda en Fase 2 una vez validado el chat web.

---

## DECISIONES YA CERRADAS (referencia rápida)

| ID | Decisión |
|----|----------|
| Modelo | Claude Sonnet 4.6 |
| Empresa piloto | cmejia |
| Multi-tenancy | Agent universal + contexto inyectado por session |
| Skills | yoko-facturas (listo) + futuros sin tocar agent |
| Custom tools | yoko_procesar_archivos, yoko_generar_excel, yoko_recuperar_proceso |
| Cache de sessions | Vercel KV (Upstash REST) |
| TTL de session | 4 hrs de inactividad |
| Modelo de billing | Tu cuenta Anthropic única (tracking por metadata.empresa_id) |
| Bot WhatsApp | Fuera de este plan — Fase 2 |

---

## PRE-REQUISITOS QUE EL OWNER DEBE TENER LISTOS

Antes de pasarle este plan a Claude Code, el owner debe haber completado:

- [ ] Crear cuenta en `platform.claude.com` con beta de Managed Agents activa
- [ ] Crear **Environment** llamado `yoko-prod` (Python 3.11)
  - Networking: Limited
  - Hosts permitidos: `yokochat.vercel.app`, `api.airtable.com`, `api.openai.com`
  - Acceso a paquetes: ACTIVADO
  - Paquetes: `requests httpx pyjwt python-dateutil`
  - Anotar: `YOKO_ENVIRONMENT_ID`
- [ ] Crear **Vault** llamado `yoko-cmejia` (vacío por ahora)
  - Anotar: `YOKO_VAULT_ID_CMEJIA`
- [ ] Crear **Memory Store** llamado `yoko-cmejia`
  - Anotar: `YOKO_MEMORY_STORE_ID_CMEJIA`
- [ ] Activar **Vercel KV** (Upstash for Redis) en proyecto `yokochat`
  - Las env vars `KV_REST_API_URL`, `KV_REST_API_TOKEN` se inyectan automáticamente
- [ ] Generar **API key de Anthropic** (`sk-ant-...`)
- [ ] Tener acceso a Vercel para agregar variables de entorno

Si algo de esto falta, **detenerse y pedir al owner que lo complete antes de empezar**.

---

## INSTRUCCIONES GENERALES PARA CLAUDE CODE

### Reglas de trabajo

1. **Trabajar UNA etapa a la vez**. No avanzar a la siguiente sin que el owner confirme.
2. **Antes de cada etapa**, leer los archivos del repo que la etapa va a tocar/usar.
3. **Después de cada etapa**, entregar al owner:
   - Lista exacta de archivos creados/modificados
   - Comandos exactos para validar localmente
   - Variables de entorno nuevas que falten configurar
4. **NO modificar** las siguientes carpetas/archivos (están fuera de scope):
   - `api/_lib/parse_file.py` — usar via re-exports (ya está refactorizado)
   - `api/_lib/facturas_processor.py` — funcionando bien
   - `api/_lib/contabilidad.py`
   - `api/_lib/db_manager.py`
   - `api/_ventas/` — módulo de ventas
   - `bot-service/` — bot de ventas (existente)
   - `api/_yoko/_lib/prompt.py` y `api/_yoko/_lib/tool_registry.py` — los dejamos por compatibilidad con el modo legacy
5. **Mantener compatibilidad legacy**: el endpoint `/api/chat` actual debe seguir funcionando con OpenAI durante la migración. Se introduce un feature flag `YOKO_BACKEND` (`openai` | `managed_agents`) para alternar.
6. **Idioma**: comentarios y mensajes de usuario en español. Nombres de funciones/variables en inglés.

### Stack confirmado

- Python 3.11 (Vercel serverless, no FastAPI)
- Anthropic Managed Agents (beta header: `managed-agents-2026-04-01`)
- SDK oficial: `pip install anthropic`
- Vercel KV via REST API (no instalar `@vercel/kv`, se llama via HTTP)
- Frontend: cero cambios estructurales, máximo ajustes en `useChat.js`

### Convenciones del repo

- Imports al tope. Type hints siempre que se pueda (consistencia con `parse_file.py` ya refactorizado).
- Errores HTTP: `req._json(STATUS, {"error": "msg"})` (patrón existente).
- Logs: `print(f"[modulo] msg", file=sys.stderr)` (patrón existente).
- Paths: `_HERE = os.path.dirname(os.path.abspath(__file__))` + `sys.path.insert` (patrón existente).
- Re-exports legacy en módulos viejos para no romper consumers.

### Lo que ESTÁ provisto al owner (ya generado, owner los descarga)

- `skills/yoko-facturas/SKILL.md` — skill listo (Claude Code lo coloca tal cual en el repo)
- Plan maestro original (`PLAN_MAESTRO.md`)
- Plan etapa 0.5 ejecutado (refactor extraction)

---

## ARQUITECTURA RESULTANTE

```
┌─────────────────────────────────────────────────────────┐
│  src/features/chat/   (sin cambios estructurales)       │
│  • ChatScreen.jsx                                       │
│  • useChat.js  (ajustes mínimos para SSE en futuro)    │
└──────────────────────┬──────────────────────────────────┘
                       │  POST /api/chat
                       ↓
┌─────────────────────────────────────────────────────────┐
│  api/chat.py  (dispatcher delgado, sin cambios)         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  api/_yoko/handler.py  (MODIFICADO con feature flag)    │
│                                                          │
│  if env(YOKO_BACKEND) == "managed_agents":              │
│      delegate to api/_yoko/handler_managed.py           │
│  else:                                                   │
│      legacy openai tool-calling (sin cambios)           │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  api/_yoko/handler_managed.py (NUEVO)                   │
│                                                          │
│  1. Identificar empresa (por user actual del JWT)       │
│  2. get_or_create_session() en Vercel KV                │
│  3. Si nueva: inyectar contexto                         │
│  4. Mandar mensaje + archivos a la session              │
│  5. Recibir respuesta SSE → devolver al cliente         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  api/_lib/managed_agents_client.py  (NUEVO)             │
│  Wrapper del SDK Anthropic con beta header.             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Anthropic Managed Agents (cloud)                       │
│  • Agent yoko-empresarial                               │
│  • Skills: yoko-facturas                                │
│  • Custom tools (HTTP a tu API):                        │
│      yoko_procesar_archivos                             │
│      yoko_generar_excel                                 │
│      yoko_recuperar_proceso                             │
└──────────────────────┬──────────────────────────────────┘
                       │  HTTP back to your Vercel API
                       ↓
┌─────────────────────────────────────────────────────────┐
│  api/facturas.py  (MODIFICADO: action=procesar-chat)    │
│                                                          │
│  Recibe lote en JSON+base64 (no multipart).             │
│  Reusa facturas_processor.py + contabilidad.py.         │
└─────────────────────────────────────────────────────────┘
```

---

## ETAPAS DE IMPLEMENTACIÓN

> Cada etapa termina con una validación concreta. NO avanzar sin confirmación.

---

### ETAPA A — Variables de entorno y dependencias

**Duración**: 30 min  
**Bloqueante**: sí  
**Depende de**: setup manual del owner ya completo

#### Tareas

1. Agregar al `pyproject.toml` (o `requirements.txt` según el repo) la dependencia:
   ```
   anthropic>=0.40.0
   ```

2. Agregar a Vercel las siguientes env vars (el owner las pone, Claude Code solo lista qué necesita):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   YOKO_AGENT_ID=               # se llena en Etapa C
   YOKO_ENVIRONMENT_ID=env_...  # del setup
   YOKO_VAULT_ID_CMEJIA=vlt_... # del setup
   YOKO_MEMORY_STORE_ID_CMEJIA=mem_...
   YOKO_BACKEND=openai          # feature flag, empieza en openai

   # Vercel KV ya inyectadas:
   KV_REST_API_URL=
   KV_REST_API_TOKEN=
   ```

3. Crear archivo `.env.example` (o actualizar el existente) con todas las variables nuevas documentadas.

#### Validación

- `pip install -r requirements.txt` (o equivalente) instala `anthropic` sin errores.
- `python -c "from anthropic import Anthropic; print(Anthropic.__module__)"` no falla.

---

### ETAPA B — Cliente de Vercel KV (session cache)

**Duración**: 2-3 hrs  
**Depende de**: Etapa A

#### Tareas

1. Crear `api/_lib/kv_client.py` — wrapper REST de Upstash:
   - `kv_get(key) -> str | None`
   - `kv_set(key, value, ttl_seconds=None) -> bool`
   - `kv_delete(key) -> bool`
   - `kv_exists(key) -> bool`
   - Usa `KV_REST_API_URL` y `KV_REST_API_TOKEN` del env.
   - Llamadas con `urllib.request` (consistente con el resto del repo, sin `requests` extra).
   - Errores se loguean a stderr con prefix `[kv_client]`.

2. Crear `api/_lib/yoko_session_store.py`:
   ```python
   def get_or_create_session(empresa_id: str, user_id: str) -> tuple[str, bool]:
       """
       Devuelve (session_id, is_new).
       is_new = True si tuvo que crear una nueva session.

       Cache key: "yoko:session:{empresa_id}:{user_id}"
       TTL: 4 hrs (renovable en cada acceso)
       """

   def force_new_session(empresa_id: str, user_id: str) -> None:
       """Borra del cache para forzar session nueva en próxima request."""

   def get_session_metadata(session_id: str) -> dict | None:
       """Devuelve metadata cacheada (empresa_id, user_id, created_at)."""
   ```
   
   Inicialmente la creación real de la session en Anthropic se hace en Etapa F. Acá solo se cachea el id.

#### Validación

```python
# Script de test manual: scripts/test_kv.py
from _lib.kv_client import kv_set, kv_get, kv_delete

kv_set("test:hello", "world", ttl_seconds=60)
assert kv_get("test:hello") == "world"
kv_delete("test:hello")
assert kv_get("test:hello") is None
print("✅ KV funciona")
```

---

### ETAPA C — Managed Agents Client + Provisioning del Agent

**Duración**: 4-5 hrs  
**Depende de**: Etapa A

#### Tareas

1. Crear `api/_lib/managed_agents_client.py`:
   - Función `get_client()` que devuelve `Anthropic(api_key=ANTHROPIC_API_KEY)` con beta header `managed-agents-2026-04-01`.
   - Funciones helper:
     - `create_session(empresa_id, user_id, vault_id, memory_store_id) -> session_id`
     - `send_user_message(session_id, content, attachments=None)`
     - `stream_assistant_response(session_id) -> generator de chunks`
     - `close_session(session_id)`
   - Manejo robusto de errores: timeouts, rate limits, errores de red.

2. Crear estructura `api/_yoko_agents/`:
   ```
   api/_yoko_agents/
   ├── __init__.py
   ├── agent_definition.py      ← define el agent en código
   ├── provision_agent.py       ← script idempotente de creación
   └── tools/
       ├── __init__.py
       ├── procesar_archivos.py
       ├── generar_excel.py
       └── recuperar_proceso.py
   ```

3. En `agent_definition.py`:
   - Función `get_agent_config() -> dict` que devuelve el dict con name, model, system, tools, skills.
   - El `system` se carga desde `skills/_system_prompts/yoko-empresarial.md` (a crear) o se hardcoddea en el archivo. **Recomendación**: archivo separado para que el sysprompt sea editable sin tocar código Python.
   - Tools en formato compatible con Anthropic API (JSON schema).
   - Skills se cargan dinámicamente desde el directorio `skills/` del repo (Etapa E).

4. En `provision_agent.py`:
   - Script ejecutable: `python -m api._yoko_agents.provision_agent`.
   - Si no existe `YOKO_AGENT_ID` en env: crea agent nuevo, imprime el id, instruye al owner que lo agregue a Vercel.
   - Si existe `YOKO_AGENT_ID`: actualiza el agent existente (update sysprompt, tools, skills).
   - Idempotente: correrlo dos veces seguidas no falla, solo actualiza.

5. Custom tools — definirlos en `tools/*.py` como funciones que retornan el JSON Schema esperado por Anthropic:

   **`procesar_archivos.py`**:
   ```python
   TOOL_DEFINITION = {
       "name": "yoko_procesar_archivos",
       "description": "Procesa comprobantes de pago peruanos (factura, boleta, NC, ND, RH, ticket, boleto aéreo) en formato PDF/JPG/PNG/WEBP. Acepta hasta 50 archivos por lote. Devuelve datos estructurados: proveedor, RUC, serie, monto, etc.",
       "input_schema": {
           "type": "object",
           "properties": {
               "tipo": {"type": "string", "enum": ["compra", "venta"]},
               "mes": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
               "files": {
                   "type": "array",
                   "items": {
                       "type": "object",
                       "properties": {
                           "filename": {"type": "string"},
                           "content_b64": {"type": "string"},
                       },
                       "required": ["filename", "content_b64"],
                   },
                   "maxItems": 50,
               },
           },
           "required": ["tipo", "mes", "files"],
       },
   }
   ```

   **`generar_excel.py`**:
   ```python
   TOOL_DEFINITION = {
       "name": "yoko_generar_excel",
       "description": "Genera el Excel del registro de compras/ventas en el formato contable de la empresa (CONCAR/SISCONT/etc.) a partir de un proceso ya procesado.",
       "input_schema": {
           "type": "object",
           "properties": {
               "proceso_id": {"type": "string"},
           },
           "required": ["proceso_id"],
       },
   }
   ```

   **`recuperar_proceso.py`**:
   ```python
   TOOL_DEFINITION = {
       "name": "yoko_recuperar_proceso",
       "description": "Consulta los detalles de un proceso ya creado (estado, facturas extraídas, totales).",
       "input_schema": {
           "type": "object",
           "properties": {
               "proceso_id": {"type": "string"},
           },
           "required": ["proceso_id"],
       },
   }
   ```

   IMPORTANTE: estos tools NO se ejecutan en el sandbox de Anthropic en este plan. Anthropic los va a llamar via "tool use" pattern, y nuestro orquestador (Etapa F) detecta esos tool calls y los ejecuta llamando endpoints de Vercel (mismo proceso, llamada interna). Esto evita la complejidad de ejecutar Python en el sandbox de Anthropic.

#### Validación

1. Correr `python -m api._yoko_agents.provision_agent` (con env vars correctas).
2. Verificar en `platform.claude.com/agents` que apareció el agent.
3. Crear una session de prueba manualmente desde la UI de Anthropic con este agent y mandar "Hola" — debería responder.

---

### ETAPA D — Skills: estructura y sincronización

**Duración**: 3 hrs  
**Depende de**: Etapa C

#### Tareas

1. Crear estructura en el repo:
   ```
   skills/
   ├── README.md          (ya provisto al owner, copiarlo)
   ├── _system_prompts/
   │   └── yoko-empresarial.md   ← system prompt del agent
   ├── _template/
   │   └── SKILL.md       (ya provisto al owner, copiarlo)
   └── yoko-facturas/
       ├── SKILL.md       (ya provisto al owner, copiarlo tal cual)
       └── README.md      ← describir el skill, custom tools que usa, casos de prueba
   ```

2. Crear `scripts/sync_skills_to_anthropic.py`:
   - Lee todos los `SKILL.md` de `skills/*/`.
   - Lee el system prompt de `skills/_system_prompts/yoko-empresarial.md`.
   - Llama a la API de Anthropic para actualizar el agent (`YOKO_AGENT_ID`) con los skills nuevos y system prompt actualizado.
   - Idempotente: si los skills no cambiaron, no hace nada.
   - Imprime un diff legible de qué cambió.

3. NO crear GitHub Actions todavía (queda para futuro). Sync manual ahora.

#### Validación

1. Correr `python scripts/sync_skills_to_anthropic.py`.
2. En la UI de Anthropic, verificar que el agent tiene el skill `yoko-facturas` cargado.
3. Crear session manual, mandar "Tengo facturas para procesar" — el agent debería activar el skill y pedir que se manden archivos.

---

### ETAPA E — Endpoint procesar-chat en facturas.py

**Duración**: 3-4 hrs  
**Depende de**: refactor extraction (ya hecho)

#### Tareas

1. Modificar `api/facturas.py`:
   - Agregar acción `procesar-chat`:
     - Recibe JSON: `{"tipo": "compra", "mes": "2026-05", "files": [{"filename": "...", "content_b64": "..."}]}`
     - Para cada file, decodifica base64 y reusa la lógica existente de `facturas_processor.py`.
     - Devuelve `{"proceso_id": "...", "facturas": [...], "alertas": [...]}`.
   - Agregar acción `download-chat`:
     - Recibe JSON: `{"proceso_id": "..."}`
     - Genera Excel CONCAR (lógica existente) y devuelve archivo binario.
   - Agregar acción `recuperar-chat`:
     - Recibe JSON: `{"proceso_id": "..."}`
     - Devuelve datos del proceso (consulta SQLite/Airtable existente).
   - Auth: estos endpoints requieren un JWT especial (signed por `YOKO_BOT_SERVICE_TOKEN`) que solo conoce el agent en su Vault.

2. NO romper las acciones existentes (`procesar`, `concar`, etc.) — solo agregar las nuevas.

3. Documentar formato esperado en docstring del archivo.

#### Validación

```bash
# Test manual con curl
JWT=$(python scripts/generate_jwt_token.py --empresa cmejia --scope agent)
curl -X POST "https://yokochat.vercel.app/api/facturas?action=procesar-chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "compra",
    "mes": "2026-05",
    "files": [{"filename": "test.pdf", "content_b64": "..."}]
  }'
# Debe responder con proceso_id y facturas extraídas.
```

---

### ETAPA F — Handler managed (orquestador)

**Duración**: 5-6 hrs  
**Depende de**: Etapas B, C, D, E

#### Tareas

1. Crear `api/_yoko/handler_managed.py`:
   - Función `handle_post(req)` con la misma firma que el handler legacy.
   - Lógica:
     1. Auth (mismo que handler legacy: extraer JWT, sacar user, empresa_id).
     2. Parse body: `{"messages": [...], "user": {...}}`.
     3. Tomar el último mensaje del usuario (asumir frontend manda solo el último, no todo el historial — Managed Agents persiste eso server-side).
     4. `session_id, is_new = get_or_create_session(empresa_id, user_id)`.
     5. Si `is_new`: construir contexto via `yoko_context_builder.construir_contexto_empresa(empresa_id, user)` y mandar como primer evento en la session.
     6. Mandar el mensaje del usuario como evento.
     7. Stream de la respuesta del assistant.
     8. **Manejo de tool calls**: cuando el agent dispare `yoko_procesar_archivos`, `yoko_generar_excel` o `yoko_recuperar_proceso`:
        - Interceptar el tool call.
        - Hacer HTTP request a `https://yokochat.vercel.app/api/facturas?action=procesar-chat` (o el endpoint correspondiente) usando JWT del Vault.
        - Devolver el resultado al agent como `tool_result`.
     9. Acumular la respuesta final del agent y devolverla al frontend en formato compatible con el actual: `{"text": "...", "action": null}`.

2. Crear `api/_lib/yoko_context_builder.py`:
   - Función `construir_contexto_empresa(empresa_id, user) -> str`.
   - Lee de Airtable: `Empresas.modulos_habilitados`, `Config_Empresa.basicos.sistema_contable`, `Empresas.razon_social`, `Empresas.ruc`.
   - Construye string en formato `<contexto_empresa>...</contexto_empresa>`.
   - **Importante**: el bloque debe coincidir exactamente con el formato que espera el system prompt de Yoko (ver `skills/_system_prompts/yoko-empresarial.md`).

3. Modificar `api/_yoko/handler.py`:
   - Agregar feature flag al inicio:
     ```python
     YOKO_BACKEND = os.environ.get("YOKO_BACKEND", "openai")
     ```
   - En `handle_post`:
     ```python
     if YOKO_BACKEND == "managed_agents":
         from _yoko.handler_managed import handle_post as handle_managed
         return handle_managed(req)
     # ... lógica legacy de OpenAI sin cambios
     ```

#### Validación

1. Setear `YOKO_BACKEND=managed_agents` en Vercel (preview deployment, no production).
2. Hacer login en el preview con un usuario de cmejia.
3. Mandar "Hola" en el chat — debe responder con saludo personalizado por nombre y mencionar los módulos activos de cmejia.
4. Mandar "Quiero procesar facturas" + adjuntar 2 PDFs — el agent debe activar el skill, llamar el tool, y devolver resumen + magic link... 
   - **AJUSTE**: como en este plan no hay magic link aún (Fase 2), el agent solo devuelve el resumen y dice "Edita en la pantalla de Facturas Inteligentes" o similar. Confirmar este comportamiento esperado en el SKILL.md.
5. Si funciona: dejar `YOKO_BACKEND=openai` en producción y `managed_agents` solo en preview hasta que el owner valide más.

---

### ETAPA G — Frontend: ajustes mínimos

**Duración**: 2-3 hrs  
**Depende de**: Etapa F

#### Tareas

Lo más probable es que el frontend NO necesite cambios. La interfaz `{"text": "...", "action": null}` se mantiene idéntica.

**Pero verificar**:

1. ¿El `useChat.js` actual manda `messages` (array completo) o solo el último mensaje?
   - Si manda array completo: dejarlo así, el handler_managed puede ignorar todos menos el último (Managed Agents tiene su propio historial).
   - Si manda solo el último: ya está perfecto.

2. ¿El frontend procesa archivos via `parse_file` ANTES de mandar el chat?
   - Mirando el código actual: SÍ (`useChat.js` líneas ~50-80 llaman `postFormAuth(API.PARSE_FILE, formData)`).
   - **Decisión**: dejar este flujo dual por ahora. La UI clásica de subir archivos en pantalla de facturas sigue usando parse_file directo. El chat web NUEVO con Managed Agents recibe los archivos como base64 dentro del mensaje.
   - Para el chat con Managed Agents: agregar una opción en `useChat.js` que detecte si `YOKO_BACKEND=managed_agents` (via feature flag client-side, ej: variable de Vite) y mande los archivos directamente al chat sin pre-procesarlos con parse_file.
   - Implementación: en `useChat.js`, si flag está activo, en vez de `postFormAuth(API.PARSE_FILE, ...)` para extraer campos, simplemente codificar archivos a base64 y meterlos en el mensaje del chat.

3. Documentar el flag client-side en un `.env` del frontend:
   ```
   VITE_YOKO_BACKEND=managed_agents
   ```

#### Validación

- Login con cmejia en el preview.
- Subir 1 PDF en el chat — debe llegar al backend en base64, el backend lo manda a Managed Agents, el agent activa el skill y procesa.
- Confirmar que la UI muestra correctamente la respuesta del agent.

---

### ETAPA H — Tests E2E con cmejia

**Duración**: 3-4 hrs  
**Depende de**: todas las anteriores

#### Tareas

1. **Pre-requisito**: verificar que `Usuarios.celular` está poblado para María, Cynthia, Pablo de cmejia (no es bloqueante para chat web, sí para Fase 2 WhatsApp).

2. **Llenar el Vault yoko-cmejia** con:
   - `YOKO_API_TOKEN`: JWT firmado especial que el agent usa para llamar tu API. Generar con `scripts/generate_jwt_token.py` (crear este script en esta etapa si no existe).
   - `YOKO_API_BASE`: `https://yokochat.vercel.app`.

3. **Tests funcionales** (manuales, documentar en `docs/tests_e2e_yoko_managed.md`):

   | Test | Input | Esperado |
   |------|-------|----------|
   | T1 | Login como María, mandar "Hola" en chat | Saludo personalizado, lista módulos cmejia |
   | T2 | Mandar "¿Cómo está mi fianza con BBVA?" | "Ese módulo no está activo" (cmejia no tiene módulo fianzas) |
   | T3 | Subir 1 PDF de factura | Carrito con 1 archivo, pregunta si hay más |
   | T4 | Subir 2 PDFs más | Carrito con 3 archivos |
   | T5 | "ya está, procesa" | Confirma tipo+mes |
   | T6 | "ok" | Procesa, devuelve resumen, indica que se puede editar en la pantalla de facturas |
   | T7 | Cerrar sesión y volver a entrar | Session anterior debe seguir activa (4 hrs TTL) y agent recuerda contexto |
   | T8 | Esperar 4 hrs sin actividad | Session expirada, próximo mensaje crea session nueva |

4. Documentar **métricas reales**:
   - Tokens consumidos por test (verificar en Anthropic dashboard).
   - Tiempo de respuesta promedio.
   - Costo aproximado por conversación.

#### Validación

- Todos los tests T1-T8 pasan según lo esperado.
- Costo por conversación está dentro del rango proyectado ($0.05-0.20).
- No hay errores 500 en logs de Vercel.

---

### ETAPA I — Cleanup y switch a producción

**Duración**: 2 hrs  
**Depende de**: Etapa H exitosa

#### Tareas

1. Si Etapa H pasó: cambiar `YOKO_BACKEND=managed_agents` en producción.

2. Monitorear primeras 24-48 hrs:
   - Logs de Vercel.
   - Costos en Anthropic dashboard.
   - Feedback del owner / equipo cmejia.

3. Si todo va bien: documentar en README principal del repo.

4. Crear issue en GitHub: "Fase 2: agregar soporte WhatsApp via yoko-bot-service" como roadmap futuro.

5. NO eliminar la lógica legacy de OpenAI todavía. Mantenerla por 30 días como fallback.

#### Validación

- Producción estable por al menos 1 semana.
- Owner satisfecho con comportamiento.
- Costos dentro de presupuesto proyectado.

---

## CHECKLIST DE ENTREGA POR ETAPA

Cada etapa debe terminar con Claude Code entregando al owner:

```markdown
## Etapa [LETRA] completada

### Archivos creados
- ruta/archivo1.py (XXX líneas)
- ruta/archivo2.py (XXX líneas)

### Archivos modificados
- ruta/archivo3.py (cambios: ...)

### Variables de entorno nuevas a configurar (owner debe poner en Vercel)
- VARIABLE_X: descripción

### Comandos de validación
1. `python ...` → debe imprimir ...
2. `curl ...` → debe responder ...

### Próximo paso
Esperar confirmación del owner para avanzar a Etapa [LETRA+1].
```

---

## REPORTE FINAL ESPERADO AL TERMINAR LAS 9 ETAPAS

```markdown
# Implementación Yoko + Managed Agents — Reporte final

## Etapas completadas
- [x] A: Variables y deps
- [x] B: KV client + session store
- [x] C: Managed Agents client + provisioning
- [x] D: Skills + sync
- [x] E: Endpoints procesar-chat
- [x] F: Handler managed (orquestador)
- [x] G: Frontend ajustes
- [x] H: Tests E2E
- [x] I: Cleanup

## Archivos finales
[Lista exhaustiva]

## Variables de entorno finales
[Lista exhaustiva]

## Métricas observadas
- Tokens promedio por conversación: X
- Costo promedio por conversación: $X
- Latencia promedio: X segundos
- Tasa de error: X%

## Pendientes / deuda técnica
- ...

## Recomendaciones para Fase 2 (WhatsApp)
- ...
```

---

## RIESGOS IDENTIFICADOS

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| Beta de Managed Agents cambia API | Media | Wrapper en `managed_agents_client.py` aísla cambios. SDK oficial debería absorberlos. |
| Costos crecen más de lo proyectado | Media | Activar prompt caching desde día 1. Alertas en Anthropic dashboard. Límites por session. |
| Frontend no soporta archivos > 5MB en JSON | Baja | Verificar límites de Vercel function payload (20MB hobby, 100MB pro). Si necesario, mantener `parse_file` directo para archivos grandes. |
| Session se traba en estado "running" | Baja | Implementar timeout client-side: si stream no responde en 60s, abortar y avisar al usuario. |
| Owner rompe limit de 12 functions de Vercel Hobby | Alta | Revisar conteo: actual 7 + agregamos `wa-magic-link`, `redeem-magic-link`, `notify-event` solo en Fase 2. En este plan, NO se agregan functions nuevas. Verificar antes de Etapa E. |

---

## LO QUE NO ESTÁ EN ESTE PLAN (futuro)

- ❌ yoko-bot-service (WhatsApp via Baileys)
- ❌ Magic links cross-channel
- ❌ Endpoint `/api/wa/incoming`
- ❌ Endpoint `/api/yoko/notify-event` 
- ❌ Soporte para SISCONT/FOXCONT (el sistema contable de cmejia es CONCAR)
- ❌ Skill yoko-caja-solicitud y yoko-caja-rendicion
- ❌ Skill yoko-fianzas
- ❌ Multi-empresa más allá de cmejia
- ❌ Sistema de billing por empresa
- ❌ GitHub Actions para auto-sync de skills
- ❌ Memory store con datos persistentes (se crea vacío en este plan)
- ❌ Migración de la pantalla web tradicional al chat (las dos coexisten)

Si Claude Code intenta agregar algo de esta lista, **detenerse y preguntar al owner**.

---

## NOTAS FINALES PARA CLAUDE CODE

1. **Mantén el modo legacy funcionando** durante toda la migración. El feature flag `YOKO_BACKEND=openai` debe seguir respondiendo perfectamente hasta que el owner explícitamente confirme el switch.

2. **No optimices prematuramente**. Streaming SSE puede esperar Fase 2 — para empezar, basta con respuesta sincrónica (esperar a que el agent termine y devolver todo el texto).

3. **Tests reales > tests sintéticos**. Para validar, usa archivos reales de cmejia (que el owner provea), no PDFs generados.

4. **Documenta en español**. El owner y equipo son hispanohablantes. Comentarios, mensajes de error, README — todo en español. Variables y nombres de funciones en inglés (consistencia con el repo).

5. **Si encuentras algo del repo que no entiendes**, lee el código y pregunta al owner. NO improvises asumiendo intenciones.

6. **Confirma cada etapa** antes de avanzar. NO encadenes 5 etapas seguidas sin pausa.

---

**FIN DEL PLAN**
