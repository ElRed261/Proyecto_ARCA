"""Frontera PyO3 F2: oms_calc replica los vectores Rust de tests_synoptic/tests_monthly.

Cada vector espeja un caso de los tests Rust (oms_calc/src/tests_synoptic.rs y
tests_monthly.rs): umbrales de borde (0.5/0.6, 1.4/1.5, 1.9/2.0 en bandas de
tendencia), políticas de vacío, cadenas de hora previa, mapeos de nombres en ambas
direcciones y los pipelines JSON (realizar_calculos_json,
recalculate_derived_fields_json, process_day_data_json) con errores de JSON
malformado.
"""

import json

import pytest

import oms_calc

# =============================================================================
# Helpers psicrométricos
# =============================================================================

def test_h26():
    assert oms_calc.calcular_h26(22.3) == 26.916132691735225
    assert oms_calc.calcular_h26(0.0) == 6.112


def test_h26_epsilon_branch_returns_none():
    assert oms_calc.calcular_h26(-243.5) is None


def test_h27():
    assert oms_calc.calcular_h27(22.3) == 0.6769257
    assert oms_calc.calcular_h27(0.0) == 0.66


def test_h28_asumido():
    assert oms_calc.calcular_h28_asumido(23.2) == 28.427355819344356
    assert oms_calc.calcular_h28_asumido(-243.5) is None


def test_tension_vapor_corpus_hour():
    # ts=23.2, th=22.3 (hora real del corpus, 78486 08122025 06Z)
    assert oms_calc.calcular_tension_vapor(23.2, 22.3) == 26.306899561735225


def test_tension_vapor_none_when_h26_none():
    assert oms_calc.calcular_tension_vapor(-243.5, -243.5) is None


def test_humedad_relativa():
    tv = oms_calc.calcular_tension_vapor(23.2, 22.3)
    assert oms_calc.calcular_humedad_relativa(tv, 23.2) == 92.54078968482115


def test_punto_rocio_and_roundtrip():
    assert oms_calc.calcular_punto_rocio(23.2, 100.0) == 23.2
    tv = oms_calc.calcular_tension_vapor(23.2, 22.3)
    hr = oms_calc.calcular_humedad_relativa(tv, 23.2)
    assert oms_calc.calcular_punto_rocio(23.2, hr) == 21.90957123957764


def test_punto_rocio_none_on_non_finite():
    assert oms_calc.calcular_punto_rocio(float("nan"), 50.0) is None


# =============================================================================
# Formateadores de grupos SYNOP
# =============================================================================

def test_temperature_group():
    assert oms_calc.format_temperature_group(23.2) == "10232"
    assert oms_calc.format_temperature_group(0.0) == "10000"
    assert oms_calc.format_temperature_group(-5.7) == "11057"
    assert oms_calc.format_temperature_group(None) == ""


def test_dew_point_group():
    assert oms_calc.format_dew_point_group(21.9) == "20219"
    assert oms_calc.format_dew_point_group(-2.5) == "21025"
    assert oms_calc.format_dew_point_group(None) == ""


def test_pressure_group():
    assert oms_calc.format_pressure_group(1026.9) == "40269"
    assert oms_calc.format_pressure_group(1015.0) == "40150"
    assert oms_calc.format_pressure_group(None) == ""


def test_tendency_group_bands_and_rounding():
    assert oms_calc.format_pressure_tendency_group(3.0) == "53030"
    assert oms_calc.format_pressure_tendency_group(1.2) == "51012"
    assert oms_calc.format_pressure_tendency_group(1.45) == "52015"  # 1.45 -> 1.5
    assert oms_calc.format_pressure_tendency_group(0.54) == "50005"  # 0.54 -> 0.5
    assert oms_calc.format_pressure_tendency_group(-1.2) == "56012"
    assert oms_calc.format_pressure_tendency_group(None) == ""


def test_pressure_24h_group():
    assert oms_calc.format_pressure_24h_group(1.2) == "58012"
    assert oms_calc.format_pressure_24h_group(-1.2) == "59012"
    assert oms_calc.format_pressure_24h_group(0.0) == "58000"
    assert oms_calc.format_pressure_24h_group(None) == ""


def test_humidity_group_clamps_and_rounds():
    assert oms_calc.format_humidity_group(80.43) == "29080"
    assert oms_calc.format_humidity_group(120.0) == "29100"
    assert oms_calc.format_humidity_group(-3.0) == "29000"
    assert oms_calc.format_humidity_group(92.54) == "29093"
    assert oms_calc.format_humidity_group(None) == ""


