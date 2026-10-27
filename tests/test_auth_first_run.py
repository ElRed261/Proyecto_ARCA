"""S3: una instalación nueva queda usable y sin credenciales en el repositorio.

Judgment Day SEG-01 (`docs/AUDITORIA_JD.md`): `seed_admin` no lo llamaba nadie
y el único camino que creaba un usuario era `run_dev.py`, con la contraseña
admin escrita en el repositorio e impresa a stdout.
"""

from __future__ import annotations

import stat
from pathlib import Path

from oms_core.services import auth

RAIZ = Path(__file__).resolve().parents[1]


def test_seed_admin_siembra_los_cuatro_usuarios(fresh_db, tmp_path):
    credenciales = auth.seed_admin(fresh_db, tmp_path)

    assert credenciales is not None
    assert set(credenciales) == {email for email, _ in auth._SEED_USERS}


def test_seed_admin_deja_una_instalacion_usable(fresh_db, tmp_path):
    """La prueba que faltaba: con lo sembrado se puede entrar."""
    credenciales = auth.seed_admin(fresh_db, tmp_path)
    admin = next(email for email, role in auth._SEED_USERS if role == "admin")

    result = auth.login(fresh_db, auth.SessionStore(), admin, credenciales[admin])

    assert result.role == "admin"
    assert result.user_email == admin


def test_el_archivo_de_credenciales_es_privado(fresh_db, tmp_path):
    auth.seed_admin(fresh_db, tmp_path)
    archivo = tmp_path / "primer_inicio.txt"

    modo = stat.S_IMODE(archivo.stat().st_mode)

    assert modo == 0o600, f"permisos {oct(modo)}: cualquiera puede leer las contraseñas"


def test_seed_admin_es_idempotente(fresh_db, tmp_path):
    auth.seed_admin(fresh_db, tmp_path)

    assert auth.seed_admin(fresh_db, tmp_path) is None


def test_el_repositorio_no_guarda_la_contrasena_dev():
    """Barrera de regresión: la credencial publicada no puede volver."""
    run_dev = (RAIZ / "run_dev.py").read_text(encoding="utf-8")

    assert "ArcaDev123" not in run_dev
