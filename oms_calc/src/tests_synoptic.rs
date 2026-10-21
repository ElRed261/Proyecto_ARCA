//! F2 unit tests for the verbatim port of `modules/synoptic/calculations.rs`.
//! Vectors mirror the oracle branches: boundary thresholds (0.5/0.6, 1.4/1.5,
//! 1.9/2.0 tendency bands), empty-input policies, formatting quirks and the
//! WMO mappings, both directions.

use crate::synoptic::*;
use std::collections::HashMap;

fn approx(a: f64, b: f64) {
    assert!((a - b).abs() < 1e-9, "expected {} got {}", b, a);
}

// =============================================================================
// Psychrometric helpers
// =============================================================================

#[test]
fn h26_wet_bulb() {
    approx(calcular_h26(22.3).unwrap(), 26.916132691735225);
    approx(calcular_h26(0.0).unwrap(), 6.112);
}

#[test]
fn h26_epsilon_branch_returns_none() {
    // Oracle guard: (temp_humedo + 243.5).abs() < f64::EPSILON
    assert!(calcular_h26(-243.5).is_none());
}

#[test]
fn h27_values() {
    approx(calcular_h27(22.3), 0.6769257);
    approx(calcular_h27(0.0), 0.66);
}

#[test]
fn h28_asumido_values_and_epsilon_branch() {
    approx(calcular_h28_asumido(23.2).unwrap(), 28.427355819344356);
    assert!(calcular_h28_asumido(-243.5).is_none());
}

#[test]
fn tension_vapor_corpus_hour() {
    // ts=23.2, th=22.3 (real corpus hour, 78486 08122025 06Z)
    let tv = calcular_tension_vapor(23.2, 22.3).unwrap();
    approx(tv, 26.306899561735225);
}

#[test]
fn tension_vapor_none_when_h26_none() {
    assert!(calcular_tension_vapor(-243.5, -243.5).is_none());
}

#[test]
fn humedad_relativa_value() {
    let tv = calcular_tension_vapor(23.2, 22.3).unwrap();
    let hr = calcular_humedad_relativa(tv, 23.2).unwrap();
    approx(hr, 92.54078968482115);
}

#[test]
fn punto_rocio_value_and_full_humidity_roundtrip() {
    // RH 100% => dew point equals the dry-bulb temperature
    approx(calcular_punto_rocio(23.2, 100.0).unwrap(), 23.2);
    let tv = calcular_tension_vapor(23.2, 22.3).unwrap();
    let hr = calcular_humedad_relativa(tv, 23.2).unwrap();
    let pr = calcular_punto_rocio(23.2, hr).unwrap();
    approx(pr, 21.90957123957764);
}

#[test]
fn punto_rocio_none_on_non_finite() {
    // NaN inputs must yield None (oracle guards is_nan/is_infinite)
    assert!(calcular_punto_rocio(f64::NAN, 50.0).is_none());
}

// =============================================================================
// SYNOP group formatters
// =============================================================================

#[test]
fn temperature_group() {
    assert_eq!(format_temperature_group(Some(23.2)), "10232");
    assert_eq!(format_temperature_group(Some(0.0)), "10000"); // sign 0 at zero, {:03} keeps 3 digits
    // Oracle shape: "1" + sign(0/1) + 3-digit ttt (abs value)
    assert_eq!(format_temperature_group(Some(-5.7)), "11057");
    assert_eq!(format_temperature_group(None), ""); // empty = not computable
}

#[test]
fn dew_point_group() {
    assert_eq!(format_dew_point_group(Some(21.9)), "20219");
    assert_eq!(format_dew_point_group(Some(-2.5)), "21025");
    assert_eq!(format_dew_point_group(None), "");
}

#[test]
fn pressure_group() {
    // 1026.9*10 = 10269 -> %10000 = 0269
    assert_eq!(format_pressure_group(Some(1026.9)), "40269");
    assert_eq!(format_pressure_group(Some(1015.0)), "40150"); // 10150 % 10000 = 0150
    assert_eq!(format_pressure_group(None), "");
}

