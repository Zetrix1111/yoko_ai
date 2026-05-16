# 🚀 Plan detallado para Claude Code — Activar jw_seguridad en WhatsApp Meta Cloud API

> **Repo:** `Zetrix1111/yoko_ai`
> **Branch:** `main`
> **Fecha:** 2026-05-12

---

## Contexto

| Campo | Valor |
|---|---|
| Tenant | `jw_seguridad` |
| WABA ID | `1143877237749374` |
| phone_number_id | `1065219666676086` |
| Número público | `+51 926 994 469` |
| Canal | Solo Meta Cloud API (sin Baileys, sin coexistencia) |
| Scope MVP | Solo texto entrante. Salida puede llevar fotos del catálogo. |
| Graph API objetivo | `v23.0` |

**Pre-requisitos cumplidos por el usuario:**

- ✅ Env vars en Vercel (`META_WEBHOOK_VERIFY_TOKEN`, `META_APP_SECRET`, `OPENAI_API_KEY`, `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`)
- ✅ Webhook registrado en Meta App Dashboard
- ✅ Registro en Airtable `meta_connections` con `activo=TRUE`
- ✅ Config en `Config_Empresa.ventas` ya cargada
- ✅ Productos cargados en tabla `productos` con `empresa_id=jw_seguridad`
- ✅ El número NO está usado por bot-baileys (cutover limpio a Meta)

**Definition of Done:**
Un mensaje de WhatsApp enviado al `+51 926 994 469` recorre todo el flujo, queda persistido en `conversaciones` + `mensajes` con `empresa_id=jw_seguridad`, y el cliente recibe respuesta del cerebro de ventas.

---

## Tarea 1 — Upgrade Graph API v18 → v23

**Archivo:** `api/_lib/whatsapp_meta_client.py`

**Cambios:**

- Línea 20 (docstring): reemplazar `v18.0` por `v23.0`
- Línea 33:
  ```python
  # Antes:
  _BASE_URL = "https://graph.facebook.com/v18.0"
  # Después:
  _BASE_URL = "https://graph.facebook.com/v23.0"
  ```

**Verificación:**

```bash
grep -n "v1[0-9]\.0\|v2[0-9]\.0" api/_lib/whatsapp_meta_client.py
```

Solo debe aparecer `v23.0` (2 ocurrencias: docstring + constante).

---

## Tarea 2 — Localizar fallback message al español peruano

**Archivo:** `api/_ventas/meta_webhook.py` (líneas 44-47)

El texto actual usa voseo argentino. Cambiar:

```python
_FALLBACK_REPLY = (
    "Disculpa, estoy con un problema técnico en este momento. "
    "Por favor, escríbeme de nuevo en unos minutos."
)
```

Cambio puntual: `escribime` → `escríbeme`.

**Verificación:**

```bash
grep -n "escribime\|escríbeme" api/_ventas/meta_webhook.py
```

Solo debe aparecer `escríbeme`.

---

## Tarea 3 — Dedup in-memory de mensajes por `wamid`

**Problema:** si Vercel responde tarde el 200 OK (cold start), Meta reintenta y el cerebro procesa el mismo mensaje 2 veces, generando respuestas duplicadas.

**Solución MVP:** cache in-memory de los últimos N `wamid`. Persiste mientras la lambda esté caliente (suficiente para cubrir la ventana de reintentos de Meta, que es de segundos).

**Archivo:** `api/_ventas/meta_webhook.py`

**a) Después de los imports** (después de la línea `from _ventas import chat as ventas_chat`), agregar:

```python
from collections import deque

# Dedup in-memory de wamid. Sobrevive mientras la lambda esté caliente.
# Cold start lo resetea, pero Meta reintenta solo en ventanas cortas (segundos).
_PROCESSED_WAMIDS: deque = deque(maxlen=500)
_PROCESSED_SET: set = set()
```

**b) En `_handle_message()`**, después de calcular `from_phone` y `text_body`, **antes** de la llamada a `_ensure_conversation`, agregar:

