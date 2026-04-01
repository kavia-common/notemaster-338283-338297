from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_current_user
from src.api.models import TagCreateRequest, TagListResponse, TagResponse, TagUpdateRequest
from src.db.repositories import create_tag, delete_tag, get_tag, list_tags, update_tag

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get(
    "",
    response_model=TagListResponse,
    summary="List tags",
    description="List tags for the authenticated user, with optional search.",
    operation_id="tags_list",
)
async def list_tags_endpoint(
    q: str | None = Query(default=None, description="Search by tag name (case-insensitive)."),
    limit: int = Query(default=50, ge=1, le=200, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Offset for pagination."),
    user=Depends(get_current_user),
) -> TagListResponse:
    """List tags."""
    items, total = await list_tags(user.user_id, q=q, limit=limit, offset=offset)
    return TagListResponse(items=[TagResponse(**t) for t in items], total=total)


@router.post(
    "",
    response_model=TagResponse,
    status_code=201,
    summary="Create tag",
    description="Create a new tag (name unique per user).",
    operation_id="tags_create",
)
async def create_tag_endpoint(payload: TagCreateRequest, user=Depends(get_current_user)) -> TagResponse:
    """Create a tag."""
    try:
        tag = await create_tag(user.user_id, name=payload.name, color=payload.color)
        return TagResponse(**tag)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Get tag",
    description="Get a single tag by id.",
    operation_id="tags_get",
)
async def get_tag_endpoint(tag_id: str, user=Depends(get_current_user)) -> TagResponse:
    """Get a tag."""
    tag = await get_tag(user.user_id, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found.")
    return TagResponse(**tag)


@router.patch(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Update tag",
    description="Update an existing tag (patch).",
    operation_id="tags_update",
)
async def update_tag_endpoint(tag_id: str, payload: TagUpdateRequest, user=Depends(get_current_user)) -> TagResponse:
    """Update a tag."""
    try:
        tag = await update_tag(user.user_id, tag_id, name=payload.name, color=payload.color)
        return TagResponse(**tag)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{tag_id}",
    status_code=204,
    response_model=None,
    summary="Delete tag",
    description="Delete a tag. Also removes it from any notes.",
    operation_id="tags_delete",
)
async def delete_tag_endpoint(tag_id: str, user=Depends(get_current_user)) -> None:
    """Delete a tag."""
    try:
        await delete_tag(user.user_id, tag_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None