#[test]
fn tendency_group_bands_and_rounding() {
    // Rounded first to 0.1 hPa, then the characteristic band applies.
    assert_eq!(format_pressure_tendency_group(Some(3.0)), "53030");
    assert_eq!(format_pressure_tendency_group(Some(1.2)), "51012");
    // 1.45 rounds to 1.5 (half away from zero) -> band "2"
    assert_eq!(format_pressure_tendency_group(Some(1.45)), "52015");
    // 0.54 rounds to 0.5 -> band "0"
    assert_eq!(format_pressure_tendency_group(Some(0.54)), "50005");
    // Negative falls: dif -1.2 -> a=6, ppp=012
    assert_eq!(format_pressure_tendency_group(Some(-1.2)), "56012");
    assert_eq!(format_pressure_tendency_group(None), "");
}

#[test]
fn pressure_24h_group() {
    assert_eq!(format_pressure_24h_group(Some(1.2)), "58012");
    assert_eq!(format_pressure_24h_group(Some(-1.2)), "59012");
    assert_eq!(format_pressure_24h_group(Some(0.0)), "58000");
    assert_eq!(format_pressure_24h_group(None), "");
}

#[test]
fn humidity_group_clamps_and_rounds() {
    assert_eq!(format_humidity_group(Some(80.43)), "29080");
    assert_eq!(format_humidity_group(Some(120.0)), "29100"); // clamped to 100
    assert_eq!(format_humidity_group(Some(-3.0)), "29000"); // clamped to 0
    assert_eq!(format_humidity_group(Some(92.54)), "29093");
    assert_eq!(format_humidity_group(None), "");
}

// =============================================================================
// Tendency bands (calcular_tendencia_a) — F0 covered these; F2 re-checks the
// exposed `tendencia_a` delegate plus the exact band boundaries.
// =============================================================================

#[test]
fn tendencia_a_bands_via_lib_delegate() {
    assert_eq!(super::tendencia_a(0.0), "4");
    assert_eq!(super::tendencia_a(0.5), "0"); // 0.1..=0.5 upper bound
    assert_eq!(super::tendencia_a(0.6), "1"); // 0.6..=1.4 lower bound
    assert_eq!(super::tendencia_a(1.4), "1");
    assert_eq!(super::tendencia_a(1.5), "2"); // 1.5..=1.9 lower bound
    assert_eq!(super::tendencia_a(1.9), "2");
    assert_eq!(super::tendencia_a(2.0), "3"); // >= 2.0
    assert_eq!(super::tendencia_a(-0.5), "5");
    assert_eq!(super::tendencia_a(-0.6), "6");
    assert_eq!(super::tendencia_a(-1.4), "6");
    assert_eq!(super::tendencia_a(-1.5), "7");
    assert_eq!(super::tendencia_a(-1.9), "7");
    assert_eq!(super::tendencia_a(-2.0), "8");
    assert_eq!(super::tendencia_a(0.05), "4"); // below the 0.1 band -> fallback 4
}

// =============================================================================
// Include policies
// =============================================================================

#[test]
fn include_policies() {
    assert!(should_include_precipitation("0"));
    assert!(should_include_precipitation("1"));
    assert!(should_include_precipitation("2"));
    assert!(!should_include_precipitation("3"));
    assert!(!should_include_precipitation("4"));
    assert!(!should_include_precipitation(""));

    // Table 1860: 1, 4 and 7 include the group; 2, 3, 5 and 6 omit it
    assert!(should_include_weather("1"));
    assert!(should_include_weather("4"));
    assert!(should_include_weather("7"));
    assert!(!should_include_weather("0"));
    assert!(!should_include_weather("2"));
    assert!(!should_include_weather("3"));
    assert!(!should_include_weather("5"));
    assert!(!should_include_weather("6"));
    assert!(!should_include_weather(""));
}

