"""A11 — every observation hour paints its own photograph.

The owner's wallpapers were processed into the package (1920×1080 WebP, 90%
lighter than the sources). Painting must never decode on the fly: the scaled
pixmap is cached per hour and size, and a missing asset falls back to the
original gradient instead of breaking the page.
"""

import pytest
from PySide6.QtCore import QSize

from oms_ui.pages import synoptic as page_module

HOURS = ("00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z")

#: A background may not exceed this; the eight together must stay light.
MAX_BYTES = 200 * 1024


@pytest.mark.parametrize("hora", HOURS)
def test_every_hour_has_an_asset(hora):
    path = page_module.HOUR_BACKGROUNDS[hora]
    assert path.exists(), f"falta el fondo de {hora}"
    assert path.suffix == ".webp"


def test_the_eight_backgrounds_stay_light():
    total = sum(page_module.HOUR_BACKGROUNDS[h].stat().st_size for h in HOURS)
    assert total < 900 * 1024, f"los fondos pesan {total / 1024:.0f} KB"
    for hora in HOURS:
        assert page_module.HOUR_BACKGROUNDS[hora].stat().st_size < MAX_BYTES, hora


def test_the_photo_covers_the_requested_size(qtbot):
    pixmap = page_module.hour_background("12Z", QSize(400, 300))
    assert pixmap is not None
    assert pixmap.size() == QSize(400, 300)


def test_the_scaled_pixmap_is_cached(qtbot):
    page_module._BACKGROUND_CACHE.clear()
    first = page_module.hour_background("06Z", QSize(320, 240))
    second = page_module.hour_background("06Z", QSize(320, 240))
    assert first is second  # same object: no second decode
    assert len(page_module._BACKGROUND_CACHE) == 1


def test_each_size_gets_its_own_entry(qtbot):
    page_module._BACKGROUND_CACHE.clear()
    page_module.hour_background("21Z", QSize(200, 150))
    page_module.hour_background("21Z", QSize(300, 200))
    assert len(page_module._BACKGROUND_CACHE) == 2


def test_an_unknown_hour_returns_none(qtbot):
    assert page_module.hour_background("07Z", QSize(100, 100)) is None


def test_a_missing_file_falls_back_to_the_gradient(qtbot, monkeypatch, tmp_path):
    monkeypatch.setitem(page_module.HOUR_BACKGROUNDS, "09Z", tmp_path / "no-existe.webp")
    assert page_module.hour_background("09Z", QSize(120, 90)) is None
