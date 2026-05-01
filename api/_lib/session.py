"""
Helpers de sesión: extraer y validar los datos del usuario que vienen
en el body de la request del chat (capa 3 del system prompt).

El frontend envía el objeto `user` con dni y opcionalmente nombre, cargo,
email, celular (ver src/features/auth/useAuth.js).

Si email o celular no llegan en el body, los enriquecemos con un lookup
a la tabla `Empleados` por DNI. Esto evita tener que tocar `api/login.py`
mientras el frontend se actualiza para enviar todos los campos.
"""

import sys

from . import airtable_client
from .airtable_client import AirtableError


# Mapeo del nombre del campo en Airtable → clave en el dict de sesión.
_EMPLEADO_FIELDS_MAP: dict[str, str] = {
    "NOMBRE CORTO": "nombre",
    "PUESTO":       "cargo",
    "EMAIL":        "email",
    "CELULAR":      "celular",
}


def _fetch_empleado_by_dni(dni: str) -> dict[str, str]:
    """
    Busca al empleado en la tabla `Empleados` por DNI y devuelve un dict
    con claves `{nombre, cargo, email, celular}`. Si la tabla falla o
    no encuentra al empleado, devuelve dict vacío (degradación suave).
    """
    try:
        records = airtable_client.list_records(
            "Empleados",
            filter_formula=f"{{DNI}}='{dni}'",
            max_records=1,
        )
    except AirtableError as e:
        print(
            f"[session] No se pudo enriquecer al usuario {dni} desde Empleados: {e}",
            file=sys.stderr,
        )
        return {}

    if not records:
        return {}

    fields = records[0].get("fields", {}) or {}
    return {
        local_key: str(fields.get(remote_key, "") or "").strip()
        for remote_key, local_key in _EMPLEADO_FIELDS_MAP.items()
    }


def extract_user(body: dict) -> dict:
    """
    Extrae { dni, nombre, cargo, email, celular } del body.

    Reglas:
      - DNI es obligatorio. Si falta, lanza ValueError.
      - nombre, cargo, email, celular son opcionales en el body. Si alguno
        viene vacío, se intenta completarlo con un lookup a Empleados.
      - Si el lookup también falla, los campos vacíos quedan como "".
    """
    if not isinstance(body, dict):
        raise ValueError("El body debe ser un objeto JSON.")

    user = body.get("user")
    if not isinstance(user, dict):
        raise ValueError("Falta el objeto 'user' en el body.")

    dni = user.get("dni")
    if not dni or not str(dni).strip():
        raise ValueError("Falta 'user.dni' en el body.")

    dni = str(dni).strip()

    result = {
        "dni":     dni,
        "nombre":  str(user.get("nombre", "")).strip(),
        "cargo":   str(user.get("cargo", "")).strip(),
        "email":   str(user.get("email", "")).strip(),
        "celular": str(user.get("celular", "")).strip(),
    }

    # Si falta cualquiera de los campos enriquecibles, hacemos UNA sola
    # consulta a Empleados y rellenamos lo que esté vacío.
    needs_lookup = not all(
        result[k] for k in ("nombre", "cargo", "email", "celular")
    )
    if needs_lookup:
        empleado = _fetch_empleado_by_dni(dni)
        for key, value in empleado.items():
            if not result[key] and value:
                result[key] = value

    return result
