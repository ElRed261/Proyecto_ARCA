use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use bcrypt::{hash, verify, DEFAULT_COST};
use tauri::{AppHandle, command};
use crate::db::get_db_path;

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
pub fn login_user(app_handle: AppHandle, email: String, password: String) -> Result<LoginResponse, String> {
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

    // Generamos un token efímero simple
    let token_payload = format!("{}:{}:{}", id, role, chrono::Utc::now().timestamp());
    let access_token = b64_encode(&token_payload);

    Ok(LoginResponse {
        access_token,
        token_type: "bearer".to_string(),
        user_email,
        roles: vec![role],
    })
}

#[command]
pub fn get_users(app_handle: AppHandle) -> Result<Vec<UserResponse>, String> {
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
                    id: 1, // ID placeholder para roles en frontend
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
    user_id: i64,
    role_name: String,
    is_active: bool,
) -> Result<String, String> {
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
    user_id: i64,
    password_val: String,
) -> Result<String, String> {
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
pub fn delete_user(app_handle: AppHandle, user_id: i64) -> Result<String, String> {
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

// Utilidad local para b64 encoding básico
fn b64_encode(input: &str) -> String {
    use std::fmt::Write;
    let mut result = String::new();
    for byte in input.as_bytes() {
        write!(result, "{:02x}", byte).unwrap();
    }
    result
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
