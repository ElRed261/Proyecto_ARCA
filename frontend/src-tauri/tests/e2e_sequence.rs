mod helpers;

use app_lib::audit::service::load_observation_with_audit_core;
use app_lib::calculations::{realizar_calculos, CalculationRequest};
use app_lib::json_handler::cli::load_cli3074_json_core;
use app_lib::json_handler::synoptic::{get_observation_core, save_observation_json_core};
use app_lib::monthly_summary::commands::ms_load_station_month_core;
use helpers::{create_test_pool, with_arca_dir, TestUser};
use serde_json::{json, Value};

const STATION: &str = "78451"; // estación sembrada por las migraciones (Monte Cristi)
const FECHA: &str = "2026-08-15";

fn observaciones_dia() -> Value {
    let mut horas = serde_json::Map::new();
    for hora in ["00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"] {
        horas.insert(
            hora.to_string(),
            json!({
                "ts": "30.0",
                "th": "20.0",
                "pres_est": "1016.0",
                "p3": "1012.0",
                "p24": "1010.0",
                "viento_dir": "90.0",
                "viento_vel": "5.0",
                "t_max": "30.5",
                "t_min": "22.0",
                "meteo_2_1": "12023",
                "meteo_4_irixhvv": "001",
                "meteo_4_1": "31018",
                "meteo_4_6": "02//",
            }),
        );
    }
    Value::Object(horas)
}

fn cli3074_embebido() -> Value {
    json!({
        "horas": {
            "1": {
                "pres_est": "1013.5",
                "p3": "1010.0",
                "meteo_4_irixhvv": "001",
                "meteo_4_6": "02//",
                "meteo_4_1": "31018",
            }
        }
    })
}

#[test]
fn secuencia_completa_login_guardado_carga_calculo_resumen_auditoria() {
    let pool = create_test_pool();

    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        let summary_dir = base.join("sumario");

        // 1. Crear usuario admin
        let admin = TestUser::create(&pool, "e2e_admin@arca.test", "Clave123!", "admin");

        // 2. Login
        let login = app_lib::auth::login_user_logic(&admin.repo, &admin.session_store, &admin.email, &admin.password)
            .expect("login del admin no debe fallar");
        assert!(
            admin.session_store.validate_session(&login.access_token).is_ok(),
            "el token de login debe ser válido"
        );

        // 3. Guardar día sinóptico con datos reales de temperatura/presión + CLI embebido
        let saved = save_observation_json_core(
            &synop_base,
            STATION.to_string(),
            FECHA.to_string(),
            observaciones_dia(),
            Some("Juan Perez".to_string()),
            Some(cli3074_embebido()),
            None,
            None,
            |_| None,
        )
        .expect("guardar la observación no debe fallar");
        assert_eq!(saved.get("success").map(|s| s.as_str()).unwrap_or(""), "true", "guardado debe reportar éxito");

        // 4. Cargar la observación y verificar round-trip
        let loaded = get_observation_core(&synop_base, STATION.to_string(), FECHA.to_string())
            .expect("cargar la observación no debe fallar");
        let hora_12 = loaded.get("12Z").and_then(|h| h.as_object()).expect("la hora 12Z debe estar presente");
        assert_eq!(hora_12.get("ts").and_then(|v| v.as_str()), Some("30.0"), "round-trip del ts");
        assert_eq!(hora_12.get("pres_est").and_then(|v| v.as_str()), Some("1016.0"), "round-trip de pres_est");

        // 5. Cálculos con el pool real (estación 78451 aporta corrección de altura)
        let req = CalculationRequest {
            station_id: Some(STATION.to_string()),
            correc_alt: None,
            ts: Some("30.0".to_string()),
            th: Some("20.0".to_string()),
            pres_est: Some("1016.0".to_string()),
            p3: Some("1012.0".to_string()),
            p24: None,
            ir: None,
            ix: None,
        };
        let calc = realizar_calculos(&pool, req);
        assert_eq!(calc.pres_nmm, "1016.5", "presión al nivel del mar = pres_est + corrección 0.5");
        assert_eq!(calc.diferencia, "10.0", "diferencia térmica Ts - Th");
        assert!(!calc.punto_rocio.is_empty(), "debe calcularse punto de rocío");
        assert!(!calc.humedad_relativa.is_empty(), "debe calcularse humedad relativa");

        // 6. Carga CLI 3074 con los datos embebidos en el layout
        let cli = load_cli3074_json_core(&synop_base, STATION, FECHA)
            .expect("cargar CLI 3074 no debe fallar");
        let cli_hora = cli.get("horas").and_then(|h| h.get("1")).and_then(|h| h.as_object());
        assert_eq!(
            cli_hora.and_then(|h| h.get("tend_dif")).and_then(|v| v.as_str()),
            Some("03.5"),
            "CLI 3074 debe exponer la diferencia calculada"
        );

        // 7. Resumen mensual con los días JSON reales
        let doc = ms_load_station_month_core(&synop_base, &summary_dir, STATION, 2026, 8)
            .expect("generar resumen mensual no debe fallar");
        assert_eq!(doc.meta.periodo, "08/2026", "periodo del resumen");
        assert_eq!(doc.meta.total_dias, 1, "un día guardado debe dar un día en el resumen");
        assert_eq!(doc.datos[0].t_max, Some(30.5), "Tmax debe reflejarse en el KPI del resumen");
        assert_eq!(doc.datos[0].dias, FECHA, "el resumen remite a la fecha del día");

        // 8. Auditoría: cargar con marcas y correcciones, recalcula campos
        let audit = load_observation_with_audit_core(&pool, &synop_base, STATION, FECHA)
            .expect("cargar observación con auditoría no debe fallar");
        let audit_hora = audit.observation.get("12Z").and_then(|h| h.as_object()).expect("horas en auditoría");
        assert_eq!(
            audit_hora.get("pres_nmm").and_then(|v| v.as_str()),
            Some("1016.5"),
            "auditoría debe recalcular pres_nmm"
        );
        assert!(
            audit.error_marks.is_empty(),
            "con observador presente no deben generarse marcas de error automáticas"
        );
    });
}