# =============================================================================
# Bandas de tendencia (tendencia_a, delegado F0 + bordes exactos)
# =============================================================================

def test_tendencia_a_bands():
    assert oms_calc.tendencia_a(0.0) == "4"
    assert oms_calc.tendencia_a(0.5) == "0"
    assert oms_calc.tendencia_a(0.6) == "1"
    assert oms_calc.tendencia_a(1.4) == "1"
    assert oms_calc.tendencia_a(1.5) == "2"
    assert oms_calc.tendencia_a(1.9) == "2"
    assert oms_calc.tendencia_a(2.0) == "3"
    assert oms_calc.tendencia_a(-0.5) == "5"
    assert oms_calc.tendencia_a(-0.6) == "6"
    assert oms_calc.tendencia_a(-1.4) == "6"
    assert oms_calc.tendencia_a(-1.5) == "7"
    assert oms_calc.tendencia_a(-1.9) == "7"
    assert oms_calc.tendencia_a(-2.0) == "8"
    assert oms_calc.tendencia_a(0.05) == "4"


# =============================================================================
# Políticas de inclusión
# =============================================================================

@pytest.mark.parametrize("ir", ["0", "1", "2"])
def test_include_precipitation_true(ir):
    assert oms_calc.should_include_precipitation(ir) is True


@pytest.mark.parametrize("ir", ["3", "4", ""])
def test_include_precipitation_false(ir):
    assert oms_calc.should_include_precipitation(ir) is False


@pytest.mark.parametrize("ix", ["1", "4"])
def test_include_weather_true(ix):
    assert oms_calc.should_include_weather(ix) is True


@pytest.mark.parametrize("ix", ["0", "2", ""])
def test_include_weather_false(ix):
    assert oms_calc.should_include_weather(ix) is False


# =============================================================================
# Mapeos WMO
# =============================================================================

def test_synop_name_mapping():
    assert oms_calc.to_synop_name("meteo_2_1") == "YYGGiw"
    assert oms_calc.to_synop_name("meteo_4_irixhvv") == "IrIXHVV"
    assert oms_calc.to_synop_name("meteo_6_2") == "0CSDL DM DH"
    assert oms_calc.to_synop_name("extra_8ns_1") == "8NsChshs_3"
    assert oms_calc.to_synop_name("meteo_16_4") == "9spspsp_24"
    assert oms_calc.to_synop_name("whatever") == "whatever"


def test_frontend_name_mapping_and_oracle_asymmetry():
    assert oms_calc.to_frontend_name("YYGGiw") == "meteo_2_1"
    assert oms_calc.to_frontend_name("IrIXHVV") == "meteo_4_irixhvv"
    assert oms_calc.to_frontend_name("0CSDL DM DH") == "meteo_6_2"
    assert oms_calc.to_frontend_name("8NsChshs_3") == "extra_8ns_1"
    assert oms_calc.to_frontend_name("8NsChshs_6") == "meteo_10_1"
    # Quirk del oráculo conservado: la tabla inversa termina en 8NsChshs_6
    assert oms_calc.to_frontend_name("9spspsp_5") == "9spspsp_5"
    assert oms_calc.to_frontend_name("unknown") == "unknown"


def test_visibilidad_from_irixhv():
    assert oms_calc.get_visibilidad_from_irixhv("32566") == "160"
    assert oms_calc.get_visibilidad_from_irixhv("80") == "300"
    assert oms_calc.get_visibilidad_from_irixhv("00") == "000"
    assert oms_calc.get_visibilidad_from_irixhv("99") == ""
    assert oms_calc.get_visibilidad_from_irixhv("5") == ""
    assert oms_calc.get_visibilidad_from_irixhv("") == ""


# =============================================================================
# format_dif / calc_dif / calc_car / calc_tiempo_presente / get_prev_hour
# =============================================================================

def test_format_dif_inserts_decimal_point():
    assert oms_calc.format_dif("") == ""
    assert oms_calc.format_dif("12.5") == "12.5"
    assert oms_calc.format_dif("256") == "25.6"
    assert oms_calc.format_dif("1025") == "10.25"
    assert oms_calc.format_dif("1025.3") == "1025.3"
    assert oms_calc.format_dif("5") == "5"


