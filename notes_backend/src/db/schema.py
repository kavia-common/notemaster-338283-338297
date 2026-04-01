from __future__ import annotations

from src.db.connection import execute


# PUBLIC_INTERFACE
async def ensure_schema() -> None:
    """Create database tables if they do not exist.

    This keeps the template self-contained for demo/CI environments.
    For production, replace with Alembic migrations.
    """
    # Users
    await execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )

    # Notes
    await execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            pinned BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    await execute(
        "CREATE INDEX IF NOT EXISTS idx_notes_user_updated_at ON notes(user_id, updated_at DESC)"
    )
    await execute("CREATE INDEX IF NOT EXISTS idx_notes_user_pinned ON notes(user_id, pinned)")

    # Tags
    await execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            color TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            UNIQUE(user_id, name)
        )
        """
    )
    await execute("CREATE INDEX IF NOT EXISTS idx_tags_user_name ON tags(user_id, name)")

    # Note <-> Tags
    await execute(
        """
        CREATE TABLE IF NOT EXISTS note_tags (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (user_id, note_id, tag_id)
        )
        """
    )
    await execute("CREATE INDEX IF NOT EXISTS idx_note_tags_user_tag ON note_tags(user_id, tag_id)")

    # Settings
    await execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            theme TEXT NOT NULL DEFAULT 'light',
            autosave BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
