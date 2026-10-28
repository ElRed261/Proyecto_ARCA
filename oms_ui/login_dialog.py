"""LoginDialog — first window of Neo Arca (PRD F3).

Email + password with an INLINE error label (no popups), wired to the
oms_core auth service through an injectable ``login_func(email, password)``
callable so the dialog stays presentation-only.
"""

from __future__ import annotations


def _qss(plantilla: str) -> str:
    """Resuelve una plantilla QSS con la paleta del tema aplicado (S1)."""
    from string import Template

    from oms_ui import theme as _theme

    return Template(plantilla).substitute(_theme.palette_actual())





from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from oms_core.services.auth import LoginResult


class LoginDialog(QDialog):
    """Modal login. On success the login result is in :attr:`result_session`."""

    def __init__(self, login_func: Callable[[str, str], LoginResult], parent=None) -> None:
        super().__init__(parent)
        self._login_func = login_func
        self.result_session: LoginResult | None = None

        self.setWindowTitle("Neo Arca — Inicio de sesión")
        self.setModal(True)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("usuario@arca.rd")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(_qss("color: $error_fuerte;"))
        self.error_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Email:", self.email_edit)
        form.addRow("Contraseña:", self.password_edit)

        self.login_button = QPushButton("Entrar")
        self.login_button.setDefault(True)
        self.cancel_button = QPushButton("Cancelar")

        buttons = QVBoxLayout()
        buttons.addWidget(self.login_button)
        buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        self.login_button.clicked.connect(self.attempt_login)
        self.cancel_button.clicked.connect(self.reject)
        # Enter in either field tries the login (no popups, inline error only).
        self.password_edit.returnPressed.connect(self.attempt_login)
        self.email_edit.returnPressed.connect(self.attempt_login)

    @property
    def email(self) -> str:
        return self.email_edit.text().strip()

    @property
    def password(self) -> str:
        return self.password_edit.text()

    def attempt_login(self) -> None:
        try:
            self.result_session = self._login_func(self.email, self.password)
        except Exception as exc:  # noqa: BLE001 - auth.AuthError and any backend failure
            self.result_session = None
            self.error_label.setText(str(exc))
            return
        self.accept()
