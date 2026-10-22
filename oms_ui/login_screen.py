"""LoginScreen — full-screen login for Neo Arca (PRD F7.5).

Mirrors the OLD AuthPage: dark background, centered white card with lockup,
inline error (no popups) and a loading button state. Presentation-only: the
auth call arrives as an injectable ``login_func(email, password)`` callable,
exactly like LoginDialog (which stays intact — tests depend on it).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from oms_core.services.auth import LoginResult


class LoginScreen(QWidget):
    """Full-screen login. Emits :attr:`authenticated` on success."""

    authenticated = Signal(object)

    def __init__(self, login_func: Callable[[str, str], LoginResult], parent=None) -> None:
        super().__init__(parent)
        self._login_func = login_func
        self.result_session: LoginResult | None = None
        self._busy = False

        self.setWindowTitle("Neo Arca — Acceso al sistema")
        self.setStyleSheet("LoginScreen { background-color: #111827; }")

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        center = QHBoxLayout()
        center.addStretch(1)
        center.addWidget(self._build_card())
        center.addStretch(1)
        outer.addLayout(center)
        outer.addStretch(1)

    # -- construction ----------------------------------------------------

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(400)
        card.setStyleSheet(
            "#loginCard { background-color: #ffffff; border-radius: 12px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(0)

        lockup = QLabel("Neo Arca")
        lockup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lockup.setStyleSheet(
            "font-size: 24px; font-weight: 800; color: #0f172a; background: transparent;"
        )
        layout.addWidget(lockup)

        subtitle = QLabel("OMS · ACCESO AL SISTEMA")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "font-size: 11px; font-weight: 600; letter-spacing: 2px; "
            "color: #64748b; background: transparent; margin-top: 4px;"
        )
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        email_label = QLabel("Correo Electrónico")
        email_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #334155; background: transparent;"
        )
        layout.addWidget(email_label)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("usuario@arca.rd")
        layout.addWidget(self.email_edit)
        layout.addSpacing(12)

        password_label = QLabel("Contraseña")
        password_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #334155; background: transparent;"
        )
        layout.addWidget(password_label)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("••••••••")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)
        layout.addSpacing(8)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            "font-size: 12px; color: #b91c1c; background: transparent;"
        )
        layout.addWidget(self.error_label)
        layout.addSpacing(8)

        self.login_button = QPushButton("Entrar")
        self.login_button.setProperty("primary", True)
        self.login_button.setDefault(True)
        layout.addWidget(self.login_button)

        self.email_edit.returnPressed.connect(self.attempt_login)
        self.password_edit.returnPressed.connect(self.attempt_login)
        self.login_button.clicked.connect(self.attempt_login)
        return card

    # -- behavior --------------------------------------------------------

    @property
    def email(self) -> str:
        return self.email_edit.text().strip()

    @property
    def password(self) -> str:
        return self.password_edit.text()

    def attempt_login(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.login_button.setEnabled(False)
        self.login_button.setText("Procesando...")
        try:
            self.result_session = self._login_func(self.email, self.password)
        except Exception as exc:  # noqa: BLE001 - auth.AuthError and backend failures show inline
            self.result_session = None
            self.error_label.setText(str(exc))
            return
        finally:
            self._busy = False
            self.login_button.setEnabled(True)
            self.login_button.setText("Entrar")
        self.authenticated.emit(self.result_session)
