use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("No encontrado: {0}")]
    NotFound(String),

    #[error("No autorizado: {0}")]
    Unauthorized(String),

    #[error("Error de validación: {0}")]
    Validation(String),

    #[error("Error de base de datos: {0}")]
    Database(#[from] rusqlite::Error),

    #[error("Error de E/S de archivos: {0}")]
    Io(#[from] std::io::Error),

    #[error("Error de serialización JSON: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Error de Excel: {0}")]
    Excel(String),

    #[error("Error interno del sistema: {0}")]
    Internal(String),
}

impl Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

impl From<String> for AppError {
    fn from(err: String) -> Self {
        AppError::Internal(err)
    }
}
