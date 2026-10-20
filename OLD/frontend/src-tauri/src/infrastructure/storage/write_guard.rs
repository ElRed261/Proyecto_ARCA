//! write_guard — P2: guardián de escritura para los JSON de guardado.
//!
//! Resuelve el lost-update de P1 (read-modify-write sin lock):
//! - `FileLock::acquire`: lock exclusivo por archivo (O_EXCL) con timeout y
//!   robo de lockfiles huérfanos (stale por mtime).
//! - `merge_json_file`: lock → leer → mutar → escribir (atomic_write con
//!   fsync). Único camino de mutación para synoptic/CLI saves.

use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

/// P2.3 — versión de esquema de los documentos de guardado. Toda escritura la
/// inyecta a nivel raíz; los lectores pueden migrar versiones viejas después.
pub const SCHEMA_VERSION: i64 = 1;

/// P2.5 — error de guardado estructurado: {stage, path, detail}.
/// stage ∈ {lock, read, logic, write, validate, dirs}; siempre serializable a JSON.
#[derive(Debug, serde::Serialize)]
pub struct SaveErr {
    pub stage: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    pub detail: String,
}

impl std::fmt::Display for SaveErr {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.to_json_string())
    }
}

impl SaveErr {
    pub fn new(stage: &str, path: Option<&Path>, detail: impl std::fmt::Display) -> Self {
        Self {
            stage: stage.to_string(),
            path: path.map(|p| p.to_string_lossy().to_string()),
            detail: detail.to_string(),
        }
    }

    pub fn to_json_string(&self) -> String {
        serde_json::to_string(self).unwrap_or_else(|_| {
            format!("{{\"stage\":\"{}\",\"detail\":\"{}\"}}", self.stage, self.detail)
        })
    }
}

const LOCK_POLL: Duration = Duration::from_millis(5);
const LOCK_STALE_DEFAULT: Duration = Duration::from_secs(30);

/// Lock exclusivo de corto plazo sobre un archivo de datos.
/// El lockfile se crea con O_EXCL (atómico) y contiene pid+tid para diagnóstico.
#[derive(Debug)]
pub struct FileLock {
    path: PathBuf,
}

impl FileLock {
    /// Adquiere el lock o falla al agotar el timeout. Steal si el lockfile es
    /// más viejo que `stale_after` (proceso anterior murió sin soltarlo).
    pub fn acquire(target: &Path, timeout: Duration, stale_after: Duration) -> Result<Self, String> {
        let lock_path = lockfile_for(target);
        let deadline = Instant::now() + timeout;

        loop {
            match OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&lock_path)
            {
                Ok(mut f) => {
                    let _ = writeln!(
                        f,
                        "pid={} tid={:?}",
                        std::process::id(),
                        std::thread::current().id()
                    );
                    return Ok(Self { path: lock_path });
                }
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                    // stale: mtime viejo → lock huérfano (proceso muerto) → robarlo
                    if let Ok(meta) = fs::metadata(&lock_path) {
                        if let Ok(modified) = meta.modified() {
                            if let Ok(age) = std::time::SystemTime::now().duration_since(modified) {
                                if age > stale_after {
                                    let _ = fs::remove_file(&lock_path);
                                }
                            }
                        }
                    }
                    if Instant::now() >= deadline {
                        return Err(format!(
                            "timeout esperando lock {:?} (timeout={:?})",
                            lock_path, timeout
                        ));
                    }
                    std::thread::sleep(LOCK_POLL);
                }
                Err(e) => {
                    return Err(format!("error creando lockfile {:?}: {}", lock_path, e));
                }
            }
        }
    }

    /// Adquiere con el timeout default (5s) y detección de stale default.
    pub fn acquire_default(target: &Path) -> Result<Self, String> {
        Self::acquire(target, Duration::from_secs(5), LOCK_STALE_DEFAULT)
    }
}

impl Drop for FileLock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

