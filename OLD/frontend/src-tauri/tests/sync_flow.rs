mod helpers;

use app_lib::infrastructure::storage::sync_queue::{
    enqueue_pending, get_sync_status_core, retry_pending_sync_core, SyncRow,
};
use helpers::create_test_pool;
use std::fs;
use std::path::PathBuf;

fn temp_dir(tag: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "arca_sync_{}_{}_{}",
        tag,
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&dir).expect("temp dir");
    dir
}

/// relative_path con el módulo incluido; los roots offline/online no lo llevan.
fn rel(station: &str, year: &str, month: &str, file: &str) -> String {
    format!("synop/{}/{}/{}/{}", station, year, month, file)
}

/// Raíz online "rota": es un archivo, no un directorio (create_dir_all falla).
fn raiz_rota() -> PathBuf {
    let root = temp_dir("broken_root_raiz");
    let f = root.join("raiz");
    fs::write(&f, "no soy un directorio").expect("blocker");
    f
}

/// P3.1 — tabla de migración presente y encolable.
#[test]
fn sync_pending_table_exists_y_sirve() {
    let pool = create_test_pool();
    let conn = pool.get().expect("conn");

    let row = SyncRow {
        module: "synop".to_string(),
        station_code: "78486".to_string(),
        relative_path: rel("78486", "2026", "08", "7848615082026.json"),
        source_path: "/todavia/no/archivo.json".to_string(),
    };
    enqueue_pending(&conn, &row).expect("enqueue debe funcionar sobre la migración");

    let status = get_sync_status_core(&conn).expect("status debe funcionar");
    assert_eq!(status.pending, 1, "una fila pendiente tras enqueue");
    assert_eq!(status.synced, 0);
}

/// P3.3 — roundtrip: raíz rota registra el error real y queda pendiente;
/// cuando la raíz vuelve, "Reintentar ahora" (force) sube y marca synced;
/// otro force no repite nada.
#[test]
fn retry_roundtrip_encola_sub_marca_y_es_idempotente() {
    let pool = create_test_pool();
    let conn = pool.get().expect("conn");

    let base = temp_dir("offline");
    let rel_path = rel("78486", "2026", "08", "7848615082026.json");
    let source = base.join(&rel_path);
    fs::create_dir_all(source.parent().unwrap()).expect("dirs offline");
    let contenido = r#"{"horas":{"00Z":{"ts":"30.0"}}}"#;
    fs::write(&source, contenido).expect("archivo offline");

    let row = SyncRow {
        module: "synop".to_string(),
        station_code: "78486".to_string(),
        relative_path: rel_path.clone(),
        source_path: source.to_string_lossy().to_string(),
    };
    enqueue_pending(&conn, &row).expect("enqueue");

    // 1) retry con la raíz online ROTA: intenta, falla, queda pendiente con error
    let rota = raiz_rota();
    let failed = retry_pending_sync_core(
        &conn,
        base.to_string_lossy().as_ref(),
        rota.to_string_lossy().as_ref(),
        false,
    )
    .expect("retry con raíz rota no debe paniquear");
    assert_eq!(failed.attempted, 1, "debe intentar la única fila");
    assert_eq!(failed.uploaded, 0, "no puede subir con raíz rota");
    assert!(
        failed.last_error.is_some(),
        "debe registrar el error real: {:?}",
        failed.last_error
    );

    let status = get_sync_status_core(&conn).expect("status");
    assert_eq!(status.pending, 1, "sigue pendiente");
    assert_eq!(status.synced, 0);
    assert!(
        status.last_errors.iter().any(|e| !e.detail.is_empty()),
        "el status debe exponer los errores últimos"
    );

    // 2) la raíz online vuelve: retry forzado (botón "Reintentar ahora") sube
    let ok_root = temp_dir("online_ok");
    let done = retry_pending_sync_core(
        &conn,
        base.to_string_lossy().as_ref(),
        ok_root.to_string_lossy().as_ref(),
        true,
    )
    .expect("retry con raíz disponible debe funcionar");
    assert_eq!(done.uploaded, 1, "debe subir el archivo");
    assert_eq!(done.marked_synced, 1, "debe marcar la fila como synced");

    let online_file = ok_root.join(&rel_path);
    assert!(online_file.exists(), "el archivo debe existir online");
    assert_eq!(
        fs::read_to_string(&online_file).unwrap(),
        contenido,
        "contenido online = contenido offline"
    );

    // 3) idempotente: otra pasada no tiene nada que hacer
    let again = retry_pending_sync_core(
        &conn,
        base.to_string_lossy().as_ref(),
        ok_root.to_string_lossy().as_ref(),
        true,
    )
    .expect("segunda pasada debe funcionar");
    assert_eq!(again.attempted, 0, "sin pendientes no repite");
    let status2 = get_sync_status_core(&conn).expect("status");
    assert_eq!(status2.pending, 0, "sin pendientes");
    assert_eq!(status2.synced, 1, "una subida registrada");
    assert!(
        online_file.exists(),
        "la segunda pasada no debe borrar lo subido"
    );
}

/// P3.3 — backoff honesto: una fila con attempts=1 y last_attempt hace 1 min
/// (dentro de 2^1 min) NO se re-intenta en pasada normal.
#[test]
fn retry_respeta_backoff_por_attempts() {
    let pool = create_test_pool();
    let conn = pool.get().expect("conn");

    let base = temp_dir("offline_backoff");
    let rel_path = rel("78485", "2026", "08", "7848515082026.json");
    let source = base.join(&rel_path);
    fs::create_dir_all(source.parent().unwrap()).expect("dirs");
    fs::write(&source, r#"{"a":1}"#).expect("archivo");

    let row = SyncRow {
        module: "synop".to_string(),
        station_code: "78485".to_string(),
        relative_path: rel_path,
        source_path: source.to_string_lossy().to_string(),
    };
    enqueue_pending(&conn, &row).expect("enqueue");

    // primer intento falla (raíz rota) → attempts=1, last_attempt = ahora
    let rota = raiz_rota();
    retry_pending_sync_core(
        &conn,
        base.to_string_lossy().as_ref(),
        rota.to_string_lossy().as_ref(),
        false,
    )
    .expect("primer intento (fallido) registrado");

    // pasada normal apenas 1 min después (2^1 = 2 min de ventana) → salta
    let good = temp_dir("backoff_online");
    let skipped = retry_pending_sync_core(
        &conn,
        base.to_string_lossy().as_ref(),
        good.to_string_lossy().as_ref(),
        false,
    )
    .expect("retry con backoff no debe fallar");
    assert_eq!(
        skipped.attempted, 0,
        "el backoff debe saltar la fila con last_attempt recién (attempts=1)"
    );

    let status = get_sync_status_core(&conn).expect("status");
    assert_eq!(status.pending, 1, "la fila sigue pendiente para luego");
}
