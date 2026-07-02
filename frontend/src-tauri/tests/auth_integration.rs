use app_lib::adapters::sqlite_user_repository::SqliteUserRepository;
use app_lib::auth::{
    change_password_logic, create_user_logic, delete_user_logic, get_users_logic,
    login_user_logic, update_user_logic, SessionStore,
};
use app_lib::ports::UserRepository;
use bcrypt::{hash, verify, DEFAULT_COST};
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use std::sync::atomic::{AtomicUsize, Ordering};

static TEST_DB_COUNTER: AtomicUsize = AtomicUsize::new(0);

fn setup_pool() -> Pool<SqliteConnectionManager> {
    let n = TEST_DB_COUNTER.fetch_add(1, Ordering::SeqCst);
    let mut path = std::env::temp_dir();
    path.push(format!("arca_auth_integration_test_{}_{}.db", std::process::id(), n));
    let _ = std::fs::remove_file(&path);

    let manager = SqliteConnectionManager::file(&path);
    let pool = Pool::new(manager).unwrap();

    let conn = pool.get().unwrap();
    conn.execute_batch(
        r#"
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
        "#,
    )
    .unwrap();

    pool
}

fn insert_user(repo: &SqliteUserRepository, email: &str, password: &str, role: &str) -> i64 {
    let password_hash = hash(password, DEFAULT_COST).unwrap();
    repo.create(email, &password_hash, role).unwrap();
    repo.find_by_email(email).unwrap().expect("usuario recién creado").id
}

fn validate_token_logic(session_store: &SessionStore, token: &str) -> Result<bool, String> {
    match session_store.validate_session(token) {
        Ok(_) => Ok(true),
        Err(_) => Ok(false),
    }
}

fn logout_logic(session_store: &SessionStore, token: &str) -> Result<String, String> {
    session_store.delete_session(token);
    Ok("Sesión cerrada".to_string())
}

#[test]
fn login_user_with_valid_credentials_returns_token_and_roles() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    insert_user(&repo, "admin@arca.rd", "secret123", "admin");

    let result = login_user_logic(&repo, &session_store, "admin@arca.rd", "secret123");

    assert!(result.is_ok());
    let response = result.unwrap();
    assert!(!response.access_token.is_empty());
    assert_eq!(response.token_type, "bearer");
    assert_eq!(response.user_email, "admin@arca.rd");
    assert_eq!(response.roles, vec!["admin"]);
}

#[test]
fn login_user_with_wrong_password_returns_error() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    insert_user(&repo, "admin@arca.rd", "secret123", "admin");

    let result = login_user_logic(&repo, &session_store, "admin@arca.rd", "wrongpassword");

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("incorrectos"));
}

#[test]
fn login_user_with_nonexistent_email_returns_error() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();

    let result = login_user_logic(&repo, &session_store, "ghost@arca.rd", "secret123");

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("incorrectos"));
}

#[test]
fn login_user_with_deactivated_user_returns_error() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    let user_id = insert_user(&repo, "inactive@arca.rd", "secret123", "admin");
    repo.update(user_id, "admin", false).unwrap();

    let result = login_user_logic(&repo, &session_store, "inactive@arca.rd", "secret123");

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("desactivada"));
}

#[test]
fn create_user_inserts_bcrypt_hash_and_allows_login() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    let result = create_user_logic(
        &repo,
        &session_store,
        &admin_token,
        "newuser@arca.rd",
        "newpass",
        "control_calidad",
    );

    assert!(result.is_ok());

    let user = repo.find_by_email("newuser@arca.rd").unwrap().expect("usuario creado");
    assert!(verify("newpass", &user.password_hash).unwrap());
    assert!(!verify("wrongpass", &user.password_hash).unwrap());

    let login = login_user_logic(&repo, &session_store, "newuser@arca.rd", "newpass");
    assert!(login.is_ok());
}

#[test]
fn create_user_with_duplicate_email_returns_error() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    create_user_logic(
        &repo,
        &session_store,
        &admin_token,
        "dup@arca.rd",
        "pass1",
        "admin",
    )
    .unwrap();

    let result = create_user_logic(
        &repo,
        &session_store,
        &admin_token,
        "dup@arca.rd",
        "pass2",
        "admin",
    );

    assert!(result.is_err());
    let err = result.unwrap_err();
    assert!(err.contains("UNIQUE") || err.to_lowercase().contains("unique"));
}

#[test]
fn get_users_returns_all_users_with_roles_array() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    insert_user(&repo, "a@arca.rd", "pass", "admin");
    insert_user(&repo, "b@arca.rd", "pass", "control_calidad");

    let users = get_users_logic(&repo, &session_store, &admin_token).unwrap();

    assert_eq!(users.len(), 2);
    assert!(users.iter().any(|u| u.email == "a@arca.rd" && u.roles.len() == 1 && u.roles[0].name == "admin"));
    assert!(users.iter().any(|u| u.email == "b@arca.rd" && u.roles[0].name == "control_calidad"));
}

#[test]
fn update_user_changes_role_and_is_active() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    let user_id = insert_user(&repo, "to_update@arca.rd", "pass", "observador");

    let result = update_user_logic(&repo, &session_store, &admin_token, user_id, "encargado", false);
    assert!(result.is_ok());

    let user = repo.find_by_email("to_update@arca.rd").unwrap().expect("usuario actualizado");
    assert_eq!(user.role, "encargado");
    assert!(!user.is_active);
}

#[test]
fn change_password_allows_login_with_new_and_blocks_old() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    let user_id = insert_user(&repo, "changer@arca.rd", "oldpass", "admin");
    let token = session_store.create_session(user_id, "changer@arca.rd".to_string(), "admin".to_string());

    let result = change_password_logic(&repo, &session_store, &token, user_id, "newpass");
    assert!(result.is_ok());

    let with_new = login_user_logic(&repo, &session_store, "changer@arca.rd", "newpass");
    assert!(with_new.is_ok());

    let with_old = login_user_logic(&repo, &session_store, "changer@arca.rd", "oldpass");
    assert!(with_old.is_err());
}

#[test]
fn delete_user_sets_is_active_zero_and_blocks_login() {
    let pool = setup_pool();
    let repo = SqliteUserRepository::new(pool);
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());
    let user_id = insert_user(&repo, "todelete@arca.rd", "pass", "admin");

    let result = delete_user_logic(&repo, &session_store, &admin_token, user_id);
    assert!(result.is_ok());

    let user = repo.find_by_email("todelete@arca.rd").unwrap().expect("usuario desactivado");
    assert!(!user.is_active);

    let login = login_user_logic(&repo, &session_store, "todelete@arca.rd", "pass");
    assert!(login.is_err());
}

#[test]
fn validate_token_returns_true_for_valid_session_and_false_after_logout() {
    let session_store = SessionStore::default();
    let token = session_store.create_session(1, "user@arca.rd".to_string(), "admin".to_string());

    assert_eq!(validate_token_logic(&session_store, &token).unwrap(), true);

    logout_logic(&session_store, &token).unwrap();

    assert_eq!(validate_token_logic(&session_store, &token).unwrap(), false);
}

#[test]
fn logout_deletes_session() {
    let session_store = SessionStore::default();
    let token = session_store.create_session(42, "logout@arca.rd".to_string(), "admin".to_string());

    assert!(session_store.validate_session(&token).is_ok());

    logout_logic(&session_store, &token).unwrap();

    assert!(session_store.validate_session(&token).is_err());
}
