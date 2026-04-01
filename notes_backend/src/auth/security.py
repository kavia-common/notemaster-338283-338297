from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, status

from src.db.config import get_settings


@dataclass(frozen=True)
class TokenData:
    """Parsed token data for authenticated requests."""

    user_id: str
    email: str


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(message: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _now() -> int:
    return int(time.time())


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256.

    Stored format: pbkdf2_sha256$<iterations>$<salt_b64>$<dk_b64>
    """
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    salt = os.urandom(16)
    iterations = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    return f"pbkdf2_sha256${iterations}${_b64url_encode(salt)}${_b64url_encode(dk)}"


# PUBLIC_INTERFACE
def verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against stored hash."""
    try:
        algo, iters_s, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iters_s)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def _jwt_encode(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(_json_dumps(header))
    payload_b64 = _b64url_encode(_json_dumps(payload))
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig_b64 = _sign(message, secret)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _jwt_decode(token: str, secret: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc

    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = _sign(message, secret)
    if not hmac.compare_digest(expected_sig, sig_b64):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature.")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    return payload


# PUBLIC_INTERFACE
def create_access_token(user_id: str, email: str) -> str:
    """Create a signed JWT access token for a given user."""
    settings = get_settings()
    iat = _now()
    exp = iat + settings.access_token_exp_minutes * 60
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": user_id,
        "email": email,
        "iat": iat,
        "exp": exp,
        "typ": "access",
    }
    return _jwt_encode(payload, settings.jwt_secret)


# PUBLIC_INTERFACE
def decode_and_validate_token(token: str) -> TokenData:
    """Decode JWT and validate standard claims.

    Raises HTTPException(401) on failure.
    """
    settings = get_settings()
    payload = _jwt_decode(token, settings.jwt_secret)

    if payload.get("typ") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    if payload.get("iss") != settings.jwt_issuer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer.")

    aud = payload.get("aud")
    if aud != settings.jwt_audience:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience.")

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < _now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired.")

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    return TokenData(user_id=str(user_id), email=str(email))


# PUBLIC_INTERFACE
def bearer_token_from_header(auth_header: Optional[str]) -> str:
    """Parse the Bearer token from Authorization header."""
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header.")
    return parts[1].strip()
