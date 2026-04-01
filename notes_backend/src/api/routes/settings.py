from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.api.models import SettingsResponse, SettingsUpdateRequest
from src.db.repositories import get_settings as repo_get_settings
from src.db.repositories import update_settings as repo_update_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get settings",
    description="Fetch settings for the authenticated user (creates defaults if missing).",
    operation_id="settings_get",
)
async def get_settings(user=Depends(get_current_user)) -> SettingsResponse:
    """Get settings."""
    data = await repo_get_settings(user.user_id)
    return SettingsResponse(**data)


@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Patch settings for the authenticated user.",
    operation_id="settings_update",
)
async def patch_settings(payload: SettingsUpdateRequest, user=Depends(get_current_user)) -> SettingsResponse:
    """Patch settings."""
    try:
        data = await repo_update_settings(user.user_id, theme=payload.theme, autosave=payload.autosave)
        return SettingsResponse(**data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
