use app_lib::auth::{require_role, LoginResponse, SessionStore, UserResponse, UserRole};
use bcrypt::{hash, verify, DEFAULT_COST};
use rusqlite::{params, Connection};

fn setup_test_db() -> Connection {
    let conn = Connection::open_in_memory().unwrap();
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
    conn
}

fn insert_user(conn: &Connection, email: &str, password: &str, role: &str, is_active: i32) -> i64 {
    let password_hash = hash(password, DEFAULT_COST).unwrap();
    conn.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, ?)",
        params![email, password_hash, role, is_active],
    )
    .unwrap();
    conn.last_insert_rowid()
}

fn login_user_logic(
    conn: &Connection,
    session_store: &SessionStore,
    email: &str,
    password: &str,
) -> Result<LoginResponse, String> {
    let mut stmt = conn
        .prepare("SELECT id, email, password_hash, role, is_active FROM users WHERE email = ?")
        .map_err(|e| e.to_string())?;

    let user_row = stmt.query_row([email], |row| {
        Ok((
            row.get::<_, i64>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, String>(2)?,
            row.get::<_, String>(3)?,
            row.get::<_, i32>(4)?,
        ))
    });

    let (id, user_email, password_hash, role, is_active) = match user_row {
        Ok(data) => data,
        Err(_) => return Err("Usuario o contraseña incorrectos".to_string()),
    };

    if is_active == 0 {
        return Err("La cuenta de usuario está desactivada".to_string());
    }

    let is_valid = verify(password, &password_hash).map_err(|e| e.to_string())?;
    if !is_valid {
        return Err("Usuario o contraseña incorrectos".to_string());
    }

    let access_token = session_store.create_session(id, user_email.clone(), role.clone());

    Ok(LoginResponse {
        access_token,
        token_type: "bearer".to_string(),
        user_email,
        roles: vec![role],
    })
}

fn create_user_logic(
    conn: &Connection,
    session_store: &SessionStore,
    token: &str,
    email: &str,
    password: &str,
    role: &str,
) -> Result<String, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;

    let password_hash = hash(password, DEFAULT_COST).map_err(|e| e.to_string())?;

    conn.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
        params![email, password_hash, role],
    )
    .map_err(|e| format!("Error al crear usuario: {}", e))?;

    Ok("Usuario creado exitosamente".to_string())
}

fn get_users_logic(
    conn: &Connection,
    session_store: &SessionStore,
    token: &str,
) -> Result<Vec<UserResponse>, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;

    let mut stmt = conn
        .prepare("SELECT id, email, role, is_active FROM users")
        .map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map([], |row| {
            let id: i64 = row.get(0)?;
            let email: String = row.get(1)?;
            let role_name: String = row.get(2)?;
            let is_active: i32 = row.get(3)?;

            Ok(UserResponse {
                id,
                email,
                roles: vec![UserRole {
                    id: 1,
                    name: role_name,
                }],
                is_active: is_active == 1,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut users = Vec::new();
    for row in rows {
        if let Ok(user) = row {
            users.push(user);
        }
    }

    Ok(users)
}

fn update_user_logic(
    conn: &Connection,
    session_store: &SessionStore,
    token: &str,
    user_id: i64,
    role_name: &str,
    is_active: bool,
) -> Result<String, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;

    let is_active_int = if is_active { 1 } else { 0 };

    conn.execute(
        "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
        params![role_name, is_active_int, user_id],
    )
    .map_err(|e| e.to_string())?;

    Ok("Usuario actualizado exitosamente".to_string())
}

fn change_password_logic(
    conn: &Connection,
    session_store: &SessionStore,
    token: &str,
    user_id: i64,
    password_val: &str,
) -> Result<String, String> {
    let session = session_store
        .validate_session(token)
        .map_err(|e| e.to_string())?;

    if session.role != "admin" && session.user_id != user_id {
        return Err("No autorizado: no puede cambiar la contraseña de otro usuario".to_string());
    }

    if password_val.trim().is_empty() {
        return Err("La contraseña no puede estar vacía".to_string());
    }

    let password_hash = hash(password_val, DEFAULT_COST).map_err(|e| e.to_string())?;

    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        params![password_hash, user_id],
    )
    .map_err(|e| e.to_string())?;

    Ok("Contraseña actualizada exitosamente".to_string())
}

fn delete_user_logic(
    conn: &Connection,
    session_store: &SessionStore,
    token: &str,
    user_id: i64,
) -> Result<String, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;

    conn.execute(
        "UPDATE users SET is_active = 0 WHERE id = ?",
        params![user_id],
    )
    .map_err(|e| e.to_string())?;

    Ok("Usuario desactivado exitosamente".to_string())
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
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    insert_user(&conn, "admin@arca.rd", "secret123", "admin", 1);

    let result = login_user_logic(&conn, &session_store, "admin@arca.rd", "secret123");

    assert!(result.is_ok());
    let response = result.unwrap();
    assert!(!response.access_token.is_empty());
    assert_eq!(response.token_type, "bearer");
    assert_eq!(response.user_email, "admin@arca.rd");
    assert_eq!(response.roles, vec!["admin"]);
}

