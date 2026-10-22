"""oms_ui.icons — the renderer must paint the colour it is asked for.

Round 13 found every icon rendering in SVG's default black: the
``currentColor`` substitution ran on the inner body instead of the SVG
header that actually carries the ``stroke`` attribute. These tests pin the
fix and the registry contract.
"""

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from PySide6.QtCore import QSize

from oms_ui.icons import lucide_icon


def test_icon_paints_the_requested_colour(qtbot):
    pixmap = lucide_icon("file-warning", "#94a3b8", 48).pixmap(QSize(48, 48))
    image = pixmap.toImage()
    counts: dict[str, int] = {}
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 200:
                counts[colour.name()] = counts.get(colour.name(), 0) + 1
    assert counts, "the icon rendered nothing"
    assert max(counts, key=counts.get) == "#94a3b8"


def test_unknown_icon_is_a_lookup_error(qtbot):
    with pytest.raises(LookupError):
        lucide_icon("not-a-lucide-icon", "#000000", 16)
