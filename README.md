# Yoko Chat

Yoko Chat es una plataforma web multi-tenant para asistentes empresariales con IA. Combina un chat central, módulos operativos para facturas, caja chica y ventas, y un puente de WhatsApp para atención comercial asistida por IA.

El proyecto está pensado para correr en Vercel como frontend Vite + funciones serverless Python, con Airtable como base operacional, Upstash KV para estado conversacional y servicios de IA de OpenAI y Anthropic.

## Funcionalidades

- **Login multi-tenant**: autentica usuarios, emite JWT y habilita módulos según la empresa del usuario.
- **Chat Yoko**: asistente empresarial con soporte para dos backends:
  - `openai`: flujo legacy síncrono con tool calling.
  - `managed_agents`: flujo nuevo con Anthropic Managed Agents, sesiones persistentes, tasks async y polling desde frontend.
- **Facturas Inteligentes**:
  - carga de comprobantes PDF/archivos desde el chat o la pantalla del módulo;
  - procesamiento por lotes;
  - recuperación de procesos;
  - edición/revisión de facturas extraídas;
  - generación de registro contable en Excel según el sistema configurado.
- **Gestión de Caja Chica**:
  - dashboard, solicitudes, aprobaciones, pagos, rendiciones, reportes y configuración;
  - extracción conversacional de documentos de solicitud con `yoko_procesar_solicitud_caja`;
  - creación y consulta de solicitudes con tools conversacionales (`yoko_crear_solicitud`, `consultar_solicitud_por_id`, `consultar_solicitudes_por_dni`, `consultar_aprobador`).
- **Ventas Inteligentes**:
  - catálogo de productos;
  - conversaciones y mensajes;
  - modo IA/HUMAN por conversación;
  - configuración del agente comercial;
  - integración con WhatsApp.
- **Bot WhatsApp Baileys**:
  - servicio Node.js separado en `bot-service/`;
  - maneja sesiones por empresa;
  - persiste conversaciones en Airtable;
  - llama al cerebro de ventas en Vercel;
  - envía respuestas IA o mensajes humanos desde outbox.
- **Configuración por empresa**:
  - blobs JSON para `Config_Empresa` y `Config_Ventas`;
  - consulta bajo demanda de centros de costo;
  - invalidación de cache cuando cambia la configuración.
- **Skills versionables para agentes IA**:
  - system prompt principal;
  - skills de facturas, caja y rendiciones;
  - custom tools sincronizables con Anthropic Managed Agents y registrables en OpenAI/ChatGPT.

## Arquitectura

```text
Browser / React
  |
  | /api/*
  v
Vercel Serverless Python
  |
  +-- Airtable: tenants, usuarios, config, productos, conversaciones, mensajes
  +-- OpenAI: chat legacy, extracción, transcripción, ventas
  +-- Anthropic Managed Agents: chat persistente con custom tools
  +-- Upstash KV: sessions, tasks async y carrito de adjuntos
  |
  +-- bot-service Node.js
        |
        +-- Baileys / WhatsApp Web
        +-- Airtable polling: wa_sessions, outbox
```

### Frontend

- `src/App.jsx`: login, rutas protegidas y módulos habilitados por tenant.
- `src/features/chat/`: experiencia de chat, adjuntos, backend switch y polling async.
- `src/features/modules/`: pantallas de módulos.
- `src/shared/api.js`: cliente HTTP compartido con JWT y manejo de 401.

### Backend serverless

Vercel ve pocos entrypoints en `api/`; cada uno despacha internamente por query string para evitar exceder límites de funciones.

- `api/login.py`: autenticación y emisión de JWT.
- `api/chat.py`: dispatcher del chat Yoko.
- `api/facturas.py`: dispatcher de Facturas Inteligentes.
- `api/solicitudes.py`: dispatcher de tools conversacionales para solicitudes de caja.
- `api/ventas.py`: dispatcher de Ventas Inteligentes y WhatsApp/Meta.
- `api/config.py`: configuración por empresa y centros de costo.
- `api/transcribe.py`: transcripción de audio.
- `api/parse_file.py`: endpoint legacy y motor base de extracción por templates.

### Agente Yoko

