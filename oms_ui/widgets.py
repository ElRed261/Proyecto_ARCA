"""Shared widgets that need behaviour plain Qt does not give us.

``StyledComboBox`` exists because a QComboBox popup is built from Qt's
private container — a top-level QFrame the stylesheet selectors cannot
reach — and, being a child of the combo, it inherits the combo's
``selection-background-color`` QSS rule. The result was the dark band the
owner kept seeing along the popup's top and bottom edges plus the harsh
default blue highlight. The container only becomes reachable once the
popup is live, so the styling happens in ``showPopup``.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QComboBox, QFrame

#: object name the popup container gets so its rule only targets the popup.
POPUP_OBJECT_NAME = "omsComboPopup"

#: the flat, light surface the popup shares with the rest of the app.
POPUP_CONTAINER_QSS = (
    f"QFrame#{POPUP_OBJECT_NAME} {{ background-color: $superficie;"
    " border: 1px solid $borde; border-radius: 10px; }"
    # the paging scroller Qt adds for long lists is a child widget; without
    # this it keeps the style's grey band at the bottom of the popup.
    f"QFrame#{POPUP_OBJECT_NAME} QWidget {{ background-color: $superficie; }}"
)

def _qss(plantilla: str) -> str:
    """Resuelve una plantilla QSS con la paleta del tema aplicado (S1)."""
    from string import Template

    from oms_ui import theme as _theme

    return Template(plantilla).substitute(_theme.palette_actual())

_SURFACE = "$superficie"
_INK = "$texto_alt"
_SELECTION = "$borde"


class StyledComboBox(QComboBox):
    """A combo whose popup matches the app's flat, light surface."""

    def showPopup(self) -> None:
        super().showPopup()
        container = self.view().window()
        container.setObjectName(POPUP_OBJECT_NAME)
        container.setStyleSheet(_qss(POPUP_CONTAINER_QSS))
        if isinstance(container, QFrame):
            # the container is a QFrame: drop the style's own frame so no
            # second border paints outside ours
            container.setFrameShape(QFrame.Shape.NoFrame)
        view = self.view()
        palette = view.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(_SURFACE))
        palette.setColor(QPalette.ColorRole.Text, QColor(_INK))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(_SELECTION))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(_INK))
        view.setPalette(palette)
        view.viewport().setPalette(palette)
        view.viewport().update()


__all__ = ["POPUP_CONTAINER_QSS", "POPUP_OBJECT_NAME", "StyledComboBox"]
