"""
crear_usuario.py — genera un bcrypt hash para crear usuarios manualmente
en la tabla `Usuarios` de Airtable.

NO toca Airtable. Solo lee email + password de la consola, valida los
inputs, hashea el password con bcrypt cost=12 y lo imprime para que vos
lo copies a la columna `password_hash` del registro nuevo.

Uso:
    python scripts/crear_usuario.py

Cómo funciona la creación end-to-end de un usuario:

  1. Crear la fila en Airtable manualmente (tabla `Usuarios`):
       email, nombre, empresa_id, activo=true
  2. Correr este script para generar el password_hash.
  3. Copiar el hash a la columna `password_hash` del registro recién creado.

Requiere que `bcrypt` esté instalado (lo está en el venv del backend
después de `pip install -e .`).
"""

from __future__ import annotations

import getpass
import re
import sys

import bcrypt


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_BCRYPT_COST = 12
_MIN_PASSWORD_LEN = 8


def main() -> int:
    print("─" * 60)
    print(" Generador de hash bcrypt para usuarios de Yoko AI")
    print("─" * 60)

    email = input("Email del usuario: ").strip().lower()
    if not _EMAIL_RE.match(email):
        print("[!] Email inválido.", file=sys.stderr)
        return 1

    password = getpass.getpass("Password (no se mostrará): ")
    if len(password) < _MIN_PASSWORD_LEN:
        print(
            f"[!] Password muy corta (mínimo {_MIN_PASSWORD_LEN} caracteres).",
            file=sys.stderr,
        )
        return 1

    confirm = getpass.getpass("Confirmar password: ")
    if password != confirm:
        print("[!] Los passwords no coinciden.", file=sys.stderr)
        return 1

    # Generar hash. bcrypt.hashpw devuelve bytes; lo decodificamos a str
    # para que sea pasteable directo en Airtable (el campo es Long Text).
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_COST))
    hashed_str = hashed.decode("utf-8")

    print()
    print("─" * 60)
    print(" Hash generado — copialo a Airtable")
    print("─" * 60)
    print(f"Email:          {email}")
    print(f"password_hash:  {hashed_str}")
    print()
    print("Próximo paso: ir a la tabla `Usuarios` en Airtable y completar")
    print("o actualizar el registro con estos campos:")
    print(f"  • email          = {email}")
    print(f"  • password_hash  = (el string de arriba)")
    print(f"  • nombre         = (nombre real del usuario)")
    print(f"  • empresa_id     = (cmejia | demo | <nuevo slug>)")
    print(f"  • activo         = true")
    print("─" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
