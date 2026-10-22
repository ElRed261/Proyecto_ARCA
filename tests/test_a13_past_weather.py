"""A13 — past weather (W1 W2) computed from the manual's hour windows.

Regla 12.2.6.6.1: six-hour windows at 00/06/12/18 and three-hour windows at
03/09/15/21. The figures come from the phenomena marked in the CLI 3074 (the
machine-readable past weather), with the cloud cover of the current hour as
the fallback; nothing observable yields ``//`` (the manual's ``7ww//``).
"""

from oms_core.services import past_weather as pw


def test_a_six_hour_window_covers_three_observations():
    assert pw.window_hours("12Z") == ("06Z", "09Z", "12Z")
    assert pw.window_hours("06Z") == ("00Z", "03Z", "06Z")
    assert pw.window_hours("00Z") == ("18Z", "21Z", "00Z")


def test_a_three_hour_window_covers_two_observations():
    assert pw.window_hours("09Z") == ("06Z", "09Z")
    assert pw.window_hours("03Z") == ("00Z", "03Z")
    assert pw.window_hours("21Z") == ("18Z", "21Z")


def test_phenomena_map_to_the_4561_figures():
    assert pw.figures_from_phenomena({"trueno": True}) == ["9"]
    assert pw.figures_from_phenomena({"niebla": True}) == ["4"]
    assert pw.figures_from_phenomena({"polvo": True}) == ["3"]
    assert pw.figures_from_phenomena({"niebla": False, "calima": ""}) == []
    assert pw.figures_from_phenomena(None) == []


def test_the_cloud_cover_fallback_uses_the_n_digit():
    assert pw.figure_from_cloud_cover("30100") == "0"   # 3 octas
    assert pw.figure_from_cloud_cover("50602") == "1"   # 5 octas
    assert pw.figure_from_cloud_cover("80602") == "2"   # 8 octas
    assert pw.figure_from_cloud_cover("/0602") == ""
    assert pw.figure_from_cloud_cover("") == ""


def test_w1_is_the_highest_and_w2_the_second():
    hours = {"12Z": {"meteo_4_1": "30100"}}
    phenomena = {"06Z": {"niebla": True}, "09Z": {"trueno": True}}
    assert pw.compute_w1w2("12Z", hours, phenomena) == "94"


def test_a_single_figure_is_repeated():
    hours = {"12Z": {"meteo_4_1": "30100"}}
    assert pw.compute_w1w2("12Z", hours, {"09Z": {"trueno": True}}) == "99"


def test_the_window_limits_what_counts():
    """A phenomenon outside the window of the hour does not enter."""
    hours = {"12Z": {"meteo_4_1": "30100"}}
    # 15Z belongs to a later window, not to the 12Z one
    assert pw.compute_w1w2("12Z", hours, {"15Z": {"trueno": True}}) == "00"


def test_without_phenomena_the_cloud_cover_speaks():
    hours = {"12Z": {"meteo_4_1": "80602"}}
    assert pw.compute_w1w2("12Z", hours, {}) == "22"


def test_without_any_data_it_is_double_slash():
    assert pw.compute_w1w2("12Z", {}, {}) == "//"


def test_the_suggested_group_reads_as_the_synop_group():
    hours = {"12Z": {"meteo_4_1": "30100"}}
    phenomena = {"09Z": {"trueno": True}, "06Z": {"niebla": True}}
    assert pw.suggested_group("12Z", hours, "03", phenomena) == "70394"
    assert pw.suggested_group("12Z", {}, "") == "7////"