// =============================================================================
// WMO mappings
// =============================================================================

#[test]
fn synop_name_mapping() {
    assert_eq!(to_synop_name("meteo_2_1"), "YYGGiw");
    assert_eq!(to_synop_name("meteo_4_irixhvv"), "IrIXHVV");
    assert_eq!(to_synop_name("meteo_6_2"), "0CSDL DM DH");
    assert_eq!(to_synop_name("extra_8ns_1"), "8NsChshs_3");
    assert_eq!(to_synop_name("meteo_16_4"), "9spspsp_24");
    // Unknown names pass through unchanged
    assert_eq!(to_synop_name("whatever"), "whatever");
}

#[test]
fn frontend_name_mapping_and_oracle_asymmetry() {
    assert_eq!(to_frontend_name("YYGGiw"), "meteo_2_1");
    assert_eq!(to_frontend_name("IrIXHVV"), "meteo_4_irixhvv");
    assert_eq!(to_frontend_name("0CSDL DM DH"), "meteo_6_2");
    assert_eq!(to_frontend_name("8NsChshs_3"), "extra_8ns_1");
    assert_eq!(to_frontend_name("8NsChshs_6"), "meteo_10_1");
    // Oracle quirk kept verbatim: the reverse table stops at 8NsChshs_6,
    // so 9spspsp_* pass through unchanged (round-trip is not an identity there).
    assert_eq!(to_frontend_name("9spspsp_5"), "9spspsp_5");
    assert_eq!(to_frontend_name("unknown"), "unknown");
}

#[test]
fn visibilidad_from_irixhv() {
    assert_eq!(get_visibilidad_from_irixhv("32566"), "160");
    assert_eq!(get_visibilidad_from_irixhv("80"), "300");
    assert_eq!(get_visibilidad_from_irixhv("00"), "000");
    // Below the table start (00) -> empty
    assert_eq!(get_visibilidad_from_irixhv("99"), "");
    // Too short -> empty
    assert_eq!(get_visibilidad_from_irixhv("5"), "");
    assert_eq!(get_visibilidad_from_irixhv(""), "");
}

// =============================================================================
// dif formatting and pressure helpers
// =============================================================================

#[test]
fn format_dif_inserts_decimal_point() {
    assert_eq!(format_dif(""), "");
    assert_eq!(format_dif("12.5"), "12.5"); // len 4 with '.', unchanged
    assert_eq!(format_dif("256"), "25.6"); // len 3 -> "ab.c"
    assert_eq!(format_dif("1025"), "10.25"); // len 4 without '.' -> "ab.cd"
    assert_eq!(format_dif("1025.3"), "1025.3"); // other lengths pass through
    assert_eq!(format_dif("5"), "5");
}

#[test]
fn calc_dif_absolute_difference() {
    assert_eq!(calc_dif("1025.3", "1022.3"), "03.0"); // {:04.1} pads to 4 chars
    assert_eq!(calc_dif("1022.3", "1025.3"), "03.0"); // absolute value
    assert_eq!(calc_dif("1012.6", "1010.1"), "02.5");
    assert_eq!(calc_dif("1025.3", "1005.3"), "20.0");
    assert_eq!(calc_dif("abc", "1022.3"), ""); // non-numeric -> empty
    assert_eq!(calc_dif("", ""), "");
}

#[test]
fn calc_car_uses_raw_difference_no_rounding() {
    // dif = 3.0 -> band 3
    assert_eq!(calc_car("1025.3", "1022.3"), "3");
    // Raw difference -1.7 -> band 7 (calc_car does NOT round first, unlike the group)
    assert_eq!(calc_car("1022.3", "1024.0"), "7");
    assert_eq!(calc_car("abc", "1022.3"), "");
    assert_eq!(calc_car("", ""), "");
}

