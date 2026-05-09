"""
scripts/upload_skill.py

Sube un skill custom (carpeta con SKILL.md y archivos auxiliares) a la
Skills API de Anthropic e imprime el `skill_id` resultante.

Uso:
    python scripts/upload_skill.py skills/yoko-facturas

Salida (ejemplo):
    OK skill subido
       skill_id:       skill_01ABC...
       latest_version: 1759178010641129
       display_title:  yoko-facturas

    Pegá esto en Vercel:
       YOKO_SKILL_FACTURAS_ID=skill_01ABC...

Re-correrlo con la MISMA carpeta crea una NUEVA versión del skill (no duplica).
La API distingue por `display_title`: si ya existe un skill con ese título, se
suma una versión; si no, se crea uno nuevo.

Pre-requisitos:
  - ANTHROPIC_API_KEY en env
  - La carpeta debe contener un SKILL.md con frontmatter YAML válido (name,
    description) — la API lo valida.
  - Total de archivos < 30 MB.

Headers requeridos por la API:
  x-api-key:        ANTHROPIC_API_KEY
  anthropic-version: 2023-06-01
  anthropic-beta:    skills-2025-10-02   ← NOTAR: distinto al managed-agents-2026-04-01.
"""

import argparse
import io
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path


_API_URL_BASE = "https://api.anthropic.com"
_BETA_HEADER = "skills-2025-10-02"
_API_VERSION = "2023-06-01"
_MAX_TOTAL_BYTES = 30 * 1024 * 1024  # 30 MB hard limit de la API


def _build_multipart(
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, bytes, str]],
) -> tuple[bytes, str]:
    """
    Construye un body multipart/form-data manual (sin requests).
    `fields`: [(name, value), ...]
    `files`:  [(name, filename, content_bytes, content_type), ...]
    Devuelve (body_bytes, content_type_header).
    """
    boundary = f"----yoko-{uuid.uuid4().hex}"
    buf = io.BytesIO()
    for name, value in fields:
        buf.write(f"--{boundary}\r\n".encode("utf-8"))
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        buf.write(value.encode("utf-8"))
        buf.write(b"\r\n")
    for name, filename, content, ctype in files:
        buf.write(f"--{boundary}\r\n".encode("utf-8"))
        # filename incluye la ruta relativa con la carpeta raíz del skill.
        buf.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        buf.write(f"Content-Type: {ctype}\r\n\r\n".encode("utf-8"))
        buf.write(content)
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode("utf-8"))
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def _collect_skill_files(skill_dir: Path) -> list[tuple[str, bytes, str]]:
    """
    Recorre `skill_dir` y devuelve [(filename_with_root, content, ctype), ...].
    `filename_with_root` queda como "<skill_dir.name>/<rel_path>" — la API
    requiere que todos los archivos compartan una raíz común.
    """
    if not (skill_dir / "SKILL.md").exists():
        raise FileNotFoundError(
            f"{skill_dir}/SKILL.md no existe. Un skill custom requiere "
            "SKILL.md con frontmatter YAML (name, description)."
        )

    root = skill_dir.name
    out: list[tuple[str, bytes, str]] = []
    total = 0
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        # Saltar archivos ocultos/sistema.
        if p.name.startswith(".") or p.name.endswith(".pyc"):
            continue
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(skill_dir).as_posix()
        filename_with_root = f"{root}/{rel}"
        content = p.read_bytes()
        total += len(content)
        if total > _MAX_TOTAL_BYTES:
            raise ValueError(
                f"El skill excede 30 MB ({total / 1_048_576:.1f} MB). "
                "Reducí el contenido antes de subir."
            )
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        out.append((filename_with_root, content, ctype))

    if not out:
        raise FileNotFoundError(f"{skill_dir} no tiene archivos para subir.")
    return out


def upload_skill(skill_dir: Path, display_title: str | None = None) -> dict:
    """
    Sube el skill al endpoint POST /v1/skills (multipart). Devuelve el dict de
    respuesta con `id`, `display_title`, `latest_version`, etc.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Falta ANTHROPIC_API_KEY en el entorno.")

    files = _collect_skill_files(skill_dir)
    title = (display_title or skill_dir.name).strip()
    if not title:
        raise ValueError("display_title vacío; pasá --title o renombrá la carpeta.")

    multipart_files: list[tuple[str, str, bytes, str]] = [
        ("files[]", filename, content, ctype) for (filename, content, ctype) in files
    ]
    body, content_type = _build_multipart(
        fields=[("display_title", title)],
        files=multipart_files,
    )

    req = urllib.request.Request(
        f"{_API_URL_BASE}/v1/skills",
        data=body,
        method="POST",
    )
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", _API_VERSION)
    req.add_header("anthropic-beta", _BETA_HEADER)
    req.add_header("Content-Type", content_type)
    req.add_header("Content-Length", str(len(body)))

    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(
            f"HTTP {e.code} subiendo skill: {err_body[:500]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Error de red subiendo skill: {e}") from e


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "skill_dir",
        help="Carpeta del skill (debe contener SKILL.md). Ej: skills/yoko-facturas",
    )
    parser.add_argument(
        "--title",
        help="display_title del skill. Default: nombre de la carpeta.",
    )
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        print(f"X La carpeta {skill_dir} no existe.", file=sys.stderr)
        return 1

    print(f"→ Subiendo skill desde {skill_dir}")
    files = _collect_skill_files(skill_dir)
    print(f"  {len(files)} archivo(s):")
    for filename, content, _ctype in files:
        print(f"    - {filename} ({len(content)} bytes)")
    print()

    try:
        res = upload_skill(skill_dir, display_title=args.title)
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        print(f"X {e}", file=sys.stderr)
        return 1

    sid = res.get("id")
    print("OK skill subido")
    print(f"   skill_id:       {sid}")
    print(f"   latest_version: {res.get('latest_version')}")
    print(f"   display_title:  {res.get('display_title')}")
    print()

    # Sugerir la env var según el nombre de la carpeta.
    suffix = skill_dir.name.replace("yoko-", "").replace("-", "_").upper()
    env_var = f"YOKO_SKILL_{suffix}_ID"
    print("Pegá esto en Vercel (Production + Preview):")
    print(f"   {env_var}={sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
