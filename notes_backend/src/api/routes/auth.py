from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_user
from src.api.models import AuthResponse, LoginRequest, MeResponse, SignupRequest
from src.auth.security import create_access_token, hash_password, verify_password
from src.db.repositories import create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=201,
    summary="Sign up",
    description="Create a new user using email/password. Returns an access token.",
    operation_id="auth_signup",
)
async def signup(payload: SignupRequest) -> AuthResponse:
    """Create user and return an access token."""
    existing = await get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    pwd_hash = hash_password(payload.password)
    try:
        user = await create_user(payload.email, pwd_hash)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    token = create_access_token(user_id=user["id"], email=user["email"])
    return AuthResponse(access_token=token, user_id=user["id"], email=user["email"])


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login",
    description="Login using email/password. Returns an access token.",
    operation_id="auth_login",
)
async def login(payload: LoginRequest) -> AuthResponse:
    """Authenticate user and return an access token."""
    user = await get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    token = create_access_token(user_id=user["id"], email=user["email"])
    return AuthResponse(access_token=token, user_id=user["id"], email=user["email"])


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get current user",
    description="Return the authenticated user's identity.",
    operation_id="auth_me",
)
async def me(user=Depends(get_current_user)) -> MeResponse:
    """Return current user info."""
    return MeResponse(user_id=user.user_id, email=user.email)
