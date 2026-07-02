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
    fn test_find_by_email_returns_existing_user() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
            insert_user(&conn, "user@arca.rd", "pass", "admin", 1);
        }

        let user = repo.find_by_email("user@arca.rd").unwrap();
        assert!(user.is_some());
        let user = user.unwrap();
        assert_eq!(user.email, "user@arca.rd");
        assert_eq!(user.role, "admin");
        assert!(user.is_active);
        assert!(user.id > 0);
    }

    #[test]
    fn test_find_by_email_returns_none_for_missing_user() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);

        let user = repo.find_by_email("missing@arca.rd").unwrap();
        assert!(user.is_none());
    }

    #[test]
    fn test_create_inserts_user_and_can_find_by_email() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        let password_hash = hash("newpass", DEFAULT_COST).unwrap();

        repo.create("new@arca.rd", &password_hash, "control_calidad").unwrap();

        let user = repo.find_by_email("new@arca.rd").unwrap();
        assert!(user.is_some());
        let user = user.unwrap();
        assert_eq!(user.email, "new@arca.rd");
        assert_eq!(user.role, "control_calidad");
        assert!(user.is_active);
    }

    #[test]
    fn test_get_all_returns_users() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
            insert_user(&conn, "a@arca.rd", "pass", "admin", 1);
            insert_user(&conn, "b@arca.rd", "pass", "control_calidad", 0);
        }

        let users = repo.get_all().unwrap();
        assert_eq!(users.len(), 2);
        assert!(users.iter().any(|u| u.email == "a@arca.rd" && u.is_active && u.role == "admin"));
        assert!(users.iter().any(|u| u.email == "b@arca.rd" && !u.is_active && u.role == "control_calidad"));
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
    fn test_change_password_updates_password_hash() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        let user_id = {
            let conn = repo.pool.get().unwrap();
            insert_user(&conn, "changer@arca.rd", "oldpass", "admin", 1)
        };

        let new_hash = hash("newpass", DEFAULT_COST).unwrap();
        repo.change_password(user_id, &new_hash).unwrap();

        let conn = repo.pool.get().unwrap();
        let stored_hash: String = conn
            .query_row("SELECT password_hash FROM users WHERE id = ?", [user_id], |row| row.get(0))
            .unwrap();
        assert_eq!(stored_hash, new_hash);
    }

    #[test]
    fn test_deactivate_sets_is_active_zero() {
        let pool = setup_pool();
        let repo = SqliteUserRepository::new(pool);
        let user_id = {
            let conn = repo.pool.get().unwrap();
            insert_user(&conn, "deactivate@arca.rd", "pass", "admin", 1)
        };

        repo.deactivate(user_id).unwrap();

        let conn = repo.pool.get().unwrap();
        let is_active: i32 = conn
            .query_row("SELECT is_active FROM users WHERE id = ?", [user_id], |row| row.get(0))
            .unwrap();
        assert_eq!(is_active, 0);
    }
}