```python
wamid = (msg.get("id") or "").strip()
if wamid:
    if wamid in _PROCESSED_SET:
        print(f"[meta_webhook] wamid duplicado, skip: {wamid}", file=sys.stderr)
        return
    if len(_PROCESSED_WAMIDS) == _PROCESSED_WAMIDS.maxlen:
        _PROCESSED_SET.discard(_PROCESSED_WAMIDS[0])
    _PROCESSED_WAMIDS.append(wamid)
    _PROCESSED_SET.add(wamid)
```

---

## Tarea 4 — Skip silencioso de eventos `statuses`

**Problema:** Meta envía por el mismo webhook eventos de delivery/read/error en `value.statuses[]`. No son input del usuario y contaminan los logs.

**Archivo:** `api/_ventas/meta_webhook.py`

En `_process_change()`, justo antes del lookup `meta_connections.get_by_phone_number_id`, agregar:

```python
# Meta envía 'statuses' (delivery/read/error) por el mismo webhook.
# No son input del usuario — skip silencioso para no contaminar logs.
if value.get("statuses") and not value.get("messages"):
    return
```

---

## Tarea 5 — Endpoint `meta_status` para validar conexión

**Objetivo:** que el dashboard pueda preguntar "¿está activa la conexión Meta de esta empresa?" sin hardcodear lógica de validación. También actualiza `estado_token` en Airtable.

**Archivo nuevo:** `api/_ventas/meta_status.py`

```python
"""
api/_ventas/meta_status.py — verificar estado de conexión Meta del tenant.

GET /api/ventas?resource=meta_status (JWT requerido)

Lee meta_connections, hace ping a /v23.0/me con el access_token,
actualiza estado_token en Airtable y devuelve resumen.
"""

import json
import sys
import urllib.error
import urllib.request

from _lib import meta_connections, airtable_client
from _lib.airtable_client import AirtableError


_TABLA = "meta_connections"


def meta_status_get(req, empresa_id: str) -> None:
    conn = meta_connections.get_by_empresa_id(empresa_id)
    if not conn:
        return req._json(404, {"connected": False, "reason": "no_record"})

    token = conn.get("access_token")
    if not token:
        return req._json(200, {"connected": False, "reason": "no_token"})

    url = f"https://graph.facebook.com/v23.0/me?access_token={token}"
    estado_token = "error"
    ok = False
    detail = ""
    try:
        with urllib.request.urlopen(url, timeout=10) as res:
            body = json.loads(res.read())
        estado_token = "activo"
        ok = True
        detail = body.get("id", "")
    except urllib.error.HTTPError as e:
        estado_token = "expirado" if e.code == 401 else "error"
        detail = f"HTTP {e.code}"
    except Exception as e:
        print(f"[meta_status] {type(e).__name__}: {e}", file=sys.stderr)
        detail = str(e)

    # Persistir estado en Airtable e invalidar cache.
    try:
        airtable_client.update_record(
            _TABLA, conn["id"], {"estado_token": estado_token},
        )
        meta_connections.invalidate_cache(empresa_id)
    except AirtableError as e:
        print(
            f"[meta_status] no se pudo actualizar estado_token: {e}",
            file=sys.stderr,
        )

    return req._json(200, {
        "connected":     ok,
        "estado_token":  estado_token,
        "phone_display": conn.get("phone_display"),
        "waba_id":       conn.get("waba_id"),
        "detail":        detail,
    })
```

**Registrar en `api/ventas.py`:**

**a) Import** (línea 45) — agregar `meta_status` al import:

```python
from _ventas import wa, conversaciones, chat as ventas_chat, prompt_preview, productos, meta_webhook, meta_status  # noqa: E402
```

**b) En `_DISPATCH_AUTH`** agregar:

```python
("meta_status", "GET"): meta_status.meta_status_get,
```

**c) En el docstring del header del archivo** (~línea 24), agregar la línea:

```
  GET    ?resource=meta_status          → estado conexión Meta + ping a Graph
```

