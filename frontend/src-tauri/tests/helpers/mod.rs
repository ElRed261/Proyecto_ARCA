// Cada test es su propia crate; los helpers no usados por un test puntual
// serían dead_code, así que el módulo completo lo permite.
#![allow(dead_code)]

use app_lib::adapters::sqlite_user_repository::SqliteUserRepository;
use app_lib::auth::{self, LoginResponse, SessionStore};
use app_lib::db::{get_migrations, DbPool};
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

static COUNTER: AtomicU64 = AtomicU64::new(0);

fn unique_suffix() -> String {
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("reloj del sistema válido")
        .as_nanos();
    // contador + nanos: los tests corren en paralelo y el id de proceso se repite
    format!("{}_{}_{}", std::process::id(), nanos, n)
}

/// Pool SQLite real sobre un archivo en temp dir, con migraciones aplicadas.
pub fn create_test_pool() -> DbPool {
    let db_path = std::env::temp_dir().join(format!("arca_test_{}.db", unique_suffix()));
    let manager = SqliteConnectionManager::file(&db_path);
    let pool = Pool::new(manager).expect("no se pudo crear el pool de test");
    let mut conn = pool.get().expect("no se pudo obtener conexión de test");
    conn.pragma_update(None, "journal_mode", "wal")
        .expect("no se pudo activar WAL");
    conn.pragma_update(None, "foreign_keys", "ON")
        .expect("no se pudo activar foreign_keys");
    get_migrations()
        .to_latest(&mut conn)
        .expect("no se pudieron aplicar las migraciones");
    drop(conn);
    pool
}

pub fn temp_base_dir() -> PathBuf {
    let dir = std::env::temp_dir().join(format!("arca_fs_{}", unique_suffix()));
    std::fs::create_dir_all(&dir).expect("no se pudo crear el dir temporal");
    dir
}

/// Setea ARCA_BASE_DIR a un dir temporal, corre el closure y limpia la env var
/// al final (incluso si el closure panicca).
// ponytail: los cores de test reciben base_dir explícito, así que la carrera de
// env var entre tests en paralelo no afecta (nadie lee ARCA_BASE_DIR en cores).
pub fn with_arca_dir(f: impl FnOnce(&Path)) {
    let dir = temp_base_dir();
    std::env::set_var("ARCA_BASE_DIR", &dir);
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| f(&dir)));
    std::env::remove_var("ARCA_BASE_DIR");
    if let Err(panic) = result {
        std::panic::resume_unwind(panic);
    }
}

/// Usuario real (no mock) creado con la lógica de auth y bcrypt real.
pub struct TestUser {
    pub email: String,
    pub password: String,
    pub login: LoginResponse,
    pub session_store: SessionStore,
    pub repo: SqliteUserRepository,
}

impl TestUser {
    pub fn create(pool: &DbPool, email: &str, password: &str, role: &str) -> TestUser {
        let session_store = SessionStore::default();
        // Arranque admin bootstrap: único modo de obtener un token admin sin runtime Tauri.
        let admin_token = session_store.create_session(0, "bootstrap@arca.test".to_string(), "admin".to_string());
        let repo = SqliteUserRepository::new(pool.clone());
        auth::create_user_logic(&repo, &session_store, &admin_token, email, password, role)
            .expect("no se pudo crear el usuario de test");
        let login = auth::login_user_logic(&repo, &session_store, email, password)
            .expect("no se pudo loguear el usuario de test");
        TestUser {
            email: email.to_string(),
            password: password.to_string(),
            login,
            session_store,
            repo,
        }
    }
}

/// Crea un usuario admin y lo loguea. Devolvemos el TestUser completo:
/// email y password para login, session_store + login para validar/logout/cambio.
pub fn create_user_and_login(pool: &DbPool) -> TestUser {
    let email = format!("user_{}@arca.test", unique_suffix());
    TestUser::create(pool, &email, "Clave123!", "admin")
}