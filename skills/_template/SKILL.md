---
name: <nombre-del-skill>
description: Una línea que explique CUÁNDO activar este skill. El agent decide invocarlo basándose en este texto, así que sé específico con keywords y casos de uso. Ejemplo "Procesa órdenes de compra internas con flujo de aprobación. Activa cuando el usuario menciona 'OC', 'orden de compra', 'aprobación de compra' o adjunta una requisición. NO actives para facturas ni para caja chica."
---

# <nombre-del-skill> — <Título descriptivo>

<Resumen de 1-2 líneas de qué hace este skill.>

---

## Cuándo activarte

- <Trigger 1: el usuario menciona X palabras clave>
- <Trigger 2: el usuario adjunta archivo en contexto Y>
- <Trigger 3: el usuario hace pregunta tipo Z>

## Cuándo NO activarte

- <Anti-trigger: solapa con otro skill>
- <Anti-trigger: tema fuera de scope>

---

## Flujo conversacional

1. **Recolección**: <qué inputs necesitás del usuario>
2. **Confirmación**: <qué validás antes de actuar>
3. **Ejecución**: <qué tool llamás>
4. **Entrega**: <cómo respondés con el resultado>

No fuerces el orden lineal: si el usuario salta o retrocede, adaptate.

---

## Las N intenciones del usuario que reconocés

(Una sección por cada intención, con ejemplos del lenguaje natural en el que
se manifiesta y cómo responder.)

### 1. <Nombre de la intención>

**Cómo se manifiesta**: <descripción + ejemplos de frases reales>

**Cómo respondés**: <qué hacés + plantilla de respuesta si aplica>

**Reglas**:
- <regla 1>
- <regla 2>

---

## Manejo de ambigüedad

Cuando el mensaje no encaja claramente en ninguna intención, NO inventes.
Pregunta de forma directa y breve. Una pregunta a la vez.

| Mensaje | Por qué es ambiguo | Tu pregunta |
|---------|--------------------|-------------|
| ... | ... | ... |

---

## Casos especiales

### <Caso 1>

<Cómo manejarlo>

---

## Tono y estilo

- Idioma: español peruano profesional, conversacional.
- Sin preámbulos, sin disculpas innecesarias.
- Variá los verbos de confirmación para no sonar robótico.
- Emojis funcionales solo cuando aporten claridad.

---

## Custom tools que invocás

- `yoko_xxx`: <qué hace + parámetros principales>

NO llames otros tools. NO ejecutes lógica de negocio vos mismo — eso vive
en el backend.

---

## Notas finales

- NO inventes datos. Si el backend devuelve campo vacío, repórtalo vacío.
- Mantené el contexto cross-channel cuando aplique.
- Ante la duda, pregunta breve. Pero si el contexto es claro, actúa.
