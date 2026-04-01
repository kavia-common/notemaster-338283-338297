import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables (with safe fallbacks).

    Contracts / invariants:
    - A PostgreSQL DSN must be resolved either from environment or db_connection.txt.
    - JWT secret must be present (no fallback beyond env aliases).
    - CORS allow-origins is always a list of origins or ["*"].
    """

    postgres_url: str
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    access_token_exp_minutes: int
    cors_allow_origins: list[str]


def _get_env_any(names: list[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return None


def _get_env_required_any(names: list[str]) -> str:
    value = _get_env_any(names)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable. Tried: {', '.join(names)}. "
            "Ask the orchestrator/user to set it in the container .env."
        )
    return value


def _get_env_int_any(names: list[str], default: int) -> int:
    raw = _get_env_any(names)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {names[0]} must be an int.") from exc


def _get_env_csv_any(names: list[str], default: str) -> list[str]:
    raw = _get_env_any(names)
    if raw is None:
        raw = default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_postgres_dsn() -> str:
    """Resolve the PostgreSQL DSN for asyncpg.

    Resolution order:
    1) POSTGRES_URL env var (canonical)
    2) notes_database-style env vars (POSTGRES_USER/PASSWORD/DB/PORT) if present
    3) Parse db_connection.txt (supports 'psql postgresql://...' format)

    Errors:
    - Raises RuntimeError with actionable message if no DSN can be resolved.

    Side effects:
    - Reads db_connection.txt from the backend container root if needed.
    """
    dsn = _get_env_any(["POSTGRES_URL"])
    if dsn:
        return dsn

    # Optional adapter: if platform provided discrete DB vars.
    user = _get_env_any(["POSTGRES_USER"])
    pwd = _get_env_any(["POSTGRES_PASSWORD"])
    db = _get_env_any(["POSTGRES_DB"])
    port = _get_env_any(["POSTGRES_PORT"])
    host = _get_env_any(["POSTGRES_HOST"]) or "localhost"
    if user and pwd and db and port:
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    # Fall back to db_connection.txt in this container (common Kavia convention).
    # The database container has it, but this backend may also be configured with it.
    path = Path(__file__).resolve().parents[2] / "db_connection.txt"
    if path.exists():
        raw = path.read_text(encoding="utf-8").strip()
        # Accept either a bare DSN or "psql <dsn>".
        if raw.startswith("psql "):
            raw = raw[len("psql ") :].strip()
        if raw.startswith("postgresql://") or raw.startswith("postgres://"):
            return raw

    raise RuntimeError(
        "Unable to resolve PostgreSQL DSN. Provide POSTGRES_URL (recommended) "
        "or ensure db_connection.txt exists (psql postgresql://user:pass@host:port/db)."
    )


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Load application settings from environment variables.

    Required (canonical):
      - POSTGRES_URL
      - JWT_SECRET
      - CORS_ALLOW_ORIGINS (optional, default "*")

    Integration aliases supported (to match existing container .env):
      - POSTGRES_URL: (no alias; may fall back to db_connection.txt)
      - JWT_SECRET: JWT_SECRET
      - CORS_ALLOW_ORIGINS: CORS_ALLOW_ORIGINS or ALLOWED_ORIGINS
      - ACCESS_TOKEN_EXP_MINUTES: ACCESS_TOKEN_EXP_MINUTES (no alias)
      - JWT_ISSUER/JWT_AUDIENCE: same names

    Notes:
    - This function is the single canonical settings entrypoint for the backend.
    """
    return Settings(
        postgres_url=_resolve_postgres_dsn(),
        jwt_secret=_get_env_required_any(["JWT_SECRET"]),
        jwt_issuer=os.getenv("JWT_ISSUER", "notes-backend"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "notes-app"),
        access_token_exp_minutes=_get_env_int_any(["ACCESS_TOKEN_EXP_MINUTES"], 60 * 24 * 14),
        cors_allow_origins=_get_env_csv_any(["CORS_ALLOW_ORIGINS", "ALLOWED_ORIGINS"], "*"),
    )
