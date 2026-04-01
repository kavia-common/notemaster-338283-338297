from __future__ import annotations

from fastapi import Header, HTTPException, status

from src.auth.security import TokenData, bearer_token_from_header, decode_and_validate_token
from src.db.repositories import get_user_by_id


# PUBLIC_INTERFACE
async def get_current_user(authorization: str | None = Header(default=None)) -> TokenData:
    """FastAPI dependency to authenticate requests using Bearer JWT."""
    token = bearer_token_from_header(authorization)
    token_data = decode_and_validate_token(token)

    user = await get_user_by_id(token_data.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return token_data