---

## Tarea 6 — Smoke test local

**Objetivo:** validar offline que toda la cadena (Airtable → Graph API → cerebro) funciona, antes de exponer el número real al público.

**Archivo nuevo:** `scripts/smoke_meta_jw.py`

```python
"""
Smoke test end-to-end para jw_seguridad SIN tocar Meta real.
Valida en orden: env vars → meta_connections → token Meta vivo → cerebro responde.

Uso:
  cd <repo_root>
  source .env       # o exportar OPENAI_API_KEY, AIRTABLE_TOKEN, AIRTABLE_BASE_ID
  python scripts/smoke_meta_jw.py
"""

import json
import os
import sys
import urllib.request
import urllib.error

# Path setup (mismo patrón que ventas.py)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))

from _lib import meta_connections           # noqa: E402
from _ventas import chat as ventas_chat     # noqa: E402


EMPRESA_ID = "jw_seguridad"


def step(n, msg):
    print(f"\n[{n}] {msg}")


def ok(msg):
    print(f"  ✅ {msg}")


def fail(msg):
    print(f"  ❌ {msg}")
    sys.exit(1)


def main():
    # 1. Variables de entorno
    step(1, "Verificando env vars")
    for v in ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID"):
        if not os.environ.get(v):
            fail(f"falta env var: {v}")
    ok("env vars presentes")

    # 2. Airtable: meta_connections activo
    step(2, f"Leyendo meta_connections para {EMPRESA_ID}")
    conn = meta_connections.get_by_empresa_id(EMPRESA_ID)
    if not conn:
        fail("no hay registro activo en meta_connections")
    ok(f"phone_number_id={conn['phone_number_id']} waba_id={conn['waba_id']}")

    # 3. Token Meta válido (ping a /me)
    step(3, "Pinging Graph API /me con access_token")
    url = f"https://graph.facebook.com/v23.0/me?access_token={conn['access_token']}"
    try:
        with urllib.request.urlopen(url, timeout=10) as res:
            data = json.loads(res.read())
        ok(f"Graph OK, id={data.get('id')}")
    except urllib.error.HTTPError as e:
        body = e.read()[:200].decode("utf-8", "ignore")
        fail(f"Graph HTTP {e.code}: {body}")
    except Exception as e:
        fail(f"Graph error: {type(e).__name__}: {e}")

    # 4. Cerebro responde con texto coherente
    step(4, "Invocando process_message del cerebro de ventas")
    try:
        result = ventas_chat.process_message(
            empresa_id=EMPRESA_ID,
            phone="51999000111",   # número de prueba
            nombre="Smoke Test",
            history=[{"role": "user", "content": "Hola, qué venden?"}],
        )
    except Exception as e:
        fail(f"process_message exception: {type(e).__name__}: {e}")

    reply = result.get("reply", "")
    if not reply:
        fail("reply vacío")
    ok(f"reply ({len(reply)} chars): {reply[:120]}…")

    print("\n🎉 SMOKE OK — todo conectado y listo para mensaje real.")


if __name__ == "__main__":
    main()
```

**Verificación:**

```bash
python scripts/smoke_meta_jw.py
```

Los 4 pasos deben aparecer en verde. Si falla en paso 3, el token está vencido. Si falla en paso 4, hay un problema con la config de la empresa o productos.

---

## Tarea 7 — Validar suscripción del webhook en Meta (manual)

En **Meta App Dashboard → WhatsApp → Configuration**:

1. Confirmar que el **Webhook URL** apunta a:
   `https://<vercel-domain>/api/ventas?resource=whatsapp_webhook`
2. En **Webhook fields**, verificar que `messages` esté **suscrito** (check verde).
3. Si la suscripción está perdida, click en "Manage" → suscribirse al campo `messages`.

> ⚠️ El campo `message_template_status_update` y otros NO son necesarios para el MVP de texto entrante.

---

## Tarea 8 — Commit + push