def test_calc_dif_absolute_difference():
    assert oms_calc.calc_dif("1025.3", "1022.3") == "03.0"
    assert oms_calc.calc_dif("1022.3", "1025.3") == "03.0"
    assert oms_calc.calc_dif("1012.6", "1010.1") == "02.5"
    assert oms_calc.calc_dif("1025.3", "1005.3") == "20.0"
    assert oms_calc.calc_dif("abc", "1022.3") == ""
    assert oms_calc.calc_dif("", "") == ""


def test_calc_car_uses_raw_difference_no_rounding():
    assert oms_calc.calc_car("1025.3", "1022.3") == "3"
    assert oms_calc.calc_car("1022.3", "1024.0") == "7"
    assert oms_calc.calc_car("abc", "1022.3") == ""
    assert oms_calc.calc_car("", "") == ""


def test_calc_tiempo_presente_from_ww_and_nddff_fallback():
    assert oms_calc.calc_tiempo_presente("71020", "", "") == "10"
    assert oms_calc.calc_tiempo_presente("71/20", "", "") == ""
    # workbook FORMULAS!M3: cover falling -> 01, steady -> 02, rising -> 03
    assert oms_calc.calc_tiempo_presente("", "30100", "50102") == "01"
    assert oms_calc.calc_tiempo_presente("", "50102", "50102") == "02"
    assert oms_calc.calc_tiempo_presente("", "50102", "30100") == "03"
    assert oms_calc.calc_tiempo_presente("", "/0102", "50102") == ""
    assert oms_calc.calc_tiempo_presente("", "50102", "/0102") == ""
    assert oms_calc.calc_tiempo_presente("", "", "") == ""
    assert oms_calc.calc_tiempo_presente("71", "", "") == ""


def test_prev_hour_chain():
    assert oms_calc.get_prev_hour("06Z") == "03Z"
    assert oms_calc.get_prev_hour("09Z") == "06Z"
    assert oms_calc.get_prev_hour("12Z") == "09Z"
    assert oms_calc.get_prev_hour("15Z") == "12Z"
    assert oms_calc.get_prev_hour("18Z") == "15Z"
    assert oms_calc.get_prev_hour("21Z") == "18Z"
    assert oms_calc.get_prev_hour("00Z") == "21Z"
    assert oms_calc.get_prev_hour("03Z") == "00Z"
    assert oms_calc.get_prev_hour("24Z") == ""
    assert oms_calc.get_prev_hour("") == ""


# =============================================================================
# realizar_calculos_json (frontera JSON)
# =============================================================================

def realizar(request, correc_alt=None):
    return json.loads(oms_calc.realizar_calculos_json(json.dumps(request), correc_alt))


def test_realizar_calculos_full_corpus_hour():
    # Hora real del corpus (78486, 08122025, 06Z); "1.6" es la corrección de la
    # estación resuelta por Python (F4), espejo del lookup de pool del oráculo.
    res = realizar(
        {"station_id": "78486", "ts": "23.2", "th": "22.3", "pres_est": "1025.3",
         "p3": "1022.3", "p24": "1024.1", "ir": "1", "ix": "4"},
        "1.6",
    )
    assert res["tension_vapor"] == "26.3"
    assert res["humedad_relativa"] == "93"
    assert res["punto_rocio"] == "21.9"
    assert res["diferencia"] == "0.9"
    assert res["grupo_1sn_ttt"] == "10232"
    assert res["grupo_2sn_td"] == "20219"
    assert res["grupo_4pppp"] == "40269"
    assert res["grupo_5appp"] == "53030"
    assert res["grupo_58_59_p24"] == "58012"
    assert res["grupo_29uuu"] == "29093"
    assert res["p3_let"] == "1025.3"
    assert res["p24_let"] == "1025.3"
    assert res["p3_dif"] == "3.0"
    assert res["p24_dif"] == "1.2"
    assert res["pres_nmm"] == "1026.9"
    assert res["correc_alt"] == "1.6"
    assert res["include_precipitation"] is True
    assert res["include_weather"] is True
    assert res["station_info"] is None
    assert res["error_message"] == ""


