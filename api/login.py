"""
api/login.py
Serverless function (Python): valida DNI consultando directamente
la tabla Empleados en Airtable. Las credenciales nunca llegan al browser.

A futuro: aquí mismo se puede agregar lógica con Anthropic SDK.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
import urllib.error


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            dni    = str(body.get("dni", "")).strip()

            # Validación básica
            if not dni.isdigit() or len(dni) != 8:
                return self._json(400, {"error": "DNI inválido. Debe tener 8 dígitos."})

            token   = os.environ.get("AIRTABLE_TOKEN")
            base_id = os.environ.get("AIRTABLE_BASE_ID")
            table   = os.environ.get("AIRTABLE_TABLE", "Empleados")

            if not token or not base_id:
                return self._json(500, {"error": "Configuración del servidor incompleta."})

            # Construcción de la URL con filtro por DNI
            formula = urllib.parse.quote(f"{{DNI}}='{dni}'")
            url = (
                f"https://api.airtable.com/v0/{base_id}"
                f"/{urllib.parse.quote(table)}"
                f"?filterByFormula={formula}&maxRecords=1"
            )

            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {token}"}
            )

            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read())

            records = data.get("records", [])

            if not records:
                # DNI no encontrado en la tabla Empleados
                return self._json(200, {"authorized": False})

            # Campos reales de la tabla: "NOMBRE CORTO", "PUESTO", "DNI"
            fields = records[0].get("fields", {})

            return self._json(200, {
                "authorized": True,
                "nombre": fields.get("NOMBRE CORTO", ""),
                "cargo":  fields.get("PUESTO", ""),
                "dni":    dni,
            })

        except urllib.error.HTTPError as e:
            print(f"[login] Error Airtable HTTP {e.code}: {e.read()}")
            return self._json(502, {"error": f"Error al consultar la base de datos (HTTP {e.code})."})

        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido en el cuerpo de la solicitud."})

        except Exception as e:
            print(f"[login] Error inesperado: {e}")
            return self._json(500, {"error": "Error interno del servidor."})

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silenciar logs de acceso HTTP
