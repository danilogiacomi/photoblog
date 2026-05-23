import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS catalogues (
            id          INTEGER PRIMARY KEY,
            slug        TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            description TEXT,
            date        TEXT,
            location    TEXT,
            cover_image TEXT,
            tags        TEXT,
            photo_count INTEGER DEFAULT 0,
            indexed_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS photos (
            id           INTEGER PRIMARY KEY,
            catalogue_id INTEGER NOT NULL REFERENCES catalogues(id) ON DELETE CASCADE,
            filename     TEXT NOT NULL,
            title        TEXT,
            caption      TEXT,
            date         TEXT,
            location     TEXT,
            tags         TEXT,
            exif_raw     TEXT,
            aspect_ratio REAL,
            UNIQUE(catalogue_id, filename)
        );
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'admin'
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL
        );
    """)
    conn.commit()


def upsert_catalogue(
    conn: sqlite3.Connection,
    *,
    slug: str,
    title: str,
    description: str | None = None,
    date: str | None = None,
    location: str | None = None,
    cover_image: str | None = None,
    tags: list | None = None,
    photo_count: int = 0,
) -> int:
    tags_json = json.dumps(tags or [])
    indexed_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO catalogues
            (slug, title, description, date, location, cover_image, tags, photo_count, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            title=excluded.title,
            description=excluded.description,
            date=excluded.date,
            location=excluded.location,
            cover_image=excluded.cover_image,
            tags=excluded.tags,
            photo_count=excluded.photo_count,
            indexed_at=excluded.indexed_at
        """,
        (slug, title, description, date, location, cover_image, tags_json, photo_count, indexed_at),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM catalogues WHERE slug = ?", (slug,)).fetchone()
    return row["id"]


def upsert_photo(
    conn: sqlite3.Connection,
    *,
    catalogue_id: int,
    filename: str,
    title: str | None = None,
    caption: str | None = None,
    date: str | None = None,
    location: str | None = None,
    tags: list | None = None,
    exif_raw: dict | None = None,
    aspect_ratio: float | None = None,
) -> None:
    tags_json = json.dumps(tags or [])
    exif_json = json.dumps(exif_raw or {})
    conn.execute(
        """
        INSERT INTO photos
            (catalogue_id, filename, title, caption, date, location, tags, exif_raw, aspect_ratio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalogue_id, filename) DO UPDATE SET
            title=excluded.title,
            caption=excluded.caption,
            date=excluded.date,
            location=excluded.location,
            tags=excluded.tags,
            exif_raw=excluded.exif_raw,
            aspect_ratio=excluded.aspect_ratio
        """,
        (catalogue_id, filename, title, caption, date, location, tags_json, exif_json, aspect_ratio),
    )
    conn.commit()


def delete_missing_catalogues(conn: sqlite3.Connection, existing_slugs: list[str]) -> None:
    if not existing_slugs:
        conn.execute("DELETE FROM catalogues")
    else:
        placeholders = ",".join("?" * len(existing_slugs))
        conn.execute(f"DELETE FROM catalogues WHERE slug NOT IN ({placeholders})", existing_slugs)
    conn.commit()


def delete_missing_photos(
    conn: sqlite3.Connection, catalogue_id: int, existing_filenames: list[str]
) -> None:
    if not existing_filenames:
        conn.execute("DELETE FROM photos WHERE catalogue_id = ?", (catalogue_id,))
    else:
        placeholders = ",".join("?" * len(existing_filenames))
        conn.execute(
            f"DELETE FROM photos WHERE catalogue_id = ? AND filename NOT IN ({placeholders})",
            [catalogue_id, *existing_filenames],
        )
    conn.commit()


def get_all_catalogues(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM catalogues ORDER BY date DESC NULLS LAST, title ASC"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_catalogue_by_slug(conn: sqlite3.Connection, slug: str) -> dict | None:
    row = conn.execute("SELECT * FROM catalogues WHERE slug = ?", (slug,)).fetchone()
    return _row_to_dict(row) if row else None


def get_photos_by_catalogue(conn: sqlite3.Connection, catalogue_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM photos WHERE catalogue_id = ? ORDER BY date ASC NULLS LAST, filename ASC",
        (catalogue_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_photo(conn: sqlite3.Connection, catalogue_id: int, filename: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM photos WHERE catalogue_id = ? AND filename = ?",
        (catalogue_id, filename),
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_adjacent_photos(
    conn: sqlite3.Connection, catalogue_id: int, filename: str
) -> tuple[dict | None, dict | None]:
    photos = get_photos_by_catalogue(conn, catalogue_id)
    filenames = [p["filename"] for p in photos]
    try:
        idx = filenames.index(filename)
    except ValueError:
        return None, None
    prev_photo = photos[idx - 1] if idx > 0 else None
    next_photo = photos[idx + 1] if idx < len(photos) - 1 else None
    return prev_photo, next_photo


def create_user(
    conn: sqlite3.Connection, *, username: str, password_hash: str, role: str = "admin"
) -> None:
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role),
    )
    conn.commit()


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def create_session(
    conn: sqlite3.Connection, *, token: str, user_id: int, expires_at: str
) -> None:
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    conn.commit()


def get_session_user(conn: sqlite3.Connection, token: str) -> Optional[dict]:
    now = datetime.now(timezone.utc).isoformat()
    row = conn.execute(
        """
        SELECT u.* FROM users u
        JOIN sessions s ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now),
    ).fetchone()
    return dict(row) if row else None


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("tags",):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
        else:
            d[key] = []
    if d.get("exif_raw"):
        try:
            d["exif_raw"] = json.loads(d["exif_raw"])
        except (json.JSONDecodeError, TypeError):
            d["exif_raw"] = {}
    else:
        d["exif_raw"] = {}
    return d