def test_realizar_calculos_resolved_correc_alt_wins_over_request():
    res = realizar({"ts": "23.2", "pres_est": "1010.0", "correc_alt": "9.9"}, "1.6")
    assert res["correc_alt"] == "1.6"
    assert res["pres_nmm"] == "1011.6"

    res2 = realizar({"pres_est": "1010.0", "correc_alt": "2.5"}, "")
    assert res2["correc_alt"] == "2.5"
    assert res2["pres_nmm"] == "1012.5"

    res3 = realizar({"pres_est": "1010.0"})
    assert res3["correc_alt"] == ""
    assert res3["pres_nmm"] == ""
    assert res3["grupo_4pppp"] == ""


def test_realizar_calculos_station_echo_rides_inside_json():
    # El eco de estación viaja DENTRO del JSON (no cruza StationInfo por la frontera)
    req = {"ts": "23.2", "station_info": {"id": "78486", "ch": "1.6", "name": "78486"}}
    res = realizar(req, "1.6")
    assert res["station_info"] == {"id": "78486", "ch": "1.6", "name": "78486"}

    # Sin resolved → sin eco
    res2 = realizar(req, None)
    assert res2.get("station_info") is None


def test_realizar_calculos_th_greater_than_ts_is_error():
    res = realizar({"ts": "20.0", "th": "22.0"})
    assert res["error_message"] == "Error: Th no puede ser mayor que Ts."
    assert res["tension_vapor"] == ""
    assert res["humedad_relativa"] == ""
    assert res["punto_rocio"] == ""
    assert res["diferencia"] == ""
    assert res["grupo_1sn_ttt"] == "10200"


def test_realizar_calculos_th_equal_ts_is_valid():
    res = realizar({"ts": "20.0", "th": "20.0"})
    assert res["error_message"] == ""
    assert res["diferencia"] == "0.0"
    tv = oms_calc.calcular_tension_vapor(20.0, 20.0)
    assert res["tension_vapor"] == f"{tv:.1f}"


def test_realizar_calculos_empty_inputs_all_empty():
    res = realizar({})
    for key in ["tension_vapor", "humedad_relativa", "punto_rocio", "diferencia",
                "grupo_1sn_ttt", "grupo_2sn_td", "grupo_4pppp", "grupo_5appp",
                "grupo_58_59_p24", "grupo_29uuu", "p3_let", "p24_let", "p3_dif",
                "p24_dif", "pres_nmm", "correc_alt", "error_message"]:
        assert res[key] == "", key
    assert res["include_precipitation"] is True
    assert res["include_weather"] is True


def test_realizar_calculos_ir_ix_policies():
    res = realizar({"ir": "3", "ix": "2"})
    assert res["include_precipitation"] is False
    assert res["include_weather"] is False

    res2 = realizar({"ir": "2", "ix": "1"})
    assert res2["include_precipitation"] is True
    assert res2["include_weather"] is True


def test_realizar_calculos_non_numeric_inputs_are_ignored():
    res = realizar({"ts": "abc", "th": "22.3", "pres_est": "x", "p3": "y", "correc_alt": "z"})
    assert res["tension_vapor"] == ""
    assert res["p3_let"] == ""
    assert res["pres_nmm"] == ""
    assert res["correc_alt"] == "z"


def test_realizar_calculos_malformed_json_raises():
    with pytest.raises(ValueError):
        oms_calc.realizar_calculos_json("{not json", None)
    with pytest.raises(ValueError):
        oms_calc.realizar_calculos_json('{"ts": "23.2"', None)
    with pytest.raises(ValueError):
        oms_calc.realizar_calculos_json("[]", None)  # wrong shape
    # Un JSON malformado no produce salida: los datos se rechazan enteros
    try:
        oms_calc.realizar_calculos_json("{oops", None)
    except ValueError:
        pass


# =============================================================================
# recalculate_derived_fields_json (frontera de recálculo)
# =============================================================================

def test_recalc_derived_fields_full_hour():
    d = json.loads(oms_calc.recalculate_derived_fields_json(
        "78486", "23.2", "22.3", "1025.3", "1022.3", "1024.1", None,
        "32566", "71020", "50102", "30100", "1.6"))
    assert d["tension_vapor"] == "26.3"
    assert d["humedad_relativa"] == "93"
    assert d["punto_rocio"] == "21.9"
    assert d["diferencia"] == "0.9"
    assert d["pres_nmm"] == "1026.9"
    assert d["tend_dif"] == "03.0"
    assert d["tend_car"] == "3"
    assert d["visibilidad"] == "160"
    assert d["tiempo_presente"] == "10"


