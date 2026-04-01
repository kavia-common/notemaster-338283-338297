from __future__ import annotations

from typing import Any, Optional

import asyncpg

from src.db.config import get_settings

_pool: Optional[asyncpg.Pool] = None


# PUBLIC_INTERFACE
async def init_db_pool() -> None:
    """Initialize the global asyncpg connection pool.

    This is called from the FastAPI startup hook.
    """
    global _pool
    if _pool is not None:
        return

    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.postgres_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )


# PUBLIC_INTERFACE
async def close_db_pool() -> None:
    """Close the global asyncpg connection pool (FastAPI shutdown hook)."""
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None


def _require_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. init_db_pool() was not called.")
    return _pool


# PUBLIC_INTERFACE
async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    """Fetch a single row."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


# PUBLIC_INTERFACE
async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Fetch multiple rows."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


# PUBLIC_INTERFACE
async def execute(query: str, *args: Any) -> str:
    """Execute a statement and return asyncpg status string."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


# PUBLIC_INTERFACE
async def transaction() -> asyncpg.transaction.Transaction:
    """Create a transaction context manager.

    Usage:
        async with (await transaction()):
            ...
    """
    pool = _require_pool()
    conn = await pool.acquire()
    tx = conn.transaction()

    # Wrap to ensure we release conn even if caller forgets:
    # We'll attach conn to the tx object for later release.
    setattr(tx, "_kavia_conn", conn)  # type: ignore[attr-defined]
    await tx.start()
    return tx


# PUBLIC_INTERFACE
async def commit_transaction(tx: asyncpg.transaction.Transaction) -> None:
    """Commit a transaction created by transaction()."""
    conn = getattr(tx, "_kavia_conn", None)
    try:
        await tx.commit()
    finally:
        if conn is not None:
            pool = _require_pool()
            await pool.release(conn)


# PUBLIC_INTERFACE
async def rollback_transaction(tx: asyncpg.transaction.Transaction) -> None:
    """Rollback a transaction created by transaction()."""
    conn = getattr(tx, "_kavia_conn", None)
    try:
        await tx.rollback()
    finally:
        if conn is not None:
            pool = _require_pool()
            await pool.release(conn)
