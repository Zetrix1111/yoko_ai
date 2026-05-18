# `skills/` — prompts y skills de Yoko

Esta carpeta contiene el prompt raíz compartido de Yoko y los skills de dominio que guían flujos especializados.

## Layout

```text
skills/
├── _system_prompts/
│   └── yoko-empresarial.md       System prompt compartido para Anthropic y OpenAI
├── facturas-inteligentes/
│   └── SKILL.md                  Procesamiento de comprobantes y registros contables
├── solicitud-caja/
│   └── SKILL.md                  Solicitudes de caja chica / entrega a rendir
├── rendicion-caja/
│   └── SKILL.md                  Rendición y cuadre de fondos
└── README.md
```

## Prompt raíz compartido

`skills/_system_prompts/yoko-empresarial.md` es el system prompt común para los runtimes de IA de Yoko.

Debe funcionar tanto para:

- Anthropic Managed Agents.
- OpenAI / ChatGPT / Agents SDK.

El prompt raíz define:

- identidad de Yoko;
- reglas multi-tenant;
- formato de `<contexto_empresa>`;
- routing hacia skills;
- reglas para herramientas disponibles o ausentes;
- marcadores de UI;
- estilo y seguridad.

Las reglas de negocio detalladas viven en los skills de dominio. No duplicar esos flujos en el prompt raíz.

Este prompt raíz no incluye arquitectura técnica de frontend/backend ni el flujo de WhatsApp/Ventas. Esos temas viven fuera de estos skills: WhatsApp pertenece al cerebro de ventas (`_ventas`) y no forma parte de `facturas-inteligentes`, `solicitud-caja` ni `rendicion-caja`.

## Estrategia de contexto

Yoko debe usar contexto por capas para no cargar información innecesaria en cada conversación.

### 1. Contexto liviano al iniciar sesión

Al iniciar una conversación o crear una sesión nueva, inyectar solo lo necesario para identificar la empresa y enrutar:

```text
<contexto_empresa>
Empresa: [Razón social] (empresa_id: [id])
RUC: [11 dígitos]
Usuario: [nombre] ([cargo/rol si está disponible])
Módulos activos: facturas-inteligentes, gestion-caja, ...
Sistema contable: CONCAR | SISCONT | otro
</contexto_empresa>
```

Este contexto inicial NO debe contener toda la configuración detallada de caja, aprobadores, centros de costo, topes o reglas por módulo.

### 2. Contexto detallado bajo demanda

Cuando el router activa un skill, el runtime debe cargar el contexto detallado de ese módulo, por ejemplo:

```text
<contexto_modulo nombre="gestion-caja">
usuario_area: ...
usuario_rol_operativo: ...
requiere_aprobacion: ...
num_aprobadores: ...
monto_maximo_activo: ...
monto_maximo: ...
seguimiento_ia: ...
</contexto_modulo>
```

No cargar listas grandes como aprobadores o centros de costo en memoria.
Los skills deben consultar esos catálogos bajo demanda mediante tools.

Para `facturas-inteligentes`, el contexto detallado puede incluir sistema contable, límites de lote, formatos soportados y plantillas disponibles.

### 3. No crear skills de configuración por ahora

La configuración no debe modelarse como un skill conversacional separado. Debe ser un **context provider** o herramienta de soporte para los skills de negocio.

Nombres sugeridos para implementación futura:

- `get_empresa_context`
- `get_modulo_context`
- `consultar_centros_costo`
- `get_aprobadores`

Los skills deben asumir:

- contexto liviano al inicio;
- contexto detallado solo cuando el flujo lo necesita;
- si falta contexto detallado, deben pedir lo mínimo o llamar una herramienta de contexto si existe;
- nunca deben inventar reglas de configuración.

## Skills de dominio

- `facturas-inteligentes`: procesa comprobantes de pago peruanos y genera registros contables.
- `solicitud-caja`: crea y consulta solicitudes de fondos de caja chica.
- `rendicion-caja`: procesa comprobantes de rendición, cuadra fondos y registra rendiciones.

## Convenciones

- Las carpetas con prefijo `_` son prompts raíz o metadata; no son skills de dominio.
- Cada skill operativo vive en `skills/<nombre>/SKILL.md`.
- Cada `SKILL.md` debe empezar con frontmatter YAML mínimo:

```yaml
---
name: <nombre>
description: <cuándo debe activarse>
---
```

## Uso recomendado en Anthropic

El provisioning del agent lee el prompt desde:

```text
skills/_system_prompts/yoko-empresarial.md
```

Los skills remotos y custom tools se sincronizan con:

```bash
python scripts/sync_skills_to_anthropic.py
```

Los custom tools de Anthropic están definidos en `api/_yoko_agents/tools/`.
Para OpenAI legacy, las tools equivalentes se registran en `api/_yoko/_lib/tools/`.

Tools alineadas con los skills actuales:

- `facturas-inteligentes`: `yoko_procesar_archivos`, `yoko_recuperar_proceso`, `yoko_generar_registro_contable`.
- `solicitud-caja`: `yoko_procesar_solicitud_caja`, `yoko_crear_solicitud`, `consultar_solicitud_por_id`, `consultar_solicitudes_por_dni`, `consultar_aprobador`, `consultar_centros_costo`.

## Uso recomendado en OpenAI / ChatGPT

Para crear el agente en ChatGPT o Agents SDK:

1. Usa `skills/_system_prompts/yoko-empresarial.md` como instrucciones principales.
2. Carga como conocimiento o instrucciones complementarias:
   - `skills/facturas-inteligentes/SKILL.md`
   - `skills/solicitud-caja/SKILL.md`
   - `skills/rendicion-caja/SKILL.md`
3. Si el agente tendrá acciones conectadas al sistema Yoko, mapea las acciones a los nombres de herramientas descritos en cada skill.
4. Si el agente no tendrá acciones, debe recopilar y validar información, pero no afirmar que registró, procesó o generó archivos reales.