def test_recalc_derived_fields_th_greater_than_ts_stays_empty():
    d = json.loads(oms_calc.recalculate_derived_fields_json(
        None, "20.0", "22.3", None, None, None, None, None, None, None, None, None))
    assert d["tension_vapor"] == ""
    assert d["humedad_relativa"] == ""
    assert d["punto_rocio"] == ""
    assert d["diferencia"] == ""


def test_recalc_derived_fields_correc_alt_priority():
    d = json.loads(oms_calc.recalculate_derived_fields_json(
        None, None, None, "1010.0", None, None, "2.5", None, None, None, None, "1.6"))
    assert d["pres_nmm"] == "1012.5"

    d2 = json.loads(oms_calc.recalculate_derived_fields_json(
        None, None, None, "1010.0", None, None, "", None, None, None, None, "1.6"))
    assert d2["pres_nmm"] == "1011.6"

    d3 = json.loads(oms_calc.recalculate_derived_fields_json(
        None, None, None, "1010.0", None, None, "  ", None, None, None, None, "1.6"))
    assert d3["pres_nmm"] == "1011.6"

    d4 = json.loads(oms_calc.recalculate_derived_fields_json(
        None, None, None, "1010.0", None, None, None, None, None, None, None, None))
    assert d4["pres_nmm"] == ""


def test_recalc_derived_fields_empty_inputs_all_empty():
    d = json.loads(oms_calc.recalculate_derived_fields_json(
        None, None, None, None, None, None, None, None, None, None, None, None))
    assert d == {"tension_vapor": "", "humedad_relativa": "", "punto_rocio": "",
                 "diferencia": "", "pres_nmm": "", "tend_dif": "", "tend_car": "",
                 "visibilidad": "", "tiempo_presente": ""}


def test_recalc_derived_fields_p24_reserved():
    a = oms_calc.recalculate_derived_fields_json(
        None, "20.0", "18.0", "1010.0", None, "1000.0", None, None, None, None, None, None)
    b = oms_calc.recalculate_derived_fields_json(
        None, "20.0", "18.0", "1010.0", None, None, None, None, None, None, None, None)
    assert a == b


# =============================================================================
# process_day_data_json (frontera resumen mensual)
# =============================================================================

def build_day(fecha="15052025"):
    z_hours = [
        {"hora": "06Z", "datos": {"p_est": 1012.6, "p_nmm": 1014.2, "rocio": 22.624143756848554,
                                  "t_vapor": 27.359955030153266, "hr": 80.43463436438854,
                                  "v_dir_deg": 60, "v_vel": 3.0}},
        {"hora": "09Z", "datos": {"p_est": 1013.1, "p_nmm": 1014.7, "rocio": 23.1,
                                  "t_vapor": 28.0, "hr": 82.0, "v_dir_deg": 45, "v_vel": 5.5}},
        {"hora": "12Z", "datos": {"p_est": 1011.8, "p_nmm": 1013.4, "rocio": 24.0,
                                  "t_vapor": 29.1, "hr": 85.0, "v_dir_deg": 70, "v_vel": 2.0}},
        {"hora": "15Z", "datos": {"p_est": 1010.9, "p_nmm": 1012.5, "rocio": 24.5,
                                  "t_vapor": 29.8, "hr": 88.0, "v_vel": 1.5}},
        {"hora": "18Z", "datos": {"p_est": 1012.0, "p_nmm": 1013.6, "rocio": 23.8,
                                  "t_vapor": 29.0, "hr": 86.0, "v_dir_deg": 20, "v_vel": 4.0}},
        {"hora": "21Z", "datos": {"p_est": 1013.4, "p_nmm": 1015.0, "rocio": 23.2,
                                  "t_vapor": 28.2, "hr": 83.0, "v_dir_deg": 25, "v_vel": 3.5}},
        {"hora": "00Z", "datos": {"p_est": 1014.8, "p_nmm": 1016.4, "rocio": 22.9,
                                  "t_vapor": 27.9, "hr": 81.0, "v_dir_deg": 30, "v_vel": 2.5}},
        {"hora": "03Z", "datos": {"p_est": 1015.5, "p_nmm": 1017.1, "rocio": 22.4,
                                  "t_vapor": 27.4, "hr": 79.5, "v_dir_deg": 40, "v_vel": 3.0}},
    ]
    extras = [
        {"hora": "TMAX", "datos": {"tmax": 31.0}},
        {"hora": "TMAX", "datos": {"tmax": 33.5}},
        {"hora": "TMIN", "datos": {"tmin": 23.0}},
        {"hora": "TMIN", "datos": {"tmin": 22.5}},
        {"hora": "filas_nuvosidad_dia", "datos": {"nub": 1.0}},
        {"hora": "filas_nuvosidad_dia", "datos": {"nub": 2.5}},
        {"hora": "filas_nuvosidad_dia", "datos": {"nub": 7.0}},
        {"hora": "filas_nuvosidad_tarde", "datos": {"nub": 0.5}},
        {"hora": "filas_nuvosidad_tarde", "datos": {"nub": 3.0}},
        {"hora": "filas_nuvosidad_tarde", "datos": {"nub": 6.0}},
    ]
    return {"meta": {"estacion": "Estación Central", "fecha": fecha},
            "horarias": z_hours + extras,
            "resumen_dia": {"pp": 2.3}}