#[test]
fn calc_tiempo_presente_from_ww_and_nddff_fallback() {
    // ww digits present -> copied
    assert_eq!(calc_tiempo_presente("71020", "", ""), "10");
    assert_eq!(calc_tiempo_presente("71/20", "", ""), ""); // contains '/'
    // Fallback on the Nddff cloud-cover digit evolution, as the station's
    // workbook computes it (FORMULAS!M3): less cover -> 01, same -> 02, more -> 03
    assert_eq!(calc_tiempo_presente("", "30100", "50102"), "01"); // cover fell
    assert_eq!(calc_tiempo_presente("", "50102", "50102"), "02"); // steady
    assert_eq!(calc_tiempo_presente("", "50102", "30100"), "03"); // cover rose
    // '/' in the Nddff digit blocks the fallback
    assert_eq!(calc_tiempo_presente("", "/0102", "50102"), "");
    assert_eq!(calc_tiempo_presente("", "50102", "/0102"), "");
    // No inputs at all
    assert_eq!(calc_tiempo_presente("", "", ""), "");
    // Short ww and empty nddff -> empty
    assert_eq!(calc_tiempo_presente("7", "", ""), "");
    // A single-digit ww still reads as two digits in the T.PRES. column
    assert_eq!(calc_tiempo_presente("71", "", ""), "01");
    assert_eq!(calc_tiempo_presente("79", "", ""), "09");
    // Whitespace inside the group is irrelevant
    assert_eq!(calc_tiempo_presente("7 10 20", "", ""), "10");
}

#[test]
fn prev_hour_chain() {
    assert_eq!(get_prev_hour("06Z"), "03Z");
    assert_eq!(get_prev_hour("09Z"), "06Z");
    assert_eq!(get_prev_hour("12Z"), "09Z");
    assert_eq!(get_prev_hour("15Z"), "12Z");
    assert_eq!(get_prev_hour("18Z"), "15Z");
    assert_eq!(get_prev_hour("21Z"), "18Z");
    // The 00Z wrap-around points back to 21Z
    assert_eq!(get_prev_hour("00Z"), "21Z");
    assert_eq!(get_prev_hour("03Z"), "00Z");
    assert_eq!(get_prev_hour("24Z"), "");
    assert_eq!(get_prev_hour(""), "");
}

// =============================================================================
// realizar_calculos_puro (JSON boundary core)
// =============================================================================

fn request(
    station_id: Option<&str>,
    ts: Option<&str>,
    th: Option<&str>,
    pres_est: Option<&str>,
    p3: Option<&str>,
    p24: Option<&str>,
    correc_alt: Option<&str>,
    ir: Option<&str>,
    ix: Option<&str>,
) -> CalculationRequest {
    CalculationRequest {
        station_id: station_id.map(String::from),
        correc_alt: correc_alt.map(String::from),
        ts: ts.map(String::from),
        th: th.map(String::from),
        pres_est: pres_est.map(String::from),
        p3: p3.map(String::from),
        p24: p24.map(String::from),
        ir: ir.map(String::from),
        ix: ix.map(String::from),
        extra: HashMap::new(),
    }
}

