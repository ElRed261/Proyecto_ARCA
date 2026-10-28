"""S10: el login sale de la paleta, no de hojas inline."""

from __future__ import annotations

import re
from pathlib import Path

from oms_ui import theme

_SRC = Path(__file__).resolve().parents[1] / "oms_ui" / "login_window.py"


def _fuente() -> str:
    return _SRC.read_text(encoding="utf-8")


def test_el_login_no_tiene_colores_literales():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", _fuente())
    assert "setStyleSheet" not in _fuente()


def test_cada_objectname_del_login_tiene_su_regla():
    nombres = set(re.findall(r'setObjectName\("([^"]+)"\)', _fuente()))
    assert nombres
    for tema in theme.THEMES:
        hoja = theme.load_stylesheet(tema)
        faltan = sorted(n for n in nombres if f"#{n}" not in hoja)
        assert not faltan, f"{tema}: sin regla para {faltan}"


def test_el_error_marca_y_desmarca_los_campos(qtbot):
    from oms_ui.login_window import LoginWindow

    def falla(_correo, _clave):
        raise RuntimeError("Credenciales inválidas")

    ventana = LoginWindow(login_func=falla)
    qtbot.addWidget(ventana)

    ventana.attempt_login()
    assert "Credenciales inválidas" in ventana.error_label.text()
    assert ventana.error_label.property("error") == "true"
    assert ventana.email_edit.property("error") == "true"

    ventana._login_func = lambda _correo, _clave: None
    ventana.attempt_login()
    assert ventana.error_label.text() == ""
    assert ventana.error_label.property("error") == "false"
    assert ventana.email_edit.property("error") == "false"
