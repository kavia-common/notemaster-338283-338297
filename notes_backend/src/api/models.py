from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message.")


# -------- Auth --------
class SignupRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address.")
    password: str = Field(..., min_length=8, description="User password (min 8 chars).")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address.")
    password: str = Field(..., description="User password.")


class AuthResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    token_type: Literal["bearer"] = Field("bearer", description="Token type.")
    user_id: str = Field(..., description="Authenticated user id.")
    email: EmailStr = Field(..., description="Authenticated user email.")


class MeResponse(BaseModel):
    user_id: str = Field(..., description="Authenticated user id.")
    email: EmailStr = Field(..., description="Authenticated user email.")


# -------- Tags --------
class TagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Tag name.")
    color: Optional[str] = Field(
        None,
        max_length=20,
        description="Optional color identifier (e.g., hex '#3b82f6' or token).",
    )


class TagUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Updated tag name.")
    color: Optional[str] = Field(
        None,
        max_length=20,
        description="Updated optional color identifier.",
    )


class TagResponse(BaseModel):
    id: str = Field(..., description="Tag id.")
    name: str = Field(..., description="Tag name.")
    color: Optional[str] = Field(None, description="Tag color.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Update timestamp.")


class TagListResponse(BaseModel):
    items: list[TagResponse] = Field(..., description="List of tags.")
    total: int = Field(..., description="Total number of tags.")


# -------- Notes --------
class NoteCreateRequest(BaseModel):
    title: str = Field("", max_length=200, description="Note title.")
    content: str = Field("", description="Note content (markdown/plain text).")
    pinned: bool = Field(False, description="Whether note is pinned.")
    tag_ids: list[str] = Field(default_factory=list, description="Associated tag ids.")


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200, description="Updated title.")
    content: Optional[str] = Field(None, description="Updated content.")
    pinned: Optional[bool] = Field(None, description="Updated pinned state.")
    tag_ids: Optional[list[str]] = Field(None, description="Replace associated tags with these tag ids.")
    # Autosave semantics: if client passes if_unmodified_since and note was modified later, reject.
    if_unmodified_since: Optional[datetime] = Field(
        None,
        description="Optimistic concurrency control: only update if note not modified since this timestamp.",
    )


class NoteResponse(BaseModel):
    id: str = Field(..., description="Note id.")
    title: str = Field(..., description="Title.")
    content: str = Field(..., description="Content.")
    pinned: bool = Field(..., description="Pinned.")
    tag_ids: list[str] = Field(..., description="Associated tag ids.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Update timestamp.")


class NoteListResponse(BaseModel):
    items: list[NoteResponse] = Field(..., description="Notes page items.")
    total: int = Field(..., description="Total notes matching filter.")
    limit: int = Field(..., description="Page size.")
    offset: int = Field(..., description="Offset used.")
    next_offset: Optional[int] = Field(None, description="Offset for next page if any.")


# -------- Settings --------
class SettingsUpdateRequest(BaseModel):
    theme: Optional[Literal["light", "dark"]] = Field(None, description="Selected theme.")
    autosave: Optional[bool] = Field(None, description="Whether autosave is enabled.")


class SettingsResponse(BaseModel):
    theme: Literal["light", "dark"] = Field(..., description="Selected theme.")
    autosave: bool = Field(..., description="Whether autosave is enabled.")
    updated_at: datetime = Field(..., description="Last updated timestamp.")
