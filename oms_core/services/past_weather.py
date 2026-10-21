"""Past weather (W1 W2) computed from the hour windows of Regla 12.2.6.6.1.

The manual fixes the period each observation covers:

* six hours for the observations at **00, 06, 12 and 18 UTC**;
* three hours for the observations at **03, 09, 15 and 21 UTC**.

Since the synoptic hours are three hours apart, a six-hour window contains the
current observation plus the two before it, and a three-hour window contains
the current one plus the one before.

The figures come from the phenomena the observer marks in the CLI 3074 rows
(they are the machine-readable "past weather"), translated to the categories
of Tabla 4561; when the window has no phenomena at all, the cloud cover of the
current hour gives the 0/1/2 figures. ``W1`` is the highest applicable figure
and ``W2`` the second (12.2.6.6.4), repeated when there is only one
(12.2.6.6.5). With nothing observable the caller gets ``"//"`` — the manual's
``7ww//`` for unknown past conditions (Regla 12.2.6.1).
"""

from __future__ import annotations

#: Chronological order of the eight synoptic hours.
_CHRONOLOGICAL = ("00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z")

#: How many previous observations each hour's window covers.
WINDOW_PREVIOUS = {
    "06Z": 2, "12Z": 2, "18Z": 2, "00Z": 2,   # six-hour window
    "09Z": 1, "15Z": 1, "21Z": 1, "03Z": 1,   # three-hour window
}

#: CLI 3074 phenomenon -> Tabla 4561 figure (highest wins when several apply).
PHENOMENON_FIGURE = {
    "trueno": "9",
    "relampago": "9",
    "tornado": "9",
    "ventarron": "9",
    "granizo": "9",
    "niebla": "4",
    "neblina": "4",
    "polvo": "3",
    "calima": "3",
}


def window_hours(hora: str) -> tuple[str, ...]:
    """The observations a window covers, oldest first, ending at ``hora``."""
    previous = WINDOW_PREVIOUS.get(hora, 1)
    index = _CHRONOLOGICAL.index(hora)
    # the day is cyclic: the 00Z window starts on the previous evening
    hours = [str(_CHRONOLOGICAL[(index - step) % len(_CHRONOLOGICAL)])
             for step in range(previous, -1, -1)]
    return tuple(hours)


def figures_from_phenomena(phenomena: object) -> list[str]:
    """Tabla 4561 figures implied by the phenomenon flags of one hour."""
    if not isinstance(phenomena, dict):
        return []
    figures = []
    for key, value in phenomena.items():
        if not value or value in ("", False):
            continue
        figure = PHENOMENON_FIGURE.get(str(key))
        if figure is not None:
            figures.append(figure)
    return figures


def figure_from_cloud_cover(nddff: object) -> str:
    """0/1/2 from the N digit (octas): half or less, part, or total cover."""
    text = str(nddff or "")
    if not text or text[0] in "/-":
        return ""
    try:
        cover = int(text[0])
    except ValueError:
        return ""
    if cover <= 4:
        return "0"      # clouds covering half the sky or less
    if cover < 8:
        return "1"      # more than half, in part
    return "2"          # more than half, in its entirety


def compute_w1w2(
    hora: str,
    hours: dict[str, dict],
    phenomena_by_hour: dict[str, object] | None = None,
) -> str:
    """Two digits for W1 W2, or ``"//"`` when nothing can be said.

    ``hours`` is the day in the form's language (``meteo_4_1`` = Nddff);
    ``phenomena_by_hour`` maps a synoptic hour to its CLI 3074 phenomenon flags.
    """
    phenomena_by_hour = phenomena_by_hour or {}
    figures: list[str] = []
    for window_hour in window_hours(hora):
        figures.extend(figures_from_phenomena(phenomena_by_hour.get(window_hour)))
    if not figures:
        cover = figure_from_cloud_cover((hours.get(hora) or {}).get("meteo_4_1"))
        if cover:
            figures.append(cover)
    if not figures:
        return "//"
    figures.sort(reverse=True)
    first = figures[0]
    second = figures[1] if len(figures) > 1 else figures[0]
    return f"{first}{second}"


def suggested_group(hora: str, hours: dict[str, dict], ww: str,
                    phenomena_by_hour: dict[str, object] | None = None) -> str:
    """The whole ``7wwW1W2`` group the observer could accept as a suggestion."""
    past = compute_w1w2(hora, hours, phenomena_by_hour)
    present = ww if ww and ww != "//" else "//"
    return f"7{present}{past}"


__all__ = [
    "PHENOMENON_FIGURE",
    "WINDOW_PREVIOUS",
    "compute_w1w2",
    "figure_from_cloud_cover",
    "figures_from_phenomena",
    "suggested_group",
    "window_hours",
]
