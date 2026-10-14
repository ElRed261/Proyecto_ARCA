"""Tests for the silver validation contract.

Day dicts are built by hand (transform schema): the ts/th/pressure/Tmax/Tmin/LL
group lives under `horas` (keys "00Z"..); the SYNOP group lives under
`cli3074` keyed by LOCAL hour, joining its Z-hour as Z = (N + 4) % 24 (pinned
by the fixture pressure match). `validate_day` returns `(df, errores)`; invalid
rows are dropped and reported, never raised.
"""

import pandera.errors

from arca_pipeline.validate import contracts
from arca_pipeline.validate.contracts import validate_day

SHA = "a" * 64


def _datos(**vals):
    defaults = {
        "ts": "24.4", "th": "22", "pres_est": "1014.2", "p3": "1015.0",
        "p24": "1013.6", "correc_alt": "1.6", "Tmax": "27.0", "Tmin": "24.3",
        "LL": "0.0",
    }
    defaults.update(vals)
    return {"datos": defaults}


def _cli(**vals):
    defaults = {
        "pres_est": "1014.2", "pres_nmm": "1015.8", "temp_seco": "24.4",
        "temp_humedo": "22", "hum_ptor": "21.0", "hum_tvap": "24.8",
        "hum_hr": "81.1", "viento_dir": "0", "viento_vel": "0",
        "visibilidad": "160", "tend_car": "6", "tend_dif": "00.8",
    }
    defaults.update(vals)
    return defaults


def _day(horas, cli3074=None, **kw):
    day = {
        "meta": {
            "estacion": kw.get("station", "78486"),
            "fecha": kw.get("fecha_raw", "01032026"),
        },
        "source_sha256": kw.get("sha", SHA),
        "validated_at": "2026-03-01T12:00:00",
        "horas": horas,
        "cli3074": cli3074 or {},
    }
    if "sha" in kw:
        day["source_sha256"] = kw["sha"]
    return day


def test_valid_day_passes():
    horas = {
        "00Z": _datos(Tmax="31.0", Tmin="27.0"),
        "06Z": _datos(),
    }
    df, errs = validate_day(_day(horas))

    assert errs == []
    assert len(df) == 2
    assert set(df["hora"]) == {"00Z", "06Z"}
    assert list(df.columns) == contracts.SILVER_COLUMNS
    row = df.loc[df["hora"] == "06Z"].iloc[0]
    assert float(row["ts"]) == 24.4
    assert float(row["Tmax"]) == 27.0
    assert row["station_code"] == "78486"
    assert row["fecha"] == "2026-03-01"  # DDMMYYYY -> YYYY-MM-DD


def test_temp_out_of_range_rejected():
    horas = {
        "00Z": _datos(Tmax="31.0", Tmin="27.0"),
        "06Z": _datos(ts="999"),
    }
    df, errs = validate_day(_day(horas))

    assert any("ts" in e and "06Z" in e for e in errs)
    assert set(df["hora"]) == {"00Z"}  # fila inválida descartada


def test_humidity_out_of_range_rejected():
    horas = {
        "00Z": _datos(Tmax="31.0", Tmin="27.0"),
        "06Z": _datos(),
    }
    cli3074 = {"2": _cli(hum_hr="150")}  # cli3074 hour 2 == 06Z
    df, errs = validate_day(_day(horas, cli3074))

    assert any("hum_hr" in e for e in errs)
    assert set(df["hora"]) == {"00Z"}


def test_tmax_below_tmin_rejected():
    horas = {"06Z": _datos(Tmax="20.0", Tmin="30.0")}
    df, errs = validate_day(_day(horas))

    assert any("Tmax" in e and "Tmin" in e for e in errs)
    assert df.empty


def test_bad_sha256_rejected():
    horas = {"00Z": _datos()}
    df, errs = validate_day(_day(horas, sha="short"))

    assert any("source_sha256" in e for e in errs)
    assert df.empty


def test_invalid_hour_key_rejected():
    horas = {"25Z": _datos()}
    df, errs = validate_day(_day(horas))

    assert any("25Z" in e for e in errs)
    assert df.empty


def test_cli_hour_24_fields_survive_validation():
    """Local hour '24' (CLI convention 1..24) maps to Z=(24+4)%24='04Z';
    the reverse lookup must find cli3074['24'], not a nonexistent '0' key."""
    horas = {"04Z": _datos(), "06Z": _datos()}
    cli3074 = {"24": _cli(pres_nmm="1016.5")}
    df, errs = validate_day(_day(horas, cli3074))

    assert errs == []
    row = df.loc[df["hora"] == "04Z"].iloc[0]
    assert float(row["pres_nmm"]) == 1016.5


def test_validate_silver_raises_on_invalid_data():
    df, _ = validate_day(_day({"06Z": _datos()}))
    df.loc[0, "ts"] = 999.0
    try:
        contracts.validate_silver(df)
    except (pandera.errors.SchemaError, pandera.errors.SchemaErrors):
        return
    raise AssertionError("validate_silver should raise SchemaError on bad data")