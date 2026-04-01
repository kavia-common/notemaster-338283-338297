import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    postgres_url: str
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    access_token_exp_minutes: int
    cors_allow_origins: list[str]


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Ask the orchestrator/user to set it in the container .env."
        )
    return value


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an int.") from exc


def _get_env_csv(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Load application settings from environment variables.

    Required:
      - POSTGRES_URL
      - JWT_SECRET

    Optional:
      - JWT_ISSUER (default: "notes-backend")
      - JWT_AUDIENCE (default: "notes-app")
      - ACCESS_TOKEN_EXP_MINUTES (default: 60*24*14)
      - CORS_ALLOW_ORIGINS (default: "*")
    """
    return Settings(
        postgres_url=_get_env("POSTGRES_URL"),
        jwt_secret=_get_env("JWT_SECRET"),
        jwt_issuer=os.getenv("JWT_ISSUER", "notes-backend"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "notes-app"),
        access_token_exp_minutes=_get_env_int("ACCESS_TOKEN_EXP_MINUTES", 60 * 24 * 14),
        cors_allow_origins=_get_env_csv("CORS_ALLOW_ORIGINS", "*"),
    )
