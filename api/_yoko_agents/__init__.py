"""
api/_yoko_agents/

Definición declarativa del agent "yoko-empresarial" en Anthropic Managed
Agents y el script idempotente que lo provisiona/actualiza.

Submódulos:
  agent_definition.py   construye el dict de config (name, model, system,
                        tools, skills) leyendo desde el repo.
  provision_agent.py    script ejecutable: crea o actualiza el agent en
                        platform.claude.com a partir de agent_definition.
  tools/                JSON Schemas de los custom tools que el agent puede
                        invocar (procesar_archivos, generar_excel, recuperar_proceso).

Las llamadas HTTP a Anthropic viven en `api/_lib/managed_agents_client.py`.
"""