def test_process_day_data_full_corpus_like_day():
    kpis = json.loads(oms_calc.process_day_data_json(json.dumps(build_day())))
    assert kpis["Dias"] == "2025-05-15"
    assert kpis["Mayor temperatura máxima"] == 33.5
    assert kpis["Menor temperatura minima"] == 22.5
    assert kpis["Media temperatura"] == 28.0
    assert kpis["MAxima presión nivel medio del mar"] == 1017.1
    assert kpis["Minima presión nivel medio del mar"] == 1012.5
    assert kpis["Media presión nivel medio del mar"] == 1014.8
    assert kpis["Media presion en la estación"] == 1013.0
    assert kpis["Lluvia"] == 2.3
    assert kpis["Dirección del viento"] == "NNE"
    assert kpis["Velocidad media del viento"] == 11.3
    assert kpis["Velocidad máxima y direccion"] == "NE 19,8"
    assert kpis["Recorrido del viento"] == 90.0
    assert kpis["Nuvocidad dia"] == 3.5
    assert kpis["Nuvocidad noche"] == 3.2
    # El oráculo computa la media con dia/tarde SIN redondear
    assert kpis["Media de nuvocidad"] == 3.3
    assert kpis["Humedad maxima"] == 88.0
    assert kpis["Humedad minima"] == 80.0
    assert kpis["Humedad media"] == 83.1
    assert kpis["Punto de rocio"] == 23.3
    assert kpis["Tensión de vapor"] == 28.3


def test_process_day_data_columns_use_oracle_names():
    kpis = json.loads(oms_calc.process_day_data_json(json.dumps(build_day())))
    for key in ["Dias", "Mayor temperatura máxima", "Menor temperatura minima",
                "Media temperatura", "MAxima presión nivel medio del mar",
                "Minima presión nivel medio del mar", "Media presión nivel medio del mar",
                "Media presion en la estación", "Lluvia", "Dirección del viento",
                "Velocidad media del viento", "Velocidad máxima y direccion",
                "Recorrido del viento", "Nuvocidad dia", "Nuvocidad noche",
                "Media de nuvocidad", "Humedad maxima", "Humedad minima",
                "Humedad media", "Punto de rocio", "Tensión de vapor"]:
        assert key in kpis


def test_process_day_data_empty_day():
    obs = {"meta": {"estacion": "X", "fecha": "15052025"}, "horarias": [],
           "resumen_dia": {"pp": None}}
    kpis = json.loads(oms_calc.process_day_data_json(json.dumps(obs)))
    assert kpis["Dias"] == "2025-05-15"
    assert kpis["Mayor temperatura máxima"] is None
    assert kpis["Minima presión nivel medio del mar"] is None
    assert kpis["Dirección del viento"] is None
    assert kpis["Velocidad máxima y direccion"] == "N/A"
    assert kpis["Nuvocidad dia"] is None


def test_process_day_data_non_z_hours_ignored():
    obs = {"meta": {"estacion": "X", "fecha": "15052025"},
           "horarias": [
               {"hora": "05Z", "datos": {"p_est": 1012.0, "p_nmm": 1014.0}},
               {"hora": "FOO", "datos": {"tmax": 99.0, "tmin": 1.0, "nub": 8.0}},
           ],
           "resumen_dia": {"pp": 0.0}}
    kpis = json.loads(oms_calc.process_day_data_json(json.dumps(obs)))
    assert kpis["Mayor temperatura máxima"] is None
    assert kpis["Menor temperatura minima"] is None
    assert kpis["Media presion en la estación"] is None
    assert kpis["Lluvia"] == 0.0


