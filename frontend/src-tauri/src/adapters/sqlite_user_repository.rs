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

#[cfg(test)]
mod tests {
    use super::*;
    use bcrypt::{hash, DEFAULT_COST};
    use rusqlite::params;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static TEST_DB_COUNTER: AtomicUsize = AtomicUsize::new(0);

    fn setup_pool() -> Pool<SqliteConnectionManager> {
        let n = TEST_DB_COUNTER.fetch_add(1, Ordering::SeqCst);
        let mut path = std::env::temp_dir();
        path.push(format!("arca_user_test_{}_{}.db", std::process::id(), n));
        let _ = std::fs::remove_file(&path);

        let manager = SqliteConnectionManager::file(&path);
        let pool = Pool::new(manager).unwrap();

        let conn = pool.get().unwrap();
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS users (
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

    fn insert_user(conn: &rusqlite::Connection, email: &str, password: &str, role: &str, is_active: i32) -> i64 {
        let password_hash = hash(password, DEFAULT_COST).unwrap();
        conn.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, ?)",
            params![email, password_hash, role, is_active],
        )
        .unwrap();
        conn.last_insert_rowid()
    }

    #[test]
    fn test_new_creates_repository() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        let _ = repo;
    }

    #[test]
    fn test_find_by_email_logic_returns_existing_user() {
        let pool = setup_pool();
        let conn = pool.get().unwrap();
        insert_user(&conn, "user@arca.rd", "pass", "admin", 1);

        let result: Result<(i64, String, String, i32), rusqlite::Error> = conn.query_row(
            "SELECT id, email, role, is_active FROM users WHERE email = ?",
            ["user@arca.rd"],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        );

        assert!(result.is_ok());
        let (id, email, role, is_active) = result.unwrap();
        assert_eq!(email, "user@arca.rd");
        assert_eq!(role, "admin");
        assert_eq!(is_active, 1);
        assert!(id > 0);
    }

    #[test]
    fn test_find_by_email_logic_returns_none_for_missing_user() {
        let pool = setup_pool();
        let conn = pool.get().unwrap();

        let result: Result<(i64, String, String, i32), rusqlite::Error> = conn.query_row(
            "SELECT id, email, role, is_active FROM users WHERE email = ?",
            ["missing@arca.rd"],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        );

        assert!(matches!(result, Err(rusqlite::Error::QueryReturnedNoRows)));
    }

    #[test]
    fn test_create_logic_inserts_user_and_can_find_by_email() {
        let pool = setup_pool();
        let conn = pool.get().unwrap();

        let password_hash = hash("newpass", DEFAULT_COST).unwrap();
        conn.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
            params!["new@arca.rd", password_hash, "control_calidad"],
        )
        .unwrap();

        let result: Result<String, rusqlite::Error> = conn.query_row(
            "SELECT role FROM users WHERE email = ?",
            ["new@arca.rd"],
            |row| row.get(0),
        );
        assert_eq!(result.unwrap(), "control_calidad");
    }

    #[test]
    fn test_get_all_returns_users_with_roles_array() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
            insert_user(&conn, "a@arca.rd", "pass", "admin", 1);
            insert_user(&conn, "b@arca.rd", "pass", "control_calidad", 0);
        }

        let users = repo.get_all().unwrap();
        assert_eq!(users.len(), 2);
        assert!(users.iter().any(|u| u.email == "a@arca.rd" && u.is_active && u.roles[0].name == "admin"));
        assert!(users.iter().any(|u| u.email == "b@arca.rd" && !u.is_active && u.roles[0].name == "control_calidad"));
    }

    #[test]
    fn test_update_changes_role_and_is_active() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        let user_id = {
            let conn = repo.pool.get().unwrap();
            insert_user(&conn, "update@arca.rd", "pass", "observador", 1)
        };

        repo.update(user_id, "encargado", false).unwrap();

        let conn = repo.pool.get().unwrap();
        let (role, is_active): (String, i32) = conn
            .query_row("SELECT role, is_active FROM users WHERE id = ?", [user_id], |row| {
                Ok((row.get(0)?, row.get(1)?))
            })
            .unwrap();
        assert_eq!(role, "encargado");
        assert_eq!(is_active, 0);
    }

    #[test]
    fn test_deactivate_sets_is_active_zero() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        let user_id = {
            let conn = repo.pool.get().unwrap();
            insert_user(&conn, "deactivate@arca.rd", "pass", "admin", 1)
        };

        repo.delete(user_id).unwrap();

        let conn = repo.pool.get().unwrap();
        let is_active: i32 = conn
            .query_row("SELECT is_active FROM users WHERE id = ?", [user_id], |row| row.get(0))
            .unwrap();
        assert_eq!(is_active, 0);
    }
}
