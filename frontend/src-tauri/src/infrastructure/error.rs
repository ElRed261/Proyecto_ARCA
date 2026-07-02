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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json;

    #[test]
    fn test_unauthorized_converts_to_correct_string() {
        let err = AppError::Unauthorized("credenciales inválidas".to_string());
        assert_eq!(err.to_string(), "No autorizado: credenciales inválidas");
    }

    #[test]
    fn test_not_found_converts_to_correct_string() {
        let err = AppError::NotFound("usuario".to_string());
        assert_eq!(err.to_string(), "No encontrado: usuario");
    }

    #[test]
    fn test_all_variants_serialize_as_strings() {
        let variants = vec![
            AppError::NotFound("x".to_string()),
            AppError::Unauthorized("x".to_string()),
            AppError::Validation("x".to_string()),
            AppError::Database(rusqlite::Error::InvalidQuery),
            AppError::Io(std::io::Error::new(std::io::ErrorKind::Other, "x")),
            AppError::Json(serde_json::from_str::<serde_json::Value>("").unwrap_err()),
            AppError::Excel("x".to_string()),
            AppError::Internal("x".to_string()),
        ];

        for err in variants {
            let json = serde_json::to_string(&err).unwrap();
            assert!(
                json.starts_with('"') && json.ends_with('"'),
                "Expected JSON string serialization, got: {}",
                json
            );
            assert!(!json.is_empty());
        }
    }
}
