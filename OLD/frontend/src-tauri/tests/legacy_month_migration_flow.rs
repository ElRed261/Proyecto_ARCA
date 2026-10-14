mod helpers;

use app_lib::audit::service::{migrate_legacy_month_dirs_core, months_core};
use helpers::create_test_pool;
use std::fs;
use std::path::Path;

fn crear_enero(base: &Path) -> std::path::PathBuf {
    let dir = base.join("78486").join("2025").join("enero");
    fs::create_dir_all(&dir).expect("debe crear la carpeta enero");
    fs::write(dir.join("7848601012025.json"), r#"{"horas":{}}"#)
        .expect("debe escribir el fixture");
    dir
}

#[test]
fn browse_meses_es_pura_lectura_sin_renombrar_nada() {
    with_temp_dir(|base| {
        let enero = crear_enero(base);

        let _pool = create_test_pool();
        let meses = months_core(base, "78486", "2025").expect("browse debe funcionar");

        assert_eq!(meses, vec!["01".to_string()], "'enero' debe listarse como 01");

        // Pure read: el dir legacy sigue intacto y NO se creó el numérico
        assert!(enero.exists(), "la lectura NO debe renombrar carpetas");
        assert!(
            !base.join("78486").join("2025").join("01").exists(),
            "la lectura NO debe crear la carpeta 01"
        );
    });
}

#[test]
fn migrate_one_shot_mueve_y_luego_resulta_cero() {
    with_temp_dir(|base| {
        let enero = crear_enero(base);
        let _pool = create_test_pool();

        // 1) migración inicial: mueve enero -> 01 con el archivo adentro
        let stats = migrate_legacy_month_dirs_core(base)
            .expect("la primera migración debe ejecutarse");
        assert!(stats.renamed_dirs >= 1, "debe reportar carpetas renombradas");
        assert!(
            !enero.exists(),
            "el dir legacy 'enero' no debe quedar tras la migración"
        );
        let destino = base.join("78486").join("2025").join("01");
        assert!(
            destino.join("7848601012025.json").exists(),
            "el archivo debe haberse movido dentro de 01/, no perdido"
        );

        // 2) segundo run: idempotente, sin cambios
        let stats2 = migrate_legacy_month_dirs_core(base)
            .expect("la segunda migración debe ejecutarse sin error");
        assert_eq!(
            stats2.renamed_dirs, 0,
            "migración repetida no debe renombrar nada"
        );
        assert_eq!(
            stats2.moved_files, 0,
            "migración repetida no debe mover archivos"
        );

        // el archivo sigue donde quedó
        assert!(destino.join("7848601012025.json").exists());
    });
}

#[test]
fn migrate_fusiona_con_dir_numerico_existente_sin_perder_archivos() {
    with_temp_dir(|base| {
        let enero = crear_enero(base);
        // ya existe 01 con otro archivo
        let existing = base.join("78486").join("2025").join("01");
        fs::create_dir_all(&existing).unwrap();
        fs::write(existing.join("7848602012025.json"), "{}").unwrap();

        let _pool = create_test_pool();
        let stats = migrate_legacy_month_dirs_core(base).expect("fusión debe funcionar");

        assert!(
            existing.join("7848601012025.json").exists(),
            "archivo de enero debe aparecer en 01/"
        );
        assert!(
            existing.join("7848602012025.json").exists(),
            "el archivo preexistente NO debe perderse"
        );
        assert!(
            !enero.exists(),
            "carpeta legacy vacía debe eliminarse tras fusionar"
        );
        assert!(stats.moved_files >= 1);
    });
}

fn with_temp_dir(f: impl FnOnce(&Path)) {
    let dir = std::env::temp_dir().join(format!(
        "arca_monthtest_{}_{}",
        std::process::id(),
        chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
    ));
    fs::create_dir_all(&dir).expect("temp dir");
    let res = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| f(&dir)));
    fs::remove_dir_all(&dir).ok();
    if let Err(e) = res {
        std::panic::resume_unwind(e);
    }
}