- `api/_yoko/handler.py`: backend legacy con OpenAI tool calling.
- `api/_yoko/handler_managed.py`: backend Managed Agents, crea o reusa sesiones y encola tasks.
- `api/_yoko/handler_worker.py`: worker async que ejecuta el turno y custom tools.
- `api/_lib/yoko_*_store.py`: persistencia en KV para sessions, tasks, contexto y carrito.
- `api/_yoko_agents/`: definición y provisioning del agent Anthropic.
- `skills/`: prompts y skills versionables.

### Bot WhatsApp

`bot-service/` es un servicio aparte. No tiene IA propia: escucha WhatsApp con Baileys, persiste mensajes y llama al endpoint de ventas de Yoko.

Flujo resumido:

1. La UI pide vincular WhatsApp.
2. El bot detecta `wa_sessions.status = qr` en Airtable.
3. Baileys genera QR y el bot lo guarda.
4. La UI muestra el QR.
5. Mensajes entrantes se guardan en Airtable.
6. Si la conversación está en modo `AI`, el bot llama al cerebro de ventas.
7. Si está en modo `HUMAN`, espera respuestas desde el dashboard.

## Módulos disponibles

Los módulos se declaran en `src/features/modules/modulesConfig.js` y se habilitan por empresa desde el JWT.

- `ventas-inteligentes`
- `gestion-caja`
- `facturas-inteligentes`
- `configuracion-empresa`

Para agregar un módulo:

1. Crear `src/features/modules/<modulo>/`.
2. Agregar su registro en `modulesConfig.js`.
3. Conectar su componente en `MODULE_COMPONENTS` dentro de `src/App.jsx`.
4. Habilitar el id del módulo para la empresa en Airtable.

## Requisitos

- Node.js 20+
- Python 3.12+
- npm
- Cuenta de Airtable con la base configurada
- Proyecto Vercel
- OpenAI API key
- Anthropic API key si se usa `managed_agents`
- Upstash KV si se usa `managed_agents`

## Instalación local

```bash
npm install
```

Para el bot de WhatsApp:

```bash
cd bot-service
npm install
```

## Variables de entorno

Copiar `.env.example` a `.env.local` para desarrollo local del frontend/Vercel dev, y configurar las mismas variables en Vercel para producción.

Variables principales:

```bash
AIRTABLE_TOKEN=pat...
AIRTABLE_BASE_ID=app...
OPENAI_API_KEY=sk-...
JWT_SECRET=<secreto-de-32+-chars>

YOKO_BACKEND=openai
VITE_YOKO_BACKEND=openai
```

Para Anthropic Managed Agents:

```bash
ANTHROPIC_API_KEY=sk-ant-...
YOKO_AGENT_ID=agent_...
YOKO_ENVIRONMENT_ID=env_...
YOKO_VAULT_ID_CMEJIA=vlt_...
YOKO_MEMORY_STORE_ID_CMEJIA=mem_...
YOKO_SKILL_FACTURAS_ID=skill_...
YOKO_AGENT_TOOLS_ENABLED=false
YOKO_INTERNAL_TOKEN=<token-random>
KV_REST_API_URL=...
KV_REST_API_TOKEN=...
```

Para el bot WhatsApp, crear `bot-service/.env` con:

```bash
AIRTABLE_TOKEN=pat...
AIRTABLE_BASE_ID=app...
YOKO_BASE_URL=https://yokochat.vercel.app
LOG_LEVEL=silent
```

## Comandos

Frontend/app principal:

```bash
npm run dev
npm run vercel:dev
npm run build
npm run lint
npm run preview
```

Bot WhatsApp:

```bash
cd bot-service
npm run start
npm run dev
npm run typecheck
```

Python:

```bash
python -m compileall -q api scripts test_airtable.py
python scripts/sync_skills_to_anthropic.py
python scripts/test_config.py
python scripts/test_kv.py
```

## Desarrollo local

`vite.config.js` proxyea `/api` hacia `https://yokochat.vercel.app` durante `npm run dev`. Esto permite trabajar el frontend contra el backend remoto.

Si necesitas correr funciones serverless localmente, usa:

```bash
npm run vercel:dev
```

## Backend de chat

El backend se decide por request:

1. Header `X-Yoko-Backend`.
2. Env var `YOKO_BACKEND`.
3. Fallback `openai`.

El frontend permite alternar entre `openai` y `managed_agents`; la preferencia se guarda en `localStorage`.