#[test]
fn realizar_calculos_full_corpus_hour() {
    // Values from the real corpus hour (78486, 08122025, 06Z); the resolved
    // station correction 1.6 replaces the oracle's pool lookup.
    let res = realizar_calculos_puro(
        request(
            Some("78486"),
            Some("23.2"),
            Some("22.3"),
            Some("1025.3"),
            Some("1022.3"),
            Some("1024.1"),
            None,
            Some("1"),
            Some("4"),
        ),
        Some("1.6".to_string()),
    );
    assert_eq!(res.tension_vapor, "26.3");
    assert_eq!(res.humedad_relativa, "93");
    assert_eq!(res.punto_rocio, "21.9");
    assert_eq!(res.diferencia, "0.9");
    assert_eq!(res.grupo_1sn_ttt, "10232");
    assert_eq!(res.grupo_2sn_td, "20219");
    assert_eq!(res.grupo_4pppp, "40269");
    assert_eq!(res.grupo_5appp, "53030");
    assert_eq!(res.grupo_58_59_p24, "58012");
    assert_eq!(res.grupo_29uuu, "29093");
    assert_eq!(res.p3_let, "1025.3");
    assert_eq!(res.p24_let, "1025.3");
    assert_eq!(res.p3_dif, "3.0");
    assert_eq!(res.p24_dif, "1.2");
    assert_eq!(res.pres_nmm, "1026.9");
    assert_eq!(res.correc_alt, "1.6");
    assert!(res.include_precipitation);
    assert!(res.include_weather);
    assert!(res.station_info.is_none());
    assert_eq!(res.error_message, "");
}

#[test]
fn realizar_calculos_resolved_correc_alt_wins_over_request() {
    // Oracle priority: station value (here: resolved) first; the request's own
    // correc_alt is only a fallback when the resolved value is empty.
    let res = realizar_calculos_puro(
        request(None, Some("23.2"), None, Some("1010.0"), None, None, Some("9.9"), None, None),
        Some("1.6".to_string()),
    );
    assert_eq!(res.correc_alt, "1.6");
    assert_eq!(res.pres_nmm, "1011.6");

    // Empty resolved value -> request fallback applies
    let res2 = realizar_calculos_puro(
        request(None, None, None, Some("1010.0"), None, None, Some("2.5"), None, None),
        Some("".to_string()),
    );
    assert_eq!(res2.correc_alt, "2.5");
    assert_eq!(res2.pres_nmm, "1012.5");

    // Neither -> empty, no group 4
    let res3 = realizar_calculos_puro(
        request(None, None, None, Some("1010.0"), None, None, None, None, None),
        None,
    );
    assert_eq!(res3.correc_alt, "");
    assert_eq!(res3.pres_nmm, "");
    assert_eq!(res3.grupo_4pppp, "");
}

#[test]
fn realizar_calculos_th_greater_than_ts_is_error() {
    let res = realizar_calculos_puro(
        request(None, Some("20.0"), Some("22.0"), None, None, None, None, None, None),
        None,
    );
    assert_eq!(res.error_message, "Error: Th no puede ser mayor que Ts.");
    assert_eq!(res.tension_vapor, "");
    assert_eq!(res.humedad_relativa, "");
    assert_eq!(res.punto_rocio, "");
    assert_eq!(res.diferencia, "");
    // The temperature group is still emitted for the dry-bulb value
    assert_eq!(res.grupo_1sn_ttt, "10200");
}

#[test]
fn realizar_calculos_th_equal_ts_is_valid() {
    let res = realizar_calculos_puro(
        request(None, Some("20.0"), Some("20.0"), None, None, None, None, None, None),
        None,
    );
    assert_eq!(res.error_message, "");
    assert_eq!(res.diferencia, "0.0");
    let tv = calcular_tension_vapor(20.0, 20.0).unwrap();
    assert_eq!(res.tension_vapor, format!("{:.1}", tv));
}

#[test]
fn realizar_calculos_empty_inputs_all_empty() {
    // Empty-input policy: missing values leave the groups empty, include flags
    // default to true (oracle `unwrap_or(true)`).
    let res = realizar_calculos_puro(request(None, None, None, None, None, None, None, None, None), None);
    assert_eq!(res.tension_vapor, "");
    assert_eq!(res.humedad_relativa, "");
    assert_eq!(res.punto_rocio, "");
    assert_eq!(res.diferencia, "");
    assert_eq!(res.grupo_1sn_ttt, "");
    assert_eq!(res.grupo_2sn_td, "");
    assert_eq!(res.grupo_4pppp, "");
    assert_eq!(res.grupo_5appp, "");
    assert_eq!(res.grupo_58_59_p24, "");
    assert_eq!(res.grupo_29uuu, "");
    assert_eq!(res.p3_let, "");
    assert_eq!(res.p24_let, "");
    assert_eq!(res.p3_dif, "");
    assert_eq!(res.p24_dif, "");
    assert_eq!(res.pres_nmm, "");
    assert_eq!(res.correc_alt, "");
    assert!(res.include_precipitation);
    assert!(res.include_weather);
    assert_eq!(res.error_message, "");
}

