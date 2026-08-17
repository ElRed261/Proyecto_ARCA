use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use bcrypt::{hash, verify, DEFAULT_COST};
use tauri::{command, State};
use crate::infrastructure::error::AppError;
use crate::ports::UserRepository;
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

pub fn login_user_logic(
    repo: &dyn UserRepository,
    session_store: &SessionStore,
    email: &str,
    password: &str,
) -> Result<LoginResponse, String> {
    let user = match repo.find_by_email(email)? {
        Some(u) => u,
        None => return Err("Usuario o contraseña incorrectos".to_string()),
    };

    if !user.is_active {
        return Err("La cuenta de usuario está desactivada".to_string());
    }

    let is_valid = verify(password, &user.password_hash).map_err(|e| e.to_string())?;
    if !is_valid {
        return Err("Usuario o contraseña incorrectos".to_string());
    }

    let access_token = session_store.create_session(user.id, user.email.clone(), user.role.clone());

    Ok(LoginResponse {
        access_token,
        token_type: "bearer".to_string(),
        user_email: user.email,
        roles: vec![user.role],
    })
}

#[command]
pub fn login_user(
    pool: State<'_, crate::db::DbPool>,
    session_store: State<'_, SessionStore>,
    email: String,
    password: String,
) -> Result<LoginResponse, String> {
    let repo = crate::adapters::sqlite_user_repository::SqliteUserRepository::new(pool.inner().clone());
    login_user_logic(&repo, &session_store, &email, &password)
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

pub fn get_users_logic(
    repo: &dyn UserRepository,
    session_store: &SessionStore,
    token: &str,
) -> Result<Vec<UserResponse>, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;

    let records = repo.get_all()?;
    let users = records
        .into_iter()
        .map(|user| UserResponse {
            id: user.id,
            email: user.email,
            roles: vec![UserRole {
                id: 1,
                name: user.role,
            }],
            is_active: user.is_active,
        })
        .collect();
    Ok(users)
}

#[command]
pub fn get_users(
    pool: State<'_, crate::db::DbPool>,
    session_store: State<'_, SessionStore>,
    token: String,
) -> Result<Vec<UserResponse>, String> {
    let repo = crate::adapters::sqlite_user_repository::SqliteUserRepository::new(pool.inner().clone());
    get_users_logic(&repo, &session_store, &token)
}

pub fn update_user_logic(
    repo: &dyn UserRepository,
    session_store: &SessionStore,
    token: &str,
    user_id: i64,
    role_name: &str,
    is_active: bool,
) -> Result<String, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;
    repo.update(user_id, role_name, is_active)?;
    Ok("Usuario actualizado exitosamente".to_string())
}

#[command]
pub fn update_user(
    pool: State<'_, crate::db::DbPool>,
    session_store: State<'_, SessionStore>,
    token: String,
    user_id: i64,
    role_name: String,
    is_active: bool,
) -> Result<String, String> {
    let repo = crate::adapters::sqlite_user_repository::SqliteUserRepository::new(pool.inner().clone());
    update_user_logic(&repo, &session_store, &token, user_id, &role_name, is_active)
}

pub fn change_password_logic(
    repo: &dyn UserRepository,
    session_store: &SessionStore,
    token: &str,
    user_id: i64,
    password_val: &str,
) -> Result<String, String> {
    let session = session_store.validate_session(token).map_err(|e| e.to_string())?;
    if session.role != "admin" && session.user_id != user_id {
        return Err("No autorizado: no puede cambiar la contraseña de otro usuario".to_string());
    }

    if password_val.trim().is_empty() {
        return Err("La contraseña no puede estar vacía".to_string());
    }

    let password_hash = hash(password_val, DEFAULT_COST).map_err(|e| e.to_string())?;
    repo.change_password(user_id, &password_hash)?;
    Ok("Contraseña actualizada exitosamente".to_string())
}

#[command]
pub fn change_password(
    pool: State<'_, crate::db::DbPool>,
    session_store: State<'_, SessionStore>,
    token: String,
    user_id: i64,
    password_val: String,
) -> Result<String, String> {
    let repo = crate::adapters::sqlite_user_repository::SqliteUserRepository::new(pool.inner().clone());
    change_password_logic(&repo, &session_store, &token, user_id, &password_val)
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

pub fn create_user_logic(
    repo: &dyn UserRepository,
    session_store: &SessionStore,
    token: &str,
    email: &str,
    password: &str,
    role: &str,
) -> Result<String, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;

    let password_hash = hash(password, DEFAULT_COST).map_err(|e| e.to_string())?;
    repo.create(email, &password_hash, role)
        .map_err(|e| format!("Error al crear usuario: {}", e))?;

    Ok("Usuario creado exitosamente".to_string())
}

#[command]
pub fn create_user(
    pool: State<'_, crate::db::DbPool>,
    session_store: State<'_, SessionStore>,
    token: String,
    email: String,
    password: String,
    role: String,
) -> Result<String, String> {
    let repo = crate::adapters::sqlite_user_repository::SqliteUserRepository::new(pool.inner().clone());
    create_user_logic(&repo, &session_store, &token, &email, &password, &role)
}

pub fn delete_user_logic(
    repo: &dyn UserRepository,
    session_store: &SessionStore,
    token: &str,
    user_id: i64,
) -> Result<String, String> {
    require_role(session_store, token, &["admin"]).map_err(|e| e.to_string())?;
    repo.deactivate(user_id)?;
    Ok("Usuario desactivado exitosamente".to_string())
}

#[command]
pub fn delete_user(
    pool: State<'_, crate::db::DbPool>,
    session_store: State<'_, SessionStore>,
    token: String,
    user_id: i64,
) -> Result<String, String> {
    let repo = crate::adapters::sqlite_user_repository::SqliteUserRepository::new(pool.inner().clone());
    delete_user_logic(&repo, &session_store, &token, user_id)
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