```bash
git add api/_lib/whatsapp_meta_client.py \
        api/_ventas/meta_webhook.py \
        api/_ventas/meta_status.py \
        api/ventas.py \
        scripts/smoke_meta_jw.py

git commit -m "feat(meta): activar jw_seguridad — upgrade v23, dedup wamid, status endpoint

- whatsapp_meta_client: Graph API v18 -> v23
- meta_webhook: dedup in-memory por wamid (evita doble proceso en reintentos)
- meta_webhook: skip silencioso de events statuses (delivery/read receipts)
- meta_webhook: localiza fallback al español peruano
- _ventas/meta_status: nuevo endpoint GET para validar conexión + ping /me
- ventas: routea meta_status como JWT-protected
- scripts/smoke_meta_jw: validación end-to-end offline (Airtable + Graph + cerebro)"

git push origin main
```

---

## Tarea 9 — Test real con `+51 926 994 469`

Después del deploy de Vercel (~30s):

1. **Smoke offline**:
   ```bash
   python scripts/smoke_meta_jw.py
   ```
   Esperado: los 4 pasos verdes.

2. **Status endpoint** (con JWT de jw_seguridad):
   ```bash
   curl -H "Authorization: Bearer <JWT>" \
        "https://<vercel-domain>/api/ventas?resource=meta_status"
   ```
   Esperado: `{"connected": true, "estado_token": "activo", ...}`

3. **Mensaje real**: desde otro WhatsApp, enviar al `+51 926 994 469`:
   > "Hola, qué chalecos manejan?"

4. **Verificar en orden:**

   | Punto | Esperado |
   |---|---|
   | Vercel logs | `[meta_webhook]` log al recibir el POST, sin errores HMAC |
   | Airtable `conversaciones` | Nuevo record con `empresa_id=jw_seguridad`, `modo=AI`, `phone` correcto |
   | Airtable `mensajes` | 2 filas (`role=user` + `role=assistant`) ligadas a la conversación |
   | WhatsApp del cliente | Respuesta del cerebro: nombra a la asesora correcta, tono peruano, sin números de stock exactos |

---

## Rollback rápido

- **Vercel UI**: promover el deployment anterior (rollback en 1 click, sin git revert).
- **Airtable**: setear `meta_connections.activo=FALSE` para jw_seguridad → el webhook ignora silenciosamente los mensajes de ese WABA sin afectar a otros tenants.
- **Git**: `git revert HEAD && git push origin main` si necesitas revertir el código permanentemente.

---

## Resumen de archivos tocados

| Archivo | Acción |
|---|---|
| `api/_lib/whatsapp_meta_client.py` | Editar (v18 → v23) |
| `api/_ventas/meta_webhook.py` | Editar (dedup, statuses skip, fallback es-PE) |
| `api/_ventas/meta_status.py` | **Crear** |
| `api/ventas.py` | Editar (import + dispatch + docstring) |
| `scripts/smoke_meta_jw.py` | **Crear** |

**Total:** 3 ediciones + 2 archivos nuevos. Sin cambios en `prompt.py`, `tools.py`, ni `chat.py` (el cerebro ya está listo).

---

## Notas operativas

- **`media_urls` sigue activo**: el cerebro puede mandar fotos de productos (chalecos, cascos) si el catálogo las tiene. Esto NO contradice el "solo texto" del usuario, que se refería a entrada (no procesar imágenes/audios que envíe el cliente).
- **Cold start**: el primer mensaje del día puede tardar ~3-5s. Si es un problema, considerar `vercel.json` con `maxDuration` ya en 30s — suficiente.
- **Ventana de 24h de Meta**: como NO usamos HSM, solo podemos responder cuando el cliente escribe primero. Si el cerebro intenta iniciar conversación pasadas 24h, Meta rechaza con error 131047. Por ahora aceptable (MVP reactivo).
- **Costo Meta**: en Perú, las conversaciones de "service" (iniciadas por el cliente) tienen un cupo gratuito mensual. Validar consumo en Meta Business Manager → WhatsApp → Insights → Conversations.
