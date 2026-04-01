from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.config import get_settings
from src.db.connection import close_db_pool, init_db_pool
from src.db.schema import ensure_schema

from src.api.routes.auth import router as auth_router
from src.api.routes.notes import router as notes_router
from src.api.routes.settings import router as settings_router
from src.api.routes.tags import router as tags_router

openapi_tags = [
    {"name": "health", "description": "Service health and diagnostics."},
    {"name": "auth", "description": "Email/password authentication and JWT token issuance."},
    {"name": "notes", "description": "CRUD APIs for notes, including search, pinning, and autosave semantics."},
    {"name": "tags", "description": "CRUD APIs for tags used to organize notes."},
    {"name": "settings", "description": "Settings sync endpoints (e.g., theme, autosave)."},
]

app = FastAPI(
    title="Notes Backend API",
    description=(
        "Backend for a notes application providing JWT auth and sync APIs for notes/tags/settings.\n\n"
        "Authentication: Use POST /api/auth/login or /api/auth/signup to obtain a Bearer token, then pass:\n"
        "  Authorization: Bearer <token>\n"
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins if settings.cors_allow_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    """Initialize database pool and ensure schema exists."""
    await init_db_pool()
    # Requires pgcrypto for gen_random_uuid(); ensure extension exists.
    # If permissions don't allow, schema creation will fail clearly.
    # We attempt to enable it for self-contained environments.
    from src.db.connection import execute  # local import to avoid cycles

    await execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    await ensure_schema()


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Close database pool."""
    await close_db_pool()


@app.get("/", tags=["health"], summary="Health check", operation_id="health_check")
async def health_check():
    """Basic health check endpoint."""
    return {"message": "Healthy"}


app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(tags_router)
app.include_router(settings_router)
