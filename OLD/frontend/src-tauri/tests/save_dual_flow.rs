mod helpers;

use app_lib::infrastructure::storage::sync_queue::{
    enqueue_pending, emit_after_save_core, get_sync_status_core, SyncRow,
};
use helpers::create_test_pool;
use std::fs;
use std::path::PathBuf;

fn temp_dir(tag: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "arca_dual_{}_{}_{}",
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

fn archivo_offline(base: &std::path::Path) -> PathBuf {
    let rel = std::path::Path::new("synop/78451/2026/08/7845115082026.json");
    let f = base.join(rel);
    fs::create_dir_all(f.parent().unwrap()).expect("dirs offline");
    fs::write(&f, r#"{"horas":{"00Z":{"ts":"30.0"}}}"#).expect("archivo offline");
    f
}

fn emit_args<'a>(
    base: &'a std::path::Path,
    online: Option<&'a PathBuf>,
    conn: &'a rusqlite::Connection,
) -> (&'a rusqlite::Connection, Option<&'a std::path::Path>, Option<&'a std::path::Path>, &'static str, &'static str, &'static str, &'static str, &'static str) {
    (
        conn,
        Some(base),
        online.map(|p| p.as_path()),
        "synop",
        "78451",
        "2026",
        "08",
        "7845115082026.json",
    )
}

#[test]
fn emit_con_online_disponible_copia_y_no_encola() {
    let pool = create_test_pool();
    let conn = pool.get().expect("conn");
    let base = temp_dir("off_ok");
    let online = temp_dir("ok");
    archivo_offline(&base);

    let (conn, off, on, m, st, y, mo, fnm) = emit_args(&base, Some(&online), &conn);
    let res = emit_after_save_core(conn, off, on, m, st, y, mo, fnm);
    assert!(res.configured, "online configurado");
    assert!(res.saved_online, "debe copiar a la raíz online");
    assert!(res.error.is_none());

    let online_file = online
        .join("synop")
        .join("78451")
        .join("2026")
        .join("08")
        .join("7845115082026.json");
    assert!(online_file.exists(), "debe existir en la raíz online");
    let status = get_sync_status_core(conn).expect("status");
    assert_eq!(status.pending, 0, "éxito no encola");
}

#[test]
fn emit_con_raiz_rota_deja_offline_intacto_y_encola() {
    let pool = create_test_pool();
    let conn = pool.get().expect("conn");
    let base = temp_dir("off_broken");
    let source = archivo_offline(&base);
    let contenido_offline = fs::read_to_string(&source).unwrap();

    // raíz online que es un FILE (no un dir) → create_dir_all falla
    let broken_root = temp_dir("broken");
    let blocker = broken_root.join("raiz");
    fs::write(&blocker, "x").expect("blocker");

    let (conn, off, on, m, st, y, mo, fnm) = emit_args(&base, Some(&blocker), &conn);
    let res = emit_after_save_core(conn, off, on, m, st, y, mo, fnm);
    assert!(res.configured);
    assert!(!res.saved_online, "no puede guardar online con raíz rota");
    assert!(res.error.is_some(), "debe registrar el error real");

    let status = get_sync_status_core(conn).expect("status");
    assert_eq!(status.pending, 1, "fallo de emisión debe encolar");

    // el OFFLINE no se toca: offline-first
    assert_eq!(
        fs::read_to_string(&source).unwrap(),
        contenido_offline,
        "el archivo offline debe quedar intacto"
    );
}

#[test]
fn emit_desactivado_es_noop() {
    let pool = create_test_pool();
    let conn = pool.get().expect("conn");
    let base = temp_dir("off_none");
    archivo_offline(&base);

    let (conn, off, _on, m, st, y, mo, fnm) = emit_args(&base, None, &conn);
    let res = emit_after_save_core(conn, off, None, m, st, y, mo, fnm);
    assert!(!res.configured, "sin online_root configurado");
    assert!(!res.saved_online);
    assert!(res.error.is_none());
    let status = get_sync_status_core(conn).expect("status");
    assert_eq!(status.pending, 0);
}

#[test]
fn emit_exitoso_marca_synced_una_fila_pendiente() {
    let pool = create_test_pool();
    let conn = pool.get().expect("conn");
    let base = temp_dir("off_pending");
    let source = archivo_offline(&base);
    let online = temp_dir("pending_online");

    // fila pendiente pre-existente (del save con Drive caído)
    enqueue_pending(
        &conn,
        &SyncRow {
            module: "synop".to_string(),
            station_code: "78451".to_string(),
            relative_path: "synop/78451/2026/08/7845115082026.json".to_string(),
            source_path: source.to_string_lossy().to_string(),
        },
    )
    .expect("enqueue previo");

    let (conn, off, on, m, st, y, mo, fnm) = emit_args(&base, Some(&online), &conn);
    let res = emit_after_save_core(conn, off, on, m, st, y, mo, fnm);
    assert!(res.saved_online);

    let status = get_sync_status_core(conn).expect("status");
    assert_eq!(status.pending, 0, "la fila preexistente queda sincronizada");
    assert_eq!(status.synced, 1, "registrada como synced");
}
