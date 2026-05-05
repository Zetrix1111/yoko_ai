"""
api/transcribe.py
Proxy a OpenAI Audio Transcriptions. Recibe el audio como bytes crudos
(Content-Type: audio/webm o similar) y devuelve { "text": "..." }.

Modelo por defecto: gpt-4o-mini-transcribe (precio ~$0.003/min, buena
precisión en español). Alternativas:
    - "whisper-1"            (clásico, $0.006/min)
    - "gpt-4o-transcribe"    (máxima precisión, ~$0.006/min)
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import urllib.request
import urllib.error
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth                 # noqa: E402
from _lib.auth import AuthError       # noqa: E402


OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"
MODEL      = "gpt-4o-mini-transcribe"
LANGUAGE   = "es"


def build_multipart(audio_bytes: bytes, content_type: str):
    """Arma un body multipart/form-data sin dependencias externas."""
    # Determina extensión según content-type que mandó el navegador
    ext = "webm"
    if   "mp4"  in content_type: ext = "mp4"
    elif "mpeg" in content_type or "mp3" in content_type: ext = "mp3"
    elif "wav"  in content_type: ext = "wav"
    elif "m4a"  in content_type: ext = "m4a"
    elif "ogg"  in content_type: ext = "ogg"

    boundary = f"----yokochat{uuid.uuid4().hex}"
    delim    = f"--{boundary}".encode()
    crlf     = b"\r\n"

    parts = []

    # Campo: file
    parts.append(delim + crlf)
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="audio.{ext}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'.encode()
    )
    parts.append(audio_bytes + crlf)

    # Campo: model
    parts.append(delim + crlf)
    parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    parts.append(MODEL.encode() + crlf)

    # Campo: language (hint para mejor precisión)
    parts.append(delim + crlf)
    parts.append(b'Content-Disposition: form-data; name="language"\r\n\r\n')
    parts.append(LANGUAGE.encode() + crlf)

    # Cierre
    parts.append(f"--{boundary}--\r\n".encode())

    return b"".join(parts), boundary


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            try:
                auth.require_auth(self.headers)
            except AuthError as e:
                return self._json(e.status, {"error": str(e)})

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return self._json(500, {"error": "OPENAI_API_KEY no configurado en el servidor."})

            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return self._json(400, {"error": "No se recibió audio."})

            audio_bytes  = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "audio/webm")

            body, boundary = build_multipart(audio_bytes, content_type)

            req = urllib.request.Request(
                OPENAI_URL,
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  f"multipart/form-data; boundary={boundary}",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=28) as res:
                raw = res.read()

            data = json.loads(raw)
            return self._json(200, {"text": data.get("text", "")})

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[transcribe] OpenAI HTTP {e.code}: {err_body}")
            return self._json(502, {"error": f"Error transcribiendo (HTTP {e.code})."})

        except Exception as e:
            print(f"[transcribe] Error: {e}")
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
