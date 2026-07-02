use crate::infrastructure::error::AppError;
use crate::audit::{ErrorMark, Correction, ErrorReportRow, PersonSummaryRow};

#[derive(Debug, Clone)]
pub struct UserRecord {
    pub id: i64,
    pub email: String,
    pub password_hash: String,
    pub role: String,
    pub is_active: bool,
}

pub trait UserRepository: Send + Sync {
    fn find_by_email(&self, email: &str) -> Result<Option<UserRecord>, String>;
    fn create(&self, email: &str, password_hash: &str, role: &str) -> Result<(), String>;
    fn get_all(&self) -> Result<Vec<UserRecord>, String>;
    fn update(&self, user_id: i64, role: &str, is_active: bool) -> Result<(), String>;
    fn change_password(&self, user_id: i64, password_hash: &str) -> Result<(), String>;
    fn deactivate(&self, user_id: i64) -> Result<(), String>;
}

pub trait AuditRepository {
    fn get_error_marks(&self, station_id: &str, fecha: &str) -> Result<Vec<ErrorMark>, AppError>;
    fn get_corrections(&self, station_id: &str, fecha: &str) -> Result<Vec<Correction>, AppError>;
    fn mark_error(&self, mark: &ErrorMark) -> Result<i32, AppError>;
    fn unmark_error(&self, id: i32) -> Result<(), AppError>;
    fn get_mark_details(&self, id: i32) -> Result<(String, String, String, String), AppError>;
    fn delete_corrections_by_mark(&self, station_id: &str, fecha: &str, hora: &str, campo: &str) -> Result<(), AppError>;
    fn update_mark_note(&self, id: i32, note: Option<String>) -> Result<(), AppError>;
    fn propose_correction(&self, corr: &Correction) -> Result<i32, AppError>;
    fn get_error_report(&self, station_id: Option<String>, year: Option<String>, month: Option<String>) -> Result<Vec<ErrorReportRow>, AppError>;
    fn get_daily_error_counts(&self, station_id: &str, month_prefix: &str) -> Result<std::collections::HashMap<String, i64>, AppError>;
    fn get_daily_correction_counts(&self, station_id: &str, month_prefix: &str) -> Result<std::collections::HashMap<String, i64>, AppError>;
    fn get_approved_corrections_for_date(&self, station_id: &str, fecha: &str) -> Result<Vec<(String, String, String)>, AppError>;
    fn get_person_summary(&self, station_id: Option<String>, year: Option<String>, month: Option<String>) -> Result<Vec<PersonSummaryRow>, AppError>;
}
