"""users repository (users table from db.rs M1). Password hashing and the
first-start seeding of DEFAULT users belong to the auth work (F3), not here."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int | None
    email: str
    password_hash: str
    role: str
    is_active: bool


_ROW = "SELECT id, email, password_hash, role, is_active FROM users"


def _from_row(row: sqlite3.Row) -> User:
    return User(
        id=int(row["id"]),
        email=row["email"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=bool(row["is_active"]),
    )


def add_user(
    conn: sqlite3.Connection,
    email: str,
    password_hash: str,
    role: str,
    *,
    is_active: bool = True,
) -> int:
    """Insert a user. Raises sqlite3.IntegrityError on duplicate email."""
    cur = conn.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, ?)",
        (email, password_hash, role, 1 if is_active else 0),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_user(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute(_ROW + " WHERE id = ?", (user_id,)).fetchone()
    return _from_row(row) if row else None


def get_user_by_email(conn: sqlite3.Connection, email: str) -> User | None:
    row = conn.execute(_ROW + " WHERE email = ?", (email,)).fetchone()
    return _from_row(row) if row else None


def list_users(conn: sqlite3.Connection, *, include_inactive: bool = False) -> list[User]:
    sql = _ROW
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY id"
    return [_from_row(row) for row in conn.execute(sql)]


def set_user_active(conn: sqlite3.Connection, user_id: int, active: bool) -> None:
    conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if active else 0, user_id))
    conn.commit()


def update_user_password(conn: sqlite3.Connection, user_id: int, password_hash: str) -> None:
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
    )
    conn.commit()
