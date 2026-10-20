use crate::ports::{UserRecord, UserRepository};
use rusqlite::{params, OptionalExtension};
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
    fn find_by_email(&self, email: &str) -> Result<Option<UserRecord>, String> {
        let conn = self.pool.get().map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT id, email, password_hash, role, is_active FROM users WHERE email = ?")
            .map_err(|e| e.to_string())?;
        let result = stmt
            .query_row([email], |row| {
                Ok(UserRecord {
                    id: row.get(0)?,
                    email: row.get(1)?,
                    password_hash: row.get(2)?,
                    role: row.get(3)?,
                    is_active: row.get::<_, i32>(4)? == 1,
                })
            })
            .optional()
            .map_err(|e| e.to_string())?;
        Ok(result)
    }

    fn create(&self, email: &str, password_hash: &str, role: &str) -> Result<(), String> {
        let conn = self.pool.get().map_err(|e| e.to_string())?;
        conn.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
            params![email, password_hash, role],
        )
        .map_err(|e| e.to_string())?;
        Ok(())
    }

    fn get_all(&self) -> Result<Vec<UserRecord>, String> {
        let conn = self.pool.get().map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT id, email, password_hash, role, is_active FROM users")
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |row| {
                Ok(UserRecord {
                    id: row.get(0)?,
                    email: row.get(1)?,
                    password_hash: row.get(2)?,
                    role: row.get(3)?,
                    is_active: row.get::<_, i32>(4)? == 1,
                })
            })
            .map_err(|e| e.to_string())?;

        let mut users = Vec::new();
        for user in rows.flatten() {
            users.push(user);
        }
        Ok(users)
    }

    fn update(&self, user_id: i64, role: &str, is_active: bool) -> Result<(), String> {
        let conn = self.pool.get().map_err(|e| e.to_string())?;
        let is_active_int = if is_active { 1 } else { 0 };
        conn.execute(
            "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
            params![role, is_active_int, user_id],
        )
        .map_err(|e| e.to_string())?;
        Ok(())
    }

    fn change_password(&self, user_id: i64, password_hash: &str) -> Result<(), String> {
        let conn = self.pool.get().map_err(|e| e.to_string())?;
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            params![password_hash, user_id],
        )
        .map_err(|e| e.to_string())?;
        Ok(())
    }

    fn deactivate(&self, user_id: i64) -> Result<(), String> {
        let conn = self.pool.get().map_err(|e| e.to_string())?;
        conn.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?",
            params![user_id],
        )
        .map_err(|e| e.to_string())?;
        Ok(())
    }
}