#[test]
fn login_user_with_wrong_password_returns_error() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    insert_user(&conn, "admin@arca.rd", "secret123", "admin", 1);

    let result = login_user_logic(&conn, &session_store, "admin@arca.rd", "wrongpassword");

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("incorrectos"));
}

#[test]
fn login_user_with_nonexistent_email_returns_error() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();

    let result = login_user_logic(&conn, &session_store, "ghost@arca.rd", "secret123");

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("incorrectos"));
}

#[test]
fn login_user_with_deactivated_user_returns_error() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    insert_user(&conn, "inactive@arca.rd", "secret123", "admin", 0);

    let result = login_user_logic(&conn, &session_store, "inactive@arca.rd", "secret123");

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("desactivada"));
}

#[test]
fn create_user_inserts_bcrypt_hash_and_allows_login() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    let result = create_user_logic(
        &conn,
        &session_store,
        &admin_token,
        "newuser@arca.rd",
        "newpass",
        "control_calidad",
    );

    assert!(result.is_ok());

    let mut stmt = conn
        .prepare("SELECT password_hash FROM users WHERE email = ?")
        .unwrap();
    let hash: String = stmt.query_row(["newuser@arca.rd"], |row| row.get(0)).unwrap();
    assert!(verify("newpass", &hash).unwrap());
    assert!(!verify("wrongpass", &hash).unwrap());

    let login = login_user_logic(&conn, &session_store, "newuser@arca.rd", "newpass");
    assert!(login.is_ok());
}

#[test]
fn create_user_with_duplicate_email_returns_error() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    create_user_logic(
        &conn,
        &session_store,
        &admin_token,
        "dup@arca.rd",
        "pass1",
        "admin",
    )
    .unwrap();

    let result = create_user_logic(
        &conn,
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
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    insert_user(&conn, "a@arca.rd", "pass", "admin", 1);
    insert_user(&conn, "b@arca.rd", "pass", "control_calidad", 1);

    let users = get_users_logic(&conn, &session_store, &admin_token).unwrap();

    assert_eq!(users.len(), 2);
    assert!(users.iter().any(|u| u.email == "a@arca.rd" && u.roles.len() == 1 && u.roles[0].name == "admin"));
    assert!(users.iter().any(|u| u.email == "b@arca.rd" && u.roles[0].name == "control_calidad"));
}

#[test]
fn update_user_changes_role_and_is_active() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());

    let user_id = insert_user(&conn, "to_update@arca.rd", "pass", "observador", 1);

    let result = update_user_logic(&conn, &session_store, &admin_token, user_id, "encargado", false);
    assert!(result.is_ok());

    let mut stmt = conn
        .prepare("SELECT role, is_active FROM users WHERE id = ?")
        .unwrap();
    let (role, is_active): (String, i32) = stmt.query_row([user_id], |row| Ok((row.get(0)?, row.get(1)?))).unwrap();
    assert_eq!(role, "encargado");
    assert_eq!(is_active, 0);
}

#[test]
fn change_password_allows_login_with_new_and_blocks_old() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    let user_id = insert_user(&conn, "changer@arca.rd", "oldpass", "admin", 1);
    let token = session_store.create_session(user_id, "changer@arca.rd".to_string(), "admin".to_string());

    let result = change_password_logic(&conn, &session_store, &token, user_id, "newpass");
    assert!(result.is_ok());

    let with_new = login_user_logic(&conn, &session_store, "changer@arca.rd", "newpass");
    assert!(with_new.is_ok());

    let with_old = login_user_logic(&conn, &session_store, "changer@arca.rd", "oldpass");
    assert!(with_old.is_err());
}

#[test]
fn delete_user_sets_is_active_zero_and_blocks_login() {
    let conn = setup_test_db();
    let session_store = SessionStore::default();
    let admin_token = session_store.create_session(1, "admin@arca.rd".to_string(), "admin".to_string());
    let user_id = insert_user(&conn, "todelete@arca.rd", "pass", "admin", 1);

    let result = delete_user_logic(&conn, &session_store, &admin_token, user_id);
    assert!(result.is_ok());

    let mut stmt = conn
        .prepare("SELECT is_active FROM users WHERE id = ?")
        .unwrap();
    let is_active: i32 = stmt.query_row([user_id], |row| row.get(0)).unwrap();
    assert_eq!(is_active, 0);

    let login = login_user_logic(&conn, &session_store, "todelete@arca.rd", "pass");
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
