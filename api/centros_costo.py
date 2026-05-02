"""
api/centros_costo.py
Devuelve la lista de centros de costo (campo OBRA) desde la tabla
"obras" en Airtable. Se consume desde Configuración de empresa.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Permitir importar desde api/_lib/ aunque la función serverless se ejecute
# con un cwd diferente al repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client
from _lib.airtable_client import AirtableError


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            records = airtable_client.list_records("obras", max_records=7)

            centros = []
            for r in records:
                f = r.get("fields", {})
                obra = f.get("OBRA")
                if not obra:
                    continue
                centros.append({
                    "id": f.get("ID") or r.get("id"),
                    "obra": obra,
                    "nombre": f.get("NOMBRE OBRA", ""),
                    "constituyen": f.get("CONSTITUYEN", ""),
                })

            return self._json(200, {"centros": centros})

        except AirtableError as e:
            print(f"[centros_costo] AirtableError: {e}")
            return self._json(502, {"error": "No se pudo consultar Airtable."})
        except Exception as e:
            print(f"[centros_costo] Error: {e}")
            return self._json(500, {"error": "Error interno del servidor."})

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