/// P2.1 — atomic_write con fsync: escribe al temp, fuerza sync_all del
/// contenido ANTES del rename, y sincroniza el dir padre (unix best-effort).
/// Garantía honesta: el crash-power no puede dejar un archivo con contenido
/// vacío/mixto en FS que respetan fsync; NTFS aplica el mismo patrón (write+flush+rename).
pub fn atomic_write_sync(path: &Path, content: &str) -> std::io::Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let file_name = path.file_name().and_then(|s| s.to_str()).unwrap_or("tmp");
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let tmp_name = format!(".{}.tmp.{}-{}", file_name, std::process::id(), nanos);
    let tmp_path = parent.join(tmp_name);

    let res = (|| {
        let mut f = File::create(&tmp_path)?;
        f.write_all(content.as_bytes())?;
        // fuerza el contenido al almacenamiento antes del rename
        f.sync_all()?;
        drop(f);

        fs::rename(&tmp_path, path)?;
        // sync del dir padre (unix only; en Windows el rename es lo que importa)
        #[cfg(unix)]
        {
            if let Ok(dir) = File::open(parent) {
                let _ = dir.sync_all();
            }
        }
        Ok(())
    })();
    if res.is_err() {
        let _ = fs::remove_file(&tmp_path);
    }
    res
}

/// lockfile para un target: `<dir>/.<name>.json.lock` (dot-file: no es .json
/// así que los lectores glob `*.json` nunca lo ven).
fn lockfile_for(target: &Path) -> PathBuf {
    let name = target
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("arca");
    target
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join(format!(".{}.lock", name))
}

/// Único camino de mutación read-modify-write para un JSON de guardado.
/// P2.2: read-modify-write BAJO lock — final siempre consistente.
///
/// `mutate` recibe el documento completo (objeto nuevo si el archivo no existe)
/// y devuelve Err para abortar sin escribir nada.
pub fn merge_json_file<F>(target: &Path, mutate: F) -> Result<serde_json::Value, SaveErr>
where
    F: FnOnce(&mut serde_json::Value) -> Result<(), String>,
{
    let _lock = FileLock::acquire_default(target)
        .map_err(|e| SaveErr::new("lock", Some(target), e))?;

    let mut doc: serde_json::Value = if target.exists() {
        let raw = fs::read_to_string(target)
            .map_err(|e| SaveErr::new("read", Some(target), e))?;
        serde_json::from_str(&raw)
            .map_err(|e| SaveErr::new("read", Some(target), format!("JSON corrupto: {}", e)))?
    } else {
        serde_json::json!({})
    };

    mutate(&mut doc).map_err(|e| SaveErr::new("logic", Some(target), e))?;

    // P2.3: toda escritura inyecta schema_version a nivel raíz
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "schema_version".to_string(),
            serde_json::json!(SCHEMA_VERSION),
        );
    }

    let pretty = serde_json::to_string_pretty(&doc)
        .map_err(|e| SaveErr::new("write", Some(target), e))?;
    atomic_write_sync(target, &pretty).map_err(|e| SaveErr::new("write", Some(target), e))?;

    Ok(doc)
}

#[cfg(test)]
mod write_guard_tests {
    use super::*;

    fn temp_target(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "arca_wg_{}_{}_{}",
            tag,
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        fs::create_dir_all(&dir).expect("temp dir");
        dir.join("target.json")
    }

    #[test]
    fn lock_es_exclusivo_segundo_please_falla() {
        let target = temp_target("exclusive");
        let _g1 = FileLock::acquire(&target, Duration::from_secs(1), Duration::from_secs(30))
            .expect("el primer acquire debe pasar");
        let err = FileLock::acquire(&target, Duration::from_millis(50), Duration::from_secs(30))
            .expect_err("el segundo acquire CONCURRENTE debe fallar por timeout");
        assert!(err.contains("timeout"), "fue: {}", err);
    }

    #[test]
    fn lock_se_libera_al_drop() {
        let target = temp_target("release");
        {
            let _g = FileLock::acquire(&target, Duration::from_secs(1), Duration::from_secs(30))
                .expect("primer acquire");
        } // drop libera
        FileLock::acquire(&target, Duration::from_secs(1), Duration::from_secs(30))
            .expect("tras drop, el lock debe poder adquirir de nuevo");
    }

