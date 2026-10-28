"""LoginWindow — compact login window for Neo Arca (redesign round 2).

Small fixed-size window (~440px) with the card directly on a light backdrop,
following OLD/IMG/Login.png: lockup, gradient primary button, offline footer
note. Presentation-only: auth arrives as an injectable
``login_func(email, password)`` callable. API preserved from LoginScreen
(result_session, authenticated signal, attempt_login, error_label,
login_button, email_edit/password_edit) so existing tests keep passing.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from oms_core.services.auth import LoginResult


class LoginWindow(QWidget):
    """Compact login window. Emits :attr:`authenticated` on success."""

    authenticated = Signal(object)

    def __init__(self, login_func: Callable[[str, str], LoginResult], parent=None) -> None:
        super().__init__(parent)
        self._login_func = login_func
        self.result_session: LoginResult | None = None
        self._busy = False

        self.setWindowTitle("Neo Arca — Acceso al sistema")
        self.setFixedWidth(440)
        self.setStyleSheet("LoginWindow { background-color: #eef2f7; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.addWidget(self._build_card())

    # -- construction ----------------------------------------------------

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("loginCard")
        card.setStyleSheet(
            "#loginCard { background-color: #ffffff; border-radius: 12px; "
            "border: 1px solid #e2e8f0; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(0)

        lockup = QLabel("Neo Arca")
        lockup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lockup.setStyleSheet(
            "font-size: 24px; font-weight: 800; color: #0f172a; background: transparent;"
        )
        layout.addWidget(lockup)

        subtitle = QLabel("OBSERVATIONS MANAGEMENT SYSTEM (OMS)")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            "font-size: 11px; font-weight: 600; "
            "color: #64748b; background: transparent; margin-top: 4px;"
        )
        layout.addWidget(subtitle)

        tagline = QLabel("Acceso al OMS — Observations Management System")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            "font-size: 12px; color: #64748b; background: transparent; margin-top: 6px;"
        )
        layout.addWidget(tagline)
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

        self.login_button = QPushButton("→  Iniciar Sesión")
        self.login_button.setProperty("primary", True)
        self.login_button.setDefault(True)
        self.login_button.setMinimumHeight(44)
        layout.addWidget(self.login_button)

        footer = QLabel("Modo Local — Autenticación Offline")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            "font-size: 11px; color: #94a3b8; background: transparent; margin-top: 14px;"
        )
        layout.addWidget(footer)

        self.email_edit.returnPressed.connect(self.attempt_login)
        self.password_edit.returnPressed.connect(self.attempt_login)
        self.login_button.clicked.connect(self.attempt_login)
        return card

    # -- behavior (unchanged contract) ------------------------------------

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
            self.login_button.setText("→  Iniciar Sesión")
        self.authenticated.emit(self.result_session)