#[test]
fn realizar_calculos_ir_ix_policies() {
    let res = realizar_calculos_puro(
        request(None, None, None, None, None, None, None, Some("3"), Some("2")),
        None,
    );
    assert!(!res.include_precipitation);
    assert!(!res.include_weather);

    let res2 = realizar_calculos_puro(
        request(None, None, None, None, None, None, None, Some("2"), Some("1")),
        None,
    );
    assert!(res2.include_precipitation);
    assert!(res2.include_weather);
}

#[test]
fn realizar_calculos_non_numeric_inputs_are_ignored() {
    let res = realizar_calculos_puro(
        request(None, Some("abc"), Some("22.3"), Some("x"), Some("y"), None, Some("z"), None, None),
        None,
    );
    assert_eq!(res.tension_vapor, "");
    assert_eq!(res.p3_let, "");
    assert_eq!(res.pres_nmm, ""); // correc_alt "z" does not parse
    assert_eq!(res.correc_alt, "z");
}

// =============================================================================
// recalculate_derived_fields (single recalculation policy)
// =============================================================================

#[test]
fn recalc_derived_fields_full_hour() {
    let d = recalculate_derived_fields(
        Some("78486"),
        Some("23.2"),
        Some("22.3"),
        Some("1025.3"),
        Some("1022.3"),
        Some("1024.1"),
        None,
        Some("32566"),
        Some("71020"),
        Some("50102"),
        Some("30100"),
        Some("1.6"), // resolved station fallback (F4)
    );
    assert_eq!(d.tension_vapor, "26.3");
    assert_eq!(d.humedad_relativa, "93");
    assert_eq!(d.punto_rocio, "21.9");
    assert_eq!(d.diferencia, "0.9");
    assert_eq!(d.pres_nmm, "1026.9");
    assert_eq!(d.tend_dif, "03.0");
    assert_eq!(d.tend_car, "3");
    assert_eq!(d.visibilidad, "160");
    assert_eq!(d.tiempo_presente, "10");
}

#[test]
fn recalc_derived_fields_th_greater_than_ts_stays_empty() {
    // Oracle guard `th_f <= ts_f`: nothing psychrometric is computed, and the
    // empty-string policy leaves every value empty for the caller to decide.
    let d = recalculate_derived_fields(
        None, Some("20.0"), Some("22.3"), None, None, None, None, None, None, None, None, None,
    );
    assert_eq!(d.tension_vapor, "");
    assert_eq!(d.humedad_relativa, "");
    assert_eq!(d.punto_rocio, "");
    assert_eq!(d.diferencia, "");
}

#[test]
fn recalc_derived_fields_correc_alt_priority() {
    // Non-empty input correc_alt wins over the resolved fallback
    let d = recalculate_derived_fields(
        None, None, None, Some("1010.0"), None, None, Some("2.5"), None, None, None, None,
        Some("1.6"),
    );
    assert_eq!(d.pres_nmm, "1012.5");

    // Empty/blank input -> resolved fallback used
    let d2 = recalculate_derived_fields(
        None, None, None, Some("1010.0"), None, None, Some(""), None, None, None, None, Some("1.6"),
    );
    assert_eq!(d2.pres_nmm, "1011.6");

    let d3 = recalculate_derived_fields(
        None, None, None, Some("1010.0"), None, None, Some("  "), None, None, None, None,
        Some("1.6"),
    );
    assert_eq!(d3.pres_nmm, "1011.6");

    // Neither -> empty
    let d4 = recalculate_derived_fields(
        None, None, None, Some("1010.0"), None, None, None, None, None, None, None, None,
    );
    assert_eq!(d4.pres_nmm, "");
}