    #[test]
    fn lock_roba_lockfile_huerfano_viejo() {
        let target = temp_target("stale");
        let lock_path = lockfile_for(&target);
        fs::write(&lock_path, "pid=1").expect("crear lock huérfano");
        // envejecer el lock Artificially: mtime viejo
        use std::time::UNIX_EPOCH;
        let old = UNIX_EPOCH + Duration::from_secs(
            std::time::SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs() - 120,
        );
        filetime::set_file_mtime(&lock_path, filetime::FileTime::from_system_time(old))
            .expect("poder fijar mtime viejo");

        FileLock::acquire(&target, Duration::from_secs(2), Duration::from_secs(30))
            .expect("un lock huérfano (>30s) debe poder robarse");
    }

    #[test]
    fn merge_json_file_inyecta_schema_version() {
        let target = temp_target("schema");
        let out = merge_json_file(&target, |doc| {
            doc.as_object_mut()
                .unwrap()
                .insert("x".into(), serde_json::json!(1));
            Ok(())
        })
        .expect("merge debe funcionar");
        assert_eq!(out.get("schema_version"), Some(&serde_json::json!(SCHEMA_VERSION)));
        let raw = fs::read_to_string(&target).unwrap();
        let doc: serde_json::Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(doc.get("schema_version"), Some(&serde_json::json!(SCHEMA_VERSION)));
    }

    #[test]
    fn merge_json_file_carrera_determinista_no_pierde_ediciones() {
        // Manufacture the lost-update:both threads read el mismo contenido viejo
        // (sleep en la sección crítica) y escriben su propia clave.
        // SIN lock: el último writer pisa la clave del otro (determinista).
        // CON merge_json_file (lock): ambas claves sobreviven.
        let target = temp_target("race");

        let t1 = {
            let target = target.clone();
            std::thread::spawn(move || {
                merge_json_file(&target, |doc| {
                    std::thread::sleep(Duration::from_millis(30)); // ventana de carrera
                    doc.as_object_mut().unwrap().insert("ts1".into(), serde_json::json!("a"));
                    Ok(())
                })
            })
        };
        let t2_target = target.clone();
        let t2 = std::thread::spawn(move || {
            merge_json_file(&t2_target, |doc| {
                std::thread::sleep(Duration::from_millis(30));
                doc.as_object_mut().unwrap().insert("ts2".into(), serde_json::json!("b"));
                Ok(())
            })
        });

        t1.join().unwrap().expect("t1 ok");
        t2.join().unwrap().expect("t2 ok");

        let raw = fs::read_to_string(&target).unwrap();
        let doc: serde_json::Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(doc.get("ts1"), Some(&serde_json::json!("a")), "la edición del hilo 1 NO debe perderse");
        assert_eq!(doc.get("ts2"), Some(&serde_json::json!("b")), "la edición del hilo 2 NO debe perderse");
    }

    #[test]
    fn merge_json_file_aborta_sin_escribir_si_mutate_falla() {
        let target = temp_target("abort");
        fs::write(&target, r#"{"previo": true}"#).unwrap();

        let err = merge_json_file(&target, |_doc| Err("regla de negocio violada".to_string()))
            .expect_err("el abort debe propagarse");
        let err_json = err.to_json_string();
        assert!(err_json.contains("regla"), "fue: {}", err_json);
        assert_eq!(err.stage, "logic", "el abort de la regla debe marcar stage logic");

        let raw = fs::read_to_string(&target).unwrap();
        assert!(raw.contains("previo"), "el archivo debe quedar intacto tras abort");
        let lock_leftovers: Vec<_> = std::fs::read_dir(target.parent().unwrap())
            .unwrap()
            .flatten()
            .filter(|e| e.file_name().to_string_lossy().ends_with(".lock"))
            .collect();
        assert!(lock_leftovers.is_empty(), "no deben quedar lockfiles huérfanos");
    }

    // filetime para el test de stale — depende de crate dev-dependency
    #[test]
    fn atomic_write_sync_roundtrip_y_temp_cleanup() {
        let target = temp_target("atomic");
        atomic_write_sync(&target, r#"{"ok":1}"#).expect("escritura atómica");
        assert_eq!(fs::read_to_string(&target).unwrap(), r#"{"ok":1}"#);
        // no dejan temp files colgados
        let temps: Vec<_> = target
            .parent()
            .unwrap()
            .read_dir()
            .unwrap()
            .flatten()
            .filter(|e| e.file_name().to_string_lossy().contains(".tmp."))
            .collect();
        assert!(temps.is_empty());
    }
}
