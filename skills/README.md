# `skills/` — capacidades versionables del agent Yoko

Esta carpeta declara las capacidades del agent Anthropic Managed Agent
"yoko-empresarial" definido en [api/_yoko_agents/](../api/_yoko_agents/).
Cada cambio acá se sincroniza al agent corriendo en `platform.claude.com`
con `python scripts/sync_skills_to_anthropic.py`.

## Layout

```
skills/
├── _system_prompts/
│   └── yoko-empresarial.md     System prompt principal del agent
├── _template/
│   └── SKILL.md                Template para skills nuevos
├── yoko-facturas/
│   └── SKILL.md                Skill activo: procesamiento de comprobantes
└── README.md                   Este archivo
```

## Convenciones

- Subcarpetas con prefijo `_` son metadata (no son skills).
- Cada skill vive en su propia subcarpeta `<nombre>/SKILL.md`.
- El nombre de la subcarpeta es el `name` del skill registrado en Anthropic.
- `SKILL.md` empieza con frontmatter YAML mínimo:
  ```yaml
  ---
  name: <nombre>
  description: <una línea — cuándo activar>
  ---
  ```

## Sincronización con Anthropic

El agent existe del lado Anthropic con un `id` (env `YOKO_AGENT_ID`).
Para empujar cambios al agent después de editar archivos en esta carpeta:

```bash
python scripts/sync_skills_to_anthropic.py
```

Es idempotente: si nada cambió respecto al estado remoto, es no-op.

## Cómo agregar un skill nuevo

1. Copiar `_template/SKILL.md` a `skills/<nombre>/SKILL.md`.
2. Editar frontmatter (`name: <nombre>`, `description: ...`).
3. Escribir el cuerpo (cuándo activar, cuándo no, flujo conversacional).
4. Si el skill necesita custom tools, definirlos en
   [api/_yoko_agents/tools/](../api/_yoko_agents/tools/) con la constante
   `TOOL_DEFINITION` y agregarlos a `tools/__init__.py::ALL_TOOLS`.
5. Correr `python scripts/sync_skills_to_anthropic.py` para subirlo.

## Custom tools registrados hoy

Definidos en [api/_yoko_agents/tools/](../api/_yoko_agents/tools/):

- `yoko_procesar_archivos` — lote de comprobantes → datos extraídos.
- `yoko_generar_excel` — proceso validado → Excel CONCAR.
- `yoko_recuperar_proceso` — estado de un proceso por id.

Los tools NO se ejecutan en el sandbox de Anthropic. Cuando el agent dispara
un `tool_use`, el orquestador (`api/_yoko/handler_managed.py`) lo intercepta
y hace HTTP a la API Yoko en Vercel.
