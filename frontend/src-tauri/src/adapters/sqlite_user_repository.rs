use crate::ports::UserRepository;
use crate::infrastructure::error::AppError;
use crate::auth::{UserResponse, UserRole};
use rusqlite::params;
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;

pub struct SqliteUserRepository {
    pool: Pool<SqliteConnectionManager>,
}

impl SqliteUserRepository {
    pub fn new(pool: Pool<SqliteConnectionManager>) -> Self {
        SqliteUserRepository { pool }
    }
}

impl UserRepository for SqliteUserRepository {
    fn get_all(&self) -> Result<Vec<UserResponse>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let mut stmt = conn.prepare("SELECT id, email, role, is_active FROM users")?;
        let rows = stmt.query_map([], |row| {
            let id: i64 = row.get(0)?;
            let email: String = row.get(1)?;
            let role_name: String = row.get(2)?;
            let is_active: i32 = row.get(3)?;

            Ok(UserResponse {
                id,
                email,
                roles: vec![UserRole { id: 1, name: role_name }],
                is_active: is_active == 1,
            })
        })?;

        let mut users = Vec::new();
        for row in rows {
            users.push(row?);
        }
        Ok(users)
    }

    fn update(&self, user_id: i64, role: &str, is_active: bool) -> Result<(), AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let is_active_int = if is_active { 1 } else { 0 };
        conn.execute(
            "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
            params![role, is_active_int, user_id],
        )?;
        Ok(())
    }

    fn change_password(&self, user_id: i64, password_hash: &str) -> Result<(), AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            params![password_hash, user_id],
        )?;
        Ok(())
    }

    fn delete(&self, user_id: i64) -> Result<(), AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        conn.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?",
            params![user_id],
        )?;
        Ok(())
    }
}
