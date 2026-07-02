use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use bcrypt::{hash, verify, DEFAULT_COST};
use tauri::{AppHandle, command, State};
use crate::db::get_db_path;
use crate::infrastructure::error::AppError;
use std::collections::HashMap;
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};

static COUNTER: AtomicUsize = AtomicUsize::new(0);

#[derive(Clone, Debug)]
pub struct Session {
    pub user_id: i64,
    pub email: String,
    pub role: String,
    pub created_at: i64,
}

pub struct SessionStore {
    pub sessions: Mutex<HashMap<String, Session>>,
}

impl Default for SessionStore {
    fn default() -> Self {
        SessionStore {
            sessions: Mutex::new(HashMap::new()),
        }
    }
}

impl SessionStore {
    pub fn create_session(&self, user_id: i64, email: String, role: String) -> String {
        let count = COUNTER.fetch_add(1, Ordering::SeqCst);
        let timestamp = chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0);
        let token = format!("{:x}-{:x}", timestamp, count);
        let session = Session {
            user_id,
            email,
            role,
            created_at: chrono::Utc::now().timestamp(),
        };
        let mut sessions = self.sessions.lock().unwrap();
        sessions.insert(token.clone(), session);
        token
    }

    pub fn validate_session(&self, token: &str) -> Result<Session, AppError> {
        let sessions = self.sessions.lock().unwrap();
        if let Some(session) = sessions.get(token) {
            let now = chrono::Utc::now().timestamp();
            if now - session.created_at > 28800 {
                return Err(AppError::Unauthorized("Sesión expirada".to_string()));
            }
            Ok(session.clone())
        } else {
            Err(AppError::Unauthorized("Sesión no encontrada o inválida".to_string()))
        }
    }

    pub fn delete_session(&self, token: &str) {
        let mut sessions = self.sessions.lock().unwrap();
        sessions.remove(token);
    }
}