#[test]
fn recalc_derived_fields_empty_inputs_all_empty() {
    let d = recalculate_derived_fields(None, None, None, None, None, None, None, None, None, None, None, None);
    assert_eq!(
        serde_json::to_string(&d).unwrap(),
        "{\"tension_vapor\":\"\",\"humedad_relativa\":\"\",\"punto_rocio\":\"\",\"diferencia\":\"\",\"pres_nmm\":\"\",\"tend_dif\":\"\",\"tend_car\":\"\",\"visibilidad\":\"\",\"tiempo_presente\":\"\"}"
    );
}

#[test]
fn recalc_derived_fields_p24_reserved() {
    // p24 does not surface in DerivedFields (oracle: reserved for group 58/59).
    let a = recalculate_derived_fields(None, Some("20.0"), Some("18.0"), Some("1010.0"), None, Some("1000.0"), None, None, None, None, None, None);
    let b = recalculate_derived_fields(None, Some("20.0"), Some("18.0"), Some("1010.0"), None, None, None, None, None, None, None, None);
    assert_eq!(
        serde_json::to_string(&a).unwrap(),
        serde_json::to_string(&b).unwrap()
    );
}

// =============================================================================
// Serialization shape of the boundary
// =============================================================================

#[test]
fn calculation_response_serializes_oracle_field_names() {
    let res = realizar_calculos_puro(request(None, Some("23.2"), None, None, None, None, None, None, None), None);
    let s = serde_json::to_string(&res).unwrap();
    for key in [
        "tension_vapor",
        "humedad_relativa",
        "punto_rocio",
        "diferencia",
        "grupo_1sn_ttt",
        "grupo_2sn_td",
        "grupo_4pppp",
        "grupo_5appp",
        "grupo_58_59_p24",
        "grupo_29uuu",
        "p3_let",
        "p24_let",
        "p3_dif",
        "p24_dif",
        "pres_nmm",
        "correc_alt",
        "include_precipitation",
        "include_weather",
        "error_message",
    ] {
        assert!(s.contains(&format!("\"{}\"", key)), "missing key {}", key);
    }
    // station_info present (null) even when there is no echo — oracle serde shape
    assert!(s.contains("\"station_info\":null"));

    // With echo: object rides through (serde_json Map re-serializes keys sorted:
    // BTree order, no preserve_order feature — documented oracle deviation)
    let raw = r#"{"ts":"23.2","station_info":{"id":"78486","ch":"1.6"}}"#;
    let data: CalculationRequest = serde_json::from_str(raw).unwrap();
    let res = realizar_calculos_puro(data, Some("1.6".to_string()));
    let s2 = serde_json::to_string(&res).unwrap();
    assert!(s2.contains("\"station_info\":{\"ch\":\"1.6\",\"id\":\"78486\"}"));
}

#[test]
fn calculation_request_flattens_unknown_keys_for_echo() {
    let raw = r#"{"station_id":"78486","ts":"23.2","station_info":{"id":"78486","ch":"1.6","name":"78486"}}"#;
    let data: CalculationRequest = serde_json::from_str(raw).unwrap();
    assert_eq!(data.station_id.as_deref(), Some("78486"));
    assert_eq!(data.extra.get("station_info").unwrap().get("ch").unwrap().as_str(), Some("1.6"));

    // Echo rides back into the response when the resolved correction is provided
    let res = realizar_calculos_puro(data, Some("1.6".to_string()));
    let out = serde_json::to_value(&res).unwrap();
    assert_eq!(out.get("station_info").unwrap().get("ch").unwrap().as_str(), Some("1.6"));
}