def test_process_day_data_rejects_non_finite_json_tokens():
    # Nota de frontera: Python serializa NaN/Infinity como tokens no estándar
    # (json.dumps los emite); serde_json los rechaza estrictamente. El filtro
    # safe_f64 del oráculo se cubre en Rust (tests_monthly); aqui queda fijado
    # el comportamiento de frontera: entrada con NaN -> ValueError, sin salida.
    obs = {"meta": {"estacion": "X", "fecha": "15052025"},
           "horarias": [
               {"hora": "06Z", "datos": {"p_est": float("nan")}},
               {"hora": "09Z", "datos": {"p_est": 1010.0}},
           ],
           "resumen_dia": {"pp": None}}
    payload = json.dumps(obs)  # emitirá el token NaN
    with pytest.raises(ValueError):
        oms_calc.process_day_data_json(payload)


def test_process_day_data_nubosidad_fallback_when_no_filas():
    obs = {"meta": {"estacion": "X", "fecha": "15052025"},
           "horarias": [
               {"hora": "06Z", "datos": {"nub": 2.0}},
               {"hora": "09Z", "datos": {"nub": 5.0}},
           ],
           "resumen_dia": {"pp": None}}
    kpis = json.loads(oms_calc.process_day_data_json(json.dumps(obs)))
    assert kpis["Nuvocidad dia"] == 3.5
    assert kpis["Nuvocidad noche"] is None
    assert kpis["Media de nuvocidad"] == 3.5


def test_process_day_data_nubosidad_filas_media_from_unrounded():
    obs = {"meta": {"estacion": "X", "fecha": "15052025"},
           "horarias": [
               {"hora": "filas_nuvosidad_dia", "datos": {"nub": 1.0}},
               {"hora": "filas_nuvosidad_dia", "datos": {"nub": 2.5}},
               {"hora": "filas_nuvosidad_dia", "datos": {"nub": 7.0}},
               {"hora": "filas_nuvosidad_tarde", "datos": {"nub": 0.5}},
               {"hora": "filas_nuvosidad_tarde", "datos": {"nub": 3.0}},
               {"hora": "filas_nuvosidad_tarde", "datos": {"nub": 6.0}},
           ],
           "resumen_dia": {"pp": None}}
    kpis = json.loads(oms_calc.process_day_data_json(json.dumps(obs)))
    assert kpis["Nuvocidad dia"] == 3.5
    assert kpis["Nuvocidad noche"] == 3.2
    assert kpis["Media de nuvocidad"] == 3.3


def test_process_day_data_dias_formats_only_8_char_fechas():
    for fecha, esperado in [("15032024", "2024-03-15"), ("1503", "1503")]:
        obs = {"meta": {"estacion": "X", "fecha": fecha}, "horarias": [],
               "resumen_dia": {"pp": None}}
        kpis = json.loads(oms_calc.process_day_data_json(json.dumps(obs)))
        assert kpis["Dias"] == esperado


def test_process_day_data_deserializes_real_corpus_file():
    # Idempotencia del pipeline sobre la forma REAL del corpus F1 (fixture)
    import pathlib

    probe = pathlib.Path(__file__).parent / "fixtures" / "importer" / "json" / (
        "Estación Central/2025/05/Estación Central 15052025.json")
    data = json.loads(probe.read_text(encoding="utf-8"))
    obs = {"meta": {"estacion": data["meta"]["estacion"], "fecha": data["meta"]["fecha"]},
           "horarias": data["horarias"],
           "resumen_dia": data["resumen_dia"]}
    kpis = json.loads(oms_calc.process_day_data_json(json.dumps(obs)))
    assert kpis["Dias"] == "2025-05-15"
    assert kpis["Lluvia"] == data["resumen_dia"]["pp"]


def test_process_day_data_malformed_json_raises():
    with pytest.raises(ValueError):
        oms_calc.process_day_data_json("{not json")
    with pytest.raises(ValueError):
        oms_calc.process_day_data_json('{"meta": {}}')
    with pytest.raises(ValueError):
        oms_calc.process_day_data_json("[]")
    with pytest.raises(ValueError):
        oms_calc.process_day_data_json('{"horarias": [{"hora": "06Z"}]}')
