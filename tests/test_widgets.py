"""Shared widgets — the QComboBox popup surface.

Round 14: the owner reported a dark band along the top and bottom edges of
every opened list. Cause: Qt builds the popup from a private container
QFrame the stylesheet cannot reach, and the combo's own
``selection-background-color`` rule cascaded into the list. These tests pin
the fixed surface: no dark band, and none of the theme's hardcoded blue
selection.
"""

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from oms_ui.theme import apply_theme
from oms_ui.widgets import POPUP_OBJECT_NAME, StyledComboBox


def _popup_image(combo):
    combo.showPopup()
    window = combo.view().window()
    return window, window.grab().toImage()


@pytest.fixture()
def combo(qtbot, qapp):
    apply_theme(qapp)
    widget = StyledComboBox()
    widget.addItems(["Monte Cristi", "La Romana", "Catey", "MDJB"])
    widget.resize(260, 36)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_popup_edges_are_not_a_dark_band(combo, qtbot):
    _window, image = _popup_image(combo)
    try:
        assert image.width() > 0 and image.height() > 0
        rows = (0, 1, image.height() - 2, image.height() - 1)
        for y in rows:
            for x in range(2, image.width() - 2, 6):
                lightness = image.pixelColor(x, y).lightness()
                assert lightness > 200, (x, y, image.pixelColor(x, y).name())
    finally:
        combo.hidePopup()


def test_popup_container_is_the_styled_frame(combo, qtbot):
    window, _image = _popup_image(combo)
    try:
        assert window.objectName() == POPUP_OBJECT_NAME
    finally:
        combo.hidePopup()


def test_popup_selection_is_not_the_theme_blue(combo, qtbot):
    _window, image = _popup_image(combo)
    try:
        seen = {
            image.pixelColor(x, y).name()
            for y in range(image.height())
            for x in range(0, image.width(), 3)
        }
        assert "#bfdbfe" not in seen  # the QLineEdit/QComboBox rule leaked here
    finally:
        combo.hidePopup()
