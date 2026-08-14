//! AppError — single error type for the whole crate.
//!
//! MIGRATION TODO: move the current AppError (infrastructure/error.rs) here and
//! standardize every command on it. Today ~half the commands return
//! `Result<T, String>` and half `Result<T, AppError>`; the goal is ONE type
//! owned by the domain layer so modules and the app layer can share failures.
//!
//! Note: AppError currently serializes to a bare string, so the frontend gains
//! nothing yet. When consolidating, keep the wire format stable or bump the
//! frontend mapping (humanizeError in AuditObservationPage).
