from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_current_user
from src.api.models import NoteCreateRequest, NoteListResponse, NoteResponse, NoteUpdateRequest
from src.db.repositories import create_note, delete_note, get_note, list_notes, update_note

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get(
    "",
    response_model=NoteListResponse,
    summary="List notes",
    description="List notes with pagination, search, and filtering by tag/pinned.",
    operation_id="notes_list",
)
async def list_notes_endpoint(
    q: str | None = Query(default=None, description="Search across title/content (case-insensitive)."),
    tag_id: str | None = Query(default=None, description="Filter to notes containing this tag."),
    pinned: bool | None = Query(default=None, description="Filter by pinned state."),
    limit: int = Query(default=50, ge=1, le=200, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Offset for pagination."),
    user=Depends(get_current_user),
) -> NoteListResponse:
    """List notes with filters."""
    items, total = await list_notes(
        user.user_id, q=q, tag_id=tag_id, pinned=pinned, limit=limit, offset=offset
    )
    next_offset = offset + limit if (offset + limit) < total else None
    return NoteListResponse(
        items=[NoteResponse(**n) for n in items],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
    )


@router.post(
    "",
    response_model=NoteResponse,
    status_code=201,
    summary="Create note",
    description="Create a note with optional tags and pinned state.",
    operation_id="notes_create",
)
async def create_note_endpoint(payload: NoteCreateRequest, user=Depends(get_current_user)) -> NoteResponse:
    """Create a note."""
    try:
        note = await create_note(
            user.user_id,
            title=payload.title,
            content=payload.content,
            pinned=payload.pinned,
            tag_ids=payload.tag_ids,
        )
        return NoteResponse(**note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get note",
    description="Get a single note by id.",
    operation_id="notes_get",
)
async def get_note_endpoint(note_id: str, user=Depends(get_current_user)) -> NoteResponse:
    """Get note."""
    note = await get_note(user.user_id, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    return NoteResponse(**note)


@router.patch(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update note (autosave)",
    description=(
        "Patch a note. Supports optimistic concurrency via if_unmodified_since. "
        "If the note was modified after that timestamp, returns 409."
    ),
    operation_id="notes_update",
)
async def update_note_endpoint(note_id: str, payload: NoteUpdateRequest, user=Depends(get_current_user)) -> NoteResponse:
    """Autosave-friendly note update endpoint."""
    try:
        note = await update_note(
            user.user_id,
            note_id,
            title=payload.title,
            content=payload.content,
            pinned=payload.pinned,
            tag_ids=payload.tag_ids,
            if_unmodified_since=payload.if_unmodified_since,
        )
        return NoteResponse(**note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{note_id}",
    status_code=204,
    response_model=None,
    summary="Delete note",
    description="Delete a note and its tag associations.",
    operation_id="notes_delete",
)
async def delete_note_endpoint(note_id: str, user=Depends(get_current_user)) -> None:
    """Delete note."""
    try:
        await delete_note(user.user_id, note_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


@router.post(
    "/{note_id}/pin",
    response_model=NoteResponse,
    summary="Pin note",
    description="Set note pinned=true.",
    operation_id="notes_pin",
)
async def pin_note(note_id: str, user=Depends(get_current_user)) -> NoteResponse:
    """Pin a note."""
    try:
        note = await update_note(
            user.user_id,
            note_id,
            title=None,
            content=None,
            pinned=True,
            tag_ids=None,
            if_unmodified_since=None,
        )
        return NoteResponse(**note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{note_id}/unpin",
    response_model=NoteResponse,
    summary="Unpin note",
    description="Set note pinned=false.",
    operation_id="notes_unpin",
)
async def unpin_note(note_id: str, user=Depends(get_current_user)) -> NoteResponse:
    """Unpin a note."""
    try:
        note = await update_note(
            user.user_id,
            note_id,
            title=None,
            content=None,
            pinned=False,
            tag_ids=None,
            if_unmodified_since=None,
        )
        return NoteResponse(**note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