#[derive(Serialize, Deserialize, Debug)]
pub struct UserRole {
    pub id: i64,
    pub name: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct UserResponse {
    pub id: i64,
    pub email: String,
    pub roles: Vec<UserRole>,
    pub is_active: bool,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct LoginResponse {
    pub access_token: String,
    pub token_type: String,
    pub user_email: String,
    pub roles: Vec<String>,
}

#[command]
pub fn login_user(
    app_handle: AppHandle,
    session_store: State<'_, SessionStore>,
    email: String,
    password: String,
) -> Result<LoginResponse, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let mut stmt = conn
        .prepare("SELECT id, email, password_hash, role, is_active FROM users WHERE email = ?")
        .map_err(|e| e.to_string())?;

    let user_row = stmt
        .query_row([&email], |row| {
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

    let is_valid = verify(&password, &password_hash).map_err(|e| e.to_string())?;
    if !is_valid {
        return Err("Usuario o contraseña incorrectos".to_string());
    }

    // Generamos un token efímero seguro guardándolo en memoria
    let access_token = session_store.create_session(id, user_email.clone(), role.clone());

    Ok(LoginResponse {
        access_token,
        token_type: "bearer".to_string(),
        user_email,
        roles: vec![role],
    })
}

pub fn require_role(
    session_store: &SessionStore,
    token: &str,
    allowed_roles: &[&str],
) -> Result<Session, AppError> {
    let session = session_store.validate_session(token)?;
    if !allowed_roles.contains(&session.role.as_str()) {
        return Err(AppError::Unauthorized("No autorizado: privilegios insuficientes".to_string()));
    }
    Ok(session)
}

#[command]
pub fn get_users(
    app_handle: AppHandle,
    session_store: State<'_, SessionStore>,
    token: String,
) -> Result<Vec<UserResponse>, String> {
    require_role(&session_store, &token, &["admin"]).map_err(|e| e.to_string())?;

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

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

#[command]
pub fn update_user(
    app_handle: AppHandle,
    session_store: State<'_, SessionStore>,
    token: String,
    user_id: i64,
    role_name: String,
    is_active: bool,
) -> Result<String, String> {
    require_role(&session_store, &token, &["admin"]).map_err(|e| e.to_string())?;

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let is_active_int = if is_active { 1 } else { 0 };

    conn.execute(
        "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
        params![role_name, is_active_int, user_id],
    )
    .map_err(|e| e.to_string())?;

    Ok("Usuario actualizado exitosamente".to_string())
}

#[command]
pub fn change_password(
    app_handle: AppHandle,
    session_store: State<'_, SessionStore>,
    token: String,
    user_id: i64,
    password_val: String,
) -> Result<String, String> {
    let session = session_store.validate_session(&token).map_err(|e| e.to_string())?;
    // Permite cambiar contraseña si es admin o si el usuario coincide
    if session.role != "admin" && session.user_id != user_id {
        return Err("No autorizado: no puede cambiar la contraseña de otro usuario".to_string());
    }

    if password_val.trim().is_empty() {
        return Err("La contraseña no puede estar vacía".to_string());
    }

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let password_hash = hash(&password_val, DEFAULT_COST).map_err(|e| e.to_string())?;

    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        params![password_hash, user_id],
    )
    .map_err(|e| e.to_string())?;

    Ok("Contraseña actualizada exitosamente".to_string())
}

#[command]
pub fn validate_token(
    session_store: State<'_, SessionStore>,
    token: String,
) -> Result<bool, String> {
    match session_store.validate_session(&token) {
        Ok(_) => Ok(true),
        Err(_) => Ok(false),
    }
}

#[command]
pub fn logout(
    session_store: State<'_, SessionStore>,
    token: String,
) -> Result<String, String> {
    session_store.delete_session(&token);
    Ok("Sesión cerrada".to_string())
}

#[command]
pub fn create_user(
    app_handle: AppHandle,
    session_store: State<'_, SessionStore>,
    token: String,
    email: String,
    password: String,
    role: String,
) -> Result<String, String> {
    require_role(&session_store, &token, &["admin"]).map_err(|e| e.to_string())?;

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let password_hash = hash(&password, DEFAULT_COST).map_err(|e| e.to_string())?;

    conn.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
        params![email, password_hash, role],
    )
    .map_err(|e| format!("Error al crear usuario: {}", e))?;

    Ok("Usuario creado exitosamente".to_string())
}

#[command]
pub fn delete_user(
    app_handle: AppHandle,
    session_store: State<'_, SessionStore>,
    token: String,
    user_id: i64,
) -> Result<String, String> {
    require_role(&session_store, &token, &["admin"]).map_err(|e| e.to_string())?;

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    // Desactivar el usuario en lugar de borrarlo físicamente
    conn.execute(
        "UPDATE users SET is_active = 0 WHERE id = ?",
        params![user_id],
    )
    .map_err(|e| e.to_string())?;

    Ok("Usuario desactivado exitosamente".to_string())
}

// Función auxiliar para validar roles en otros comandos protegidos
pub fn validate_user_role(conn: &Connection, user_id: i64, allowed_roles: &[&str]) -> Result<bool, String> {
    let mut stmt = conn
        .prepare("SELECT role, is_active FROM users WHERE id = ?")
        .map_err(|e| e.to_string())?;

    let user_info = stmt.query_row([user_id], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, i32>(1)?))
    });

    match user_info {
        Ok((role, is_active)) => {
            if is_active == 0 {
                return Ok(false);
            }
            Ok(allowed_roles.contains(&role.as_str()))
        }
        Err(_) => Ok(false),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_session_returns_non_empty_token() {
        let store = SessionStore::default();
        let token = store.create_session(1, "test@arca.do".to_string(), "admin".to_string());
        assert!(!token.is_empty(), "Token no debe estar vacío");
    }

    #[test]
    fn test_create_session_stores_session_data() {
        let store = SessionStore::default();
        let token = store.create_session(42, "user@arca.do".to_string(), "control_calidad".to_string());
        let session = store.validate_session(&token).expect("Sesión válida");
        assert_eq!(session.user_id, 42);
        assert_eq!(session.email, "user@arca.do");
        assert_eq!(session.role, "control_calidad");
    }

    #[test]
    fn test_create_two_sessions_returns_different_tokens() {
        let store = SessionStore::default();
        let t1 = store.create_session(1, "a@arca.do".to_string(), "admin".to_string());
        let t2 = store.create_session(2, "b@arca.do".to_string(), "admin".to_string());
        assert_ne!(t1, t2, "Cada sesión debe tener un token único");
    }

    #[test]
    fn test_validate_session_invalid_token() {
        let store = SessionStore::default();
        let result = store.validate_session("token-inexistente");
        assert!(result.is_err(), "Token inválido debe dar error");
        assert!(result.unwrap_err().to_string().contains("no encontrada"));
    }

    #[test]
    fn test_validate_session_expired() {
        let store = SessionStore::default();
        let token = store.create_session(1, "test@arca.do".to_string(), "admin".to_string());
        // Simular expiración: modificar created_at a 9 horas atrás (32400s > 28800s)
        {
            let mut sessions = store.sessions.lock().unwrap();
            if let Some(session) = sessions.get_mut(&token) {
                session.created_at = chrono::Utc::now().timestamp() - 32400;
            }
        }
        let result = store.validate_session(&token);
        assert!(result.is_err(), "Sesión expirada debe dar error");
        assert!(result.unwrap_err().to_string().contains("expirada"));
    }

    #[test]
    fn test_validate_session_not_yet_expired() {
        let store = SessionStore::default();
        let token = store.create_session(1, "test@arca.do".to_string(), "admin".to_string());
        // Simular 7 horas de sesión (25200s < 28800s)
        {
            let mut sessions = store.sessions.lock().unwrap();
            if let Some(session) = sessions.get_mut(&token) {
                session.created_at = chrono::Utc::now().timestamp() - 25200;
            }
        }
        let result = store.validate_session(&token);
        assert!(result.is_ok(), "Sesión dentro de las 8h debe ser válida");
    }

    #[test]
    fn test_delete_session_removes_token() {
        let store = SessionStore::default();
        let token = store.create_session(1, "test@arca.do".to_string(), "admin".to_string());
        store.delete_session(&token);
        let result = store.validate_session(&token);
        assert!(result.is_err(), "Sesión eliminada no debe validar");
    }

    #[test]
    fn test_delete_session_nonexistent_is_noop() {
        let store = SessionStore::default();
        // No debe panicar al eliminar un token que no existe
        store.delete_session("token-inexistente");
    }

    #[test]
    fn test_require_role_allowed() {
        let store = SessionStore::default();
        let token = store.create_session(1, "admin@arca.do".to_string(), "admin".to_string());
        let result = require_role(&store, &token, &["admin"]);
        assert!(result.is_ok(), "Admin debe tener acceso a commands de admin");
        assert_eq!(result.unwrap().role, "admin");
    }

    #[test]
    fn test_require_role_denied() {
        let store = SessionStore::default();
        let token = store.create_session(1, "qc@arca.do".to_string(), "control_calidad".to_string());
        let result = require_role(&store, &token, &["admin"]);
        assert!(result.is_err(), "control_calidad NO debe tener acceso admin");
        assert!(result.unwrap_err().to_string().contains("insuficientes"));
    }

    #[test]
    fn test_require_role_multiple_allowed() {
        let store = SessionStore::default();
        let token = store.create_session(1, "qc@arca.do".to_string(), "control_calidad".to_string());
        let result = require_role(&store, &token, &["admin", "control_calidad"]);
        assert!(result.is_ok(), "control_calidad debe pasar cuando está en la lista");
    }

    #[test]
    fn test_require_role_invalid_token() {
        let store = SessionStore::default();
        let result = require_role(&store, "token-falso", &["admin"]);
        assert!(result.is_err(), "Token inválido debe fallar antes de checkear rol");
    }
}
