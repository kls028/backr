"""Profile read/write for the signed-in wallet."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.models import Profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wallet: str | None
    display_name: str | None
    created_at: dt.datetime


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)


@router.get("/me", response_model=ProfileOut)
async def read_me(user: CurrentUserDep, session: SessionDep) -> Profile:
    profile = await session.scalar(select(Profile).where(Profile.id == user.id))
    if profile is None:
        # The on_auth_user_created trigger should have made this row. If it is
        # missing, the trigger is broken -- surface it rather than papering over.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile row missing for authenticated user",
        )
    return profile


@router.patch("/me", response_model=ProfileOut)
async def update_me(payload: ProfileUpdate, user: CurrentUserDep, session: SessionDep) -> Profile:
    profile = await session.scalar(select(Profile).where(Profile.id == user.id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    if payload.display_name is not None:
        profile.display_name = payload.display_name

    await session.flush()
    return profile
