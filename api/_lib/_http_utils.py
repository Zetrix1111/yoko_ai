"""
api/_lib/_http_utils.py

Helpers compartidos por los clientes HTTP de _lib (airtable_client,
kv_client, managed_agents_client). Centralizan dos patrones que vivían
duplicados en los 3 archivos:

  1. Lectura de env var obligatoria con error semántico del cliente.
  2. Lectura defensiva del body de un urllib HTTPError.

El objetivo es que cada cliente HTTP delegue acá la fontanería repetida,
preservando su contrato de errores: cada cliente sigue levantando su
propia clase (AirtableError, KVError, ManagedAgentsError) — `require_env`
recibe la clase como parámetro para no acoplar este módulo a ninguna.

El nombre con underscore inicial (`_http_utils.py`) sigue la convención
del paquete `_lib/` (módulos privados, no parte de una API pública).
"""

import os
import urllib.error


def require_env(name: str, exc_class: type[Exception]) -> str:
    """
    Lee una env var obligatoria. Si está vacía o ausente, levanta
    `exc_class` con un mensaje uniforme.

    Cada cliente HTTP pasa su propia clase de excepción para mantener
    su contrato de errores hacia el caller (tests y código de aplicación
    siguen pudiendo `except AirtableError:` sin sorpresas).
    """
    val = os.environ.get(name)
    if not val:
        raise exc_class(f"Falta {name} en las variables de entorno.")
    return val


def read_http_error_body(e: urllib.error.HTTPError) -> str:
    """
    Lee el body de un urllib HTTPError de forma defensiva. Si el socket
    ya está cerrado, el encoding falla, o cualquier otro problema, devuelve
    string vacío en vez de propagar el fallo secundario y enmascarar el
    error HTTP original.

    Reemplaza el patrón
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
    que vivía idéntico en los 3 clientes.
    """
    try:
        return e.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
