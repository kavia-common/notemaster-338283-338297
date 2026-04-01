from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import asyncpg

from src.db.connection import execute, fetch, fetchrow


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------- Users ----------------
# PUBLIC_INTERFACE
async def create_user(email: str, password_hash: str) -> dict:
    """Create a new user; raises ValueError if email already exists."""
    try:
        row = await fetchrow(
            """
            INSERT INTO users (email, password_hash, created_at, updated_at)
            VALUES ($1, $2, NOW(), NOW())
            RETURNING id::text AS id, email, created_at, updated_at
            """,
            email.lower(),
            password_hash,
        )
    except asyncpg.UniqueViolationError as exc:
        raise ValueError("Email already registered.") from exc

    if row is None:
        raise RuntimeError("Failed to create user.")
    return dict(row)


# PUBLIC_INTERFACE
async def get_user_by_email(email: str) -> Optional[dict]:
    """Fetch a user by email."""
    row = await fetchrow(
        """
        SELECT id::text AS id, email, password_hash, created_at, updated_at
        FROM users
        WHERE email = $1
        """,
        email.lower(),
    )
    return dict(row) if row else None


# PUBLIC_INTERFACE
async def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch a user by id."""
    row = await fetchrow(
        """
        SELECT id::text AS id, email, password_hash, created_at, updated_at
        FROM users
        WHERE id = $1::uuid
        """,
        user_id,
    )
    return dict(row) if row else None


# ---------------- Tags ----------------
# PUBLIC_INTERFACE
async def create_tag(user_id: str, name: str, color: Optional[str]) -> dict:
    """Create a tag for a user; name is unique per user."""
    try:
        row = await fetchrow(
            """
            INSERT INTO tags (user_id, name, color, created_at, updated_at)
            VALUES ($1::uuid, $2, $3, NOW(), NOW())
            RETURNING id::text AS id, name, color, created_at, updated_at
            """,
            user_id,
            name.strip(),
            color,
        )
    except asyncpg.UniqueViolationError as exc:
        raise ValueError("Tag name already exists.") from exc

    if row is None:
        raise RuntimeError("Failed to create tag.")
    return dict(row)


# PUBLIC_INTERFACE
async def list_tags(user_id: str, q: Optional[str], limit: int, offset: int) -> tuple[list[dict], int]:
    """List tags for user with optional case-insensitive search."""
    q_filter = (q or "").strip()
    where = "WHERE user_id = $1::uuid"
    args: list = [user_id]
    if q_filter:
        where += " AND name ILIKE $2"
        args.append(f"%{q_filter}%")

    total_row = await fetchrow(f"SELECT COUNT(*) AS c FROM tags {where}", *args)
    total = int(total_row["c"]) if total_row else 0

    # Pagination args
    args_page = args + [limit, offset]
    rows = await fetch(
        f"""
        SELECT id::text AS id, name, color, created_at, updated_at
        FROM tags
        {where}
        ORDER BY name ASC
        LIMIT ${len(args)+1} OFFSET ${len(args)+2}
        """,
        *args_page,
    )
    return [dict(r) for r in rows], total


# PUBLIC_INTERFACE
async def get_tag(user_id: str, tag_id: str) -> Optional[dict]:
    """Get a tag by id for user."""
    row = await fetchrow(
        """
        SELECT id::text AS id, name, color, created_at, updated_at
        FROM tags
        WHERE user_id = $1::uuid AND id = $2::uuid
        """,
        user_id,
        tag_id,
    )
    return dict(row) if row else None


# PUBLIC_INTERFACE
async def update_tag(user_id: str, tag_id: str, name: Optional[str], color: Optional[str]) -> dict:
    """Update tag fields."""
    existing = await get_tag(user_id, tag_id)
    if not existing:
        raise KeyError("Tag not found.")

    new_name = name.strip() if name is not None else existing["name"]
    new_color = color if color is not None else existing["color"]

    try:
        row = await fetchrow(
            """
            UPDATE tags
            SET name = $1, color = $2, updated_at = NOW()
            WHERE user_id = $3::uuid AND id = $4::uuid
            RETURNING id::text AS id, name, color, created_at, updated_at
            """,
            new_name,
            new_color,
            user_id,
            tag_id,
        )
    except asyncpg.UniqueViolationError as exc:
        raise ValueError("Tag name already exists.") from exc

    if row is None:
        raise RuntimeError("Failed to update tag.")
    return dict(row)


# PUBLIC_INTERFACE
async def delete_tag(user_id: str, tag_id: str) -> None:
    """Delete tag and its associations."""
    await execute(
        "DELETE FROM note_tags WHERE user_id = $1::uuid AND tag_id = $2::uuid",
        user_id,
        tag_id,
    )
    status = await execute(
        "DELETE FROM tags WHERE user_id = $1::uuid AND id = $2::uuid",
        user_id,
        tag_id,
    )
    if status.startswith("DELETE 0"):
        raise KeyError("Tag not found.")


# ---------------- Notes ----------------
# PUBLIC_INTERFACE
async def create_note(user_id: str, title: str, content: str, pinned: bool, tag_ids: list[str]) -> dict:
    """Create a note and set its tags."""
    row = await fetchrow(
        """
        INSERT INTO notes (user_id, title, content, pinned, created_at, updated_at)
        VALUES ($1::uuid, $2, $3, $4, NOW(), NOW())
        RETURNING id::text AS id, title, content, pinned, created_at, updated_at
        """,
        user_id,
        title or "",
        content or "",
        pinned,
    )
    if row is None:
        raise RuntimeError("Failed to create note.")

    note = dict(row)
    await replace_note_tags(user_id, note["id"], tag_ids)
    note["tag_ids"] = await list_note_tag_ids(user_id, note["id"])
    return note


async def list_note_tag_ids(user_id: str, note_id: str) -> list[str]:
    rows = await fetch(
        """
        SELECT tag_id::text AS tag_id
        FROM note_tags
        WHERE user_id = $1::uuid AND note_id = $2::uuid
        ORDER BY created_at ASC
        """,
        user_id,
        note_id,
    )
    return [r["tag_id"] for r in rows]


async def replace_note_tags(user_id: str, note_id: str, tag_ids: list[str]) -> None:
    # Ensure tags belong to user
    if tag_ids:
        rows = await fetch(
            """
            SELECT id::text AS id
            FROM tags
            WHERE user_id = $1::uuid AND id = ANY($2::uuid[])
            """,
            user_id,
            tag_ids,
        )
        found = {r["id"] for r in rows}
        missing = [t for t in tag_ids if t not in found]
        if missing:
            raise ValueError("One or more tag_ids do not exist.")

    await execute(
        "DELETE FROM note_tags WHERE user_id = $1::uuid AND note_id = $2::uuid",
        user_id,
        note_id,
    )
    for tag_id in tag_ids:
        await execute(
            """
            INSERT INTO note_tags (user_id, note_id, tag_id, created_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, NOW())
            """,
            user_id,
            note_id,
            tag_id,
        )


# PUBLIC_INTERFACE
async def get_note(user_id: str, note_id: str) -> Optional[dict]:
    """Get note with tag_ids."""
    row = await fetchrow(
        """
        SELECT id::text AS id, title, content, pinned, created_at, updated_at
        FROM notes
        WHERE user_id = $1::uuid AND id = $2::uuid
        """,
        user_id,
        note_id,
    )
    if not row:
        return None
    note = dict(row)
    note["tag_ids"] = await list_note_tag_ids(user_id, note_id)
    return note


# PUBLIC_INTERFACE
async def list_notes(
    user_id: str,
    q: Optional[str],
    tag_id: Optional[str],
    pinned: Optional[bool],
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """List notes with filters and pagination. Search applies to title/content."""
    clauses = ["user_id = $1::uuid"]
    args: list = [user_id]
    idx = 2

    q_filter = (q or "").strip()
    if q_filter:
        clauses.append(f"(title ILIKE ${idx} OR content ILIKE ${idx})")
        args.append(f"%{q_filter}%")
        idx += 1

    if pinned is not None:
        clauses.append(f"pinned = ${idx}")
        args.append(pinned)
        idx += 1

    if tag_id:
        # Use EXISTS against note_tags
        clauses.append(
            f"""EXISTS (
                SELECT 1 FROM note_tags nt
                WHERE nt.user_id = notes.user_id
                  AND nt.note_id = notes.id
                  AND nt.tag_id = ${idx}::uuid
            )"""
        )
        args.append(tag_id)
        idx += 1

    where = "WHERE " + " AND ".join(clauses)

    total_row = await fetchrow(f"SELECT COUNT(*) AS c FROM notes {where}", *args)
    total = int(total_row["c"]) if total_row else 0

    args_page = args + [limit, offset]
    rows = await fetch(
        f"""
        SELECT id::text AS id, title, content, pinned, created_at, updated_at
        FROM notes
        {where}
        ORDER BY pinned DESC, updated_at DESC
        LIMIT ${idx} OFFSET ${idx+1}
        """,
        *args_page,
    )

    items: list[dict] = []
    for r in rows:
        note = dict(r)
        note["tag_ids"] = await list_note_tag_ids(user_id, note["id"])
        items.append(note)

    return items, total


# PUBLIC_INTERFACE
async def update_note(
    user_id: str,
    note_id: str,
    title: Optional[str],
    content: Optional[str],
    pinned: Optional[bool],
    tag_ids: Optional[list[str]],
    if_unmodified_since: Optional[datetime],
) -> dict:
    """Update note with autosave/concurrency semantics."""
    existing = await get_note(user_id, note_id)
    if not existing:
        raise KeyError("Note not found.")

    if if_unmodified_since is not None:
        # Normalize tz-aware: assume UTC if naive
        check_ts = if_unmodified_since
        if check_ts.tzinfo is None:
            check_ts = check_ts.replace(tzinfo=timezone.utc)
        updated_at: datetime = existing["updated_at"]
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if updated_at > check_ts:
            raise PermissionError("Note was modified by another session.")

    new_title = title if title is not None else existing["title"]
    new_content = content if content is not None else existing["content"]
    new_pinned = pinned if pinned is not None else existing["pinned"]

    row = await fetchrow(
        """
        UPDATE notes
        SET title = $1, content = $2, pinned = $3, updated_at = NOW()
        WHERE user_id = $4::uuid AND id = $5::uuid
        RETURNING id::text AS id, title, content, pinned, created_at, updated_at
        """,
        new_title,
        new_content,
        new_pinned,
        user_id,
        note_id,
    )
    if row is None:
        raise RuntimeError("Failed to update note.")

    if tag_ids is not None:
        await replace_note_tags(user_id, note_id, tag_ids)

    note = dict(row)
    note["tag_ids"] = await list_note_tag_ids(user_id, note_id)
    return note


# PUBLIC_INTERFACE
async def delete_note(user_id: str, note_id: str) -> None:
    """Delete note and its tag associations."""
    await execute(
        "DELETE FROM note_tags WHERE user_id = $1::uuid AND note_id = $2::uuid",
        user_id,
        note_id,
    )
    status = await execute(
        "DELETE FROM notes WHERE user_id = $1::uuid AND id = $2::uuid",
        user_id,
        note_id,
    )
    if status.startswith("DELETE 0"):
        raise KeyError("Note not found.")


# ---------------- Settings ----------------
# PUBLIC_INTERFACE
async def get_settings(user_id: str) -> dict:
    """Get settings row for user; if missing, create defaults."""
    row = await fetchrow(
        """
        SELECT user_id::text AS user_id, theme, autosave, updated_at
        FROM settings
        WHERE user_id = $1::uuid
        """,
        user_id,
    )
    if row:
        return dict(row)

    # Create defaults
    row2 = await fetchrow(
        """
        INSERT INTO settings (user_id, theme, autosave, created_at, updated_at)
        VALUES ($1::uuid, 'light', TRUE, NOW(), NOW())
        RETURNING user_id::text AS user_id, theme, autosave, updated_at
        """,
        user_id,
    )
    if row2 is None:
        raise RuntimeError("Failed to initialize settings.")
    return dict(row2)


# PUBLIC_INTERFACE
async def update_settings(user_id: str, theme: Optional[str], autosave: Optional[bool]) -> dict:
    """Update user settings (patch)."""
    current = await get_settings(user_id)
    new_theme = theme if theme is not None else current["theme"]
    new_autosave = autosave if autosave is not None else current["autosave"]

    row = await fetchrow(
        """
        UPDATE settings
        SET theme = $1, autosave = $2, updated_at = NOW()
        WHERE user_id = $3::uuid
        RETURNING user_id::text AS user_id, theme, autosave, updated_at
        """,
        new_theme,
        new_autosave,
        user_id,
    )
    if row is None:
        raise RuntimeError("Failed to update settings.")
    return dict(row)