### `openai`

- Mantiene historial completo desde frontend.
- Usa `api/_lib/openai_client.py`.
- Ejecuta tools locales vía registry.
- Guarda adjuntos en carrito KV cuando el módulo tiene tool conversacional de extracción.
- `parse_file` queda como endpoint legacy y motor base de extracción, no como flujo principal del chat.

### `managed_agents`

- Envía el último mensaje del usuario.
- Persiste historial en sessions de Anthropic.
- Guarda adjuntos en carrito KV.
- Encola una task y dispara `/api/chat?action=worker`.
- La UI consulta `/api/chat?action=status&task_id=...` hasta `done`, `error` o `expired`.

## Facturas Inteligentes

Endpoint consolidado:

```text
/api/facturas?action=procesar
/api/facturas?action=actualizar
/api/facturas?action=recuperar
/api/facturas?action=eliminar-fila
/api/facturas?action=concar
/api/facturas?action=procesar-chat
/api/facturas?action=recuperar-chat
/api/facturas?action=registro-contable-chat
```

El flujo chat usa marcadores especiales para que la UI pueda abrir revisión o descarga:

```text
[ABRIR_REVISION:<proceso_id>]
[DESCARGAR_REGISTRO:<proceso_id>]
```

## Ventas Inteligentes

Endpoint consolidado:

```text
/api/ventas?resource=wa
/api/ventas?resource=conversaciones
/api/ventas?resource=mensajes
/api/ventas?resource=conversaciones_modo
/api/ventas?resource=productos
/api/ventas?resource=prompt_preview
/api/ventas?resource=meta_status
/api/ventas?resource=sales_chat
/api/ventas?resource=whatsapp_webhook
```

La mayoría de recursos requiere JWT. `sales_chat` y `whatsapp_webhook` son server-to-server/public según el caso.

## Skills y provisioning del agent

Los skills viven en `skills/`. Para sincronizar cambios con Anthropic:

```bash
python scripts/sync_skills_to_anthropic.py
```

Custom tools actuales:

- `yoko_procesar_archivos`
- `yoko_generar_registro_contable`
- `yoko_recuperar_proceso`

El agent se define en `api/_yoko_agents/agent_definition.py` y se provisiona con los scripts de `scripts/`.

## Estado de calidad conocido

Última revisión local:

- `python -m compileall -q api scripts test_airtable.py`: OK.
- `cd bot-service && npm run typecheck`: OK.
- `npm run lint`: actualmente falla por reglas de lint/React Hooks y variables no usadas.
- `npm run build`: puede fallar en este entorno con Vite/Rolldown por emisión de `index.html` con ruta relativa extraña. Reproducir fuera del sandbox antes de concluir que es un bug de app.

## Seguridad y notas operativas

- `api/login.py` está en modo prueba y acepta una contraseña compartida temporal para empleados existentes. Antes de producción real, restaurar el flujo con tabla `Usuarios` y bcrypt.
- No commitear `.env`, `.env.local` ni secretos. Ya están cubiertos por `.gitignore`.
- `JWT_SECRET` debe tener al menos 32 caracteres.
- Los endpoints protegidos deben resolver `empresa_id` desde el JWT, no desde el body.
- Mantener `YOKO_BACKEND` y `VITE_YOKO_BACKEND` alineados para evitar flujos mixtos de adjuntos.

## Deploy

`vercel.json` configura:

- build con `npm run build`;
- salida `dist`;
- rewrites `/api/*`;
- duración máxima de funciones críticas como `api/chat.py` y `api/facturas.py`.

Para producción:

1. Configurar variables de entorno en Vercel.
2. Verificar login, chat, facturas y ventas en Preview.
3. Si se habilita Managed Agents, correr la checklist de `docs/tests_e2e_yoko_managed.md`.
4. Promover a Production.
5. Monitorear logs de Vercel, Airtable y el servicio WhatsApp.

## Estructura del repo

```text
api/                 Funciones serverless Python y librerías backend
bot-service/         Servicio Node.js/Baileys para WhatsApp
docs/                Checklists y documentación operativa
public/              PWA, service worker, íconos y assets públicos
scripts/             Scripts de testing, provisioning y sincronización
skills/              Skills y prompts del agent Yoko
src/                 Frontend React
```
