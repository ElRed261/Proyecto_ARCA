"""Fase 1 del sistema de diseño: tokens, estados y tema conmutable.

docs/DISENO_OMS.md §2 y §4. Estas pruebas son barreras de regresión: la hoja
no puede volver a llevar colores literales, el tema oscuro no puede quedarse a
medio sustituir y un control deshabilitado no puede verse igual que uno
editable (defecto UI-02 de docs/AUDITORIA_JD.md).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from oms_ui import theme

QSS = Path(theme.__file__).with_name("theme.qss")


class _SettingsFalso:
    """QSettings en memoria: los tests no tocan la configuración del usuario."""

    def __init__(self) -> None:
        self.datos: dict[str, object] = {}

    def value(self, clave: str, defecto=None):
        return self.datos.get(clave, defecto)

    def setValue(self, clave: str, valor) -> None:  # noqa: N802 - API de Qt
        self.datos[clave] = valor


@pytest.fixture
def settings_falso(monkeypatch):
    falso = _SettingsFalso()
    monkeypatch.setattr(theme, "_settings", lambda: falso)
    return falso


# ---------------------------------------------------------------- tokens


def test_la_plantilla_no_tiene_colores_literales():
    plantilla = QSS.read_text(encoding="utf-8")

    literales = re.findall(r"#[0-9a-fA-F]{3,8}", plantilla)

    assert literales == [], f"colores fuera de PALETTE: {literales[:5]}"


def test_cada_tema_renderiza_sin_tokens_pendientes():
    for nombre in theme.THEMES:
        css = theme.load_stylesheet(nombre)
        assert len(css) > 1000, nombre
        assert "$" not in css, f"token sin sustituir en {nombre}"


def test_el_claro_conserva_los_colores_que_hoy_se_ven():
    """La fase 1 tokeniza sin cambiar la apariencia (docs/DISENO_OMS.md §1)."""
    css = theme.load_stylesheet("claro")

    for valor in ("#f3f4f6", "#ffffff", "#e2e8f0", "#2563eb", "#1e293b"):
        assert valor in css, valor


def test_el_oscuro_usa_su_propia_paleta():
    claro = theme.load_stylesheet("claro")
    oscuro = theme.load_stylesheet("oscuro")

    assert "#0b1220" in oscuro
    assert "#0b1220" not in claro
    assert claro != oscuro


def test_un_rol_sin_paleta_falla_ruidosamente(monkeypatch, tmp_path):
    plantilla = tmp_path / "theme.qss"
    plantilla.write_text("QWidget { color: $rol_que_no_existe; }", encoding="utf-8")
    monkeypatch.setattr(theme, "_QSS_FILE", plantilla)

    with pytest.raises(ValueError):
        theme.load_stylesheet("claro")


# ---------------------------------------------------------------- estados


def test_el_deshabilitado_no_se_ve_igual_que_el_editable():
    """UI-02: el observador tiene que distinguir la celda bloqueada."""
    css = theme.load_stylesheet("claro")
    claro = theme.PALETTE_CLARO

    assert "QLineEdit:disabled" in css
    assert claro["tenue"] != claro["texto"]

    bloque = css.split("QLineEdit:disabled")[1].split("}")[0]
    assert claro["tenue"] in bloque
    assert claro["texto"] not in bloque


def test_el_boton_tiene_foco_visible():
    """WCAG 2.4.7: en una app de Tab-Enter se tiene que ver dónde está el foco."""
    css = theme.load_stylesheet("claro")

    assert "QPushButton:focus" in css
    bloque = css.split("QPushButton:focus")[1].split("}")[0]
    assert theme.PALETTE_CLARO["acento_foco"] in bloque


def test_los_estados_no_usan_propiedades_que_qt_ignora():
    """`opacity` y `outline` no existen en Qt: se descartan en silencio."""
    css = theme.load_stylesheet("claro")

    assert "opacity:" not in css
    assert "outline:" not in css


# ---------------------------------------------------------------- tema


def test_normalize_theme_acepta_alias_y_descarta_basura():
    assert theme.normalize_theme("oscuro") == "oscuro"
    assert theme.normalize_theme("dark") == "oscuro"
    assert theme.normalize_theme("light") == "claro"
    assert theme.normalize_theme("") == "claro"
    assert theme.normalize_theme(None) == "claro"
    assert theme.normalize_theme("typo-que-no-existe") == "claro"


def test_el_tema_elegido_persiste(settings_falso):
    assert theme.current_theme() == "claro"

    assert theme.set_theme("oscuro") == "oscuro"

    assert theme.current_theme() == "oscuro"
    assert settings_falso.datos["apariencia/tema"] == "oscuro"


def test_set_theme_con_basura_guarda_el_de_fabrica(settings_falso):
    assert theme.set_theme("no-existe") == "claro"
    assert theme.current_theme() == "claro"


def test_apply_theme_aplica_el_tema_pedido(qtbot):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    theme.apply_theme(app, "oscuro")
    assert theme.PALETTE_OSCURO["fondo"] in app.styleSheet()

    theme.apply_theme(app, "claro")
    assert theme.PALETTE_CLARO["fondo"] in app.styleSheet()


# ---------------------------------------------------------------- conmutador


def test_el_conmutador_de_configuracion_cambia_el_tema(fresh_db, settings_falso):
    """Fase 1b: el combo de Apariencia persiste y reaplica en caliente."""
    from PySide6.QtWidgets import QApplication

    from oms_ui.pages.maintenance import MaintenancePage

    app = QApplication.instance()
    theme.set_theme("claro")
    theme.apply_theme(app, "claro")
    page = MaintenancePage(fresh_db, role="admin")

    assert page.theme_combo.count() == len(theme.THEMES)
    indice = page.theme_combo.findData("oscuro")
    assert indice >= 0

    page.theme_combo.setCurrentIndex(indice)

    assert theme.current_theme() == "oscuro"
    assert theme.PALETTE_OSCURO["fondo"] in app.styleSheet()
    assert "Oscuro" in page.theme_label.text()

    theme.set_theme("claro")
    theme.apply_theme(app, "claro")


def test_el_conmutador_esta_para_todos_los_roles(fresh_db, settings_falso):
    """El tema es del usuario, no del administrador: no se bloquea por rol."""
    from oms_ui.pages.maintenance import MaintenancePage

    page = MaintenancePage(fresh_db, role="observador")

    assert page.theme_combo.isEnabled()
