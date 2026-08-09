"""Profile read/write for the signed-in wallet."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.models import Profile
from app.platform_models import AthleteProfile, ProfileRole
from app.schemas.profiles import AthleteProfileOut, AthleteProfileUpdate

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


@router.get("/me/roles", response_model=list[str])
async def read_roles(user: CurrentUserDep, session: SessionDep) -> list[str]:
    rows = await session.scalars(
        select(ProfileRole.role).where(ProfileRole.profile_id == user.id).order_by(ProfileRole.role)
    )
    return list(rows)


@router.post("/me/athlete", response_model=AthleteProfileOut)
async def activate_athlete(
    payload: AthleteProfileUpdate, user: CurrentUserDep, session: SessionDep
) -> AthleteProfile:
    profile = await session.scalar(select(Profile).where(Profile.id == user.id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    await session.execute(
        insert(ProfileRole)
        .values(profile_id=user.id, role="athlete")
        .on_conflict_do_nothing(index_elements=["profile_id", "role"])
    )
    athlete = await session.scalar(
        select(AthleteProfile).where(AthleteProfile.profile_id == user.id)
    )
    if athlete is None:
        athlete = AthleteProfile(profile_id=user.id, **payload.model_dump())
        session.add(athlete)
    else:
        for field, value in payload.model_dump().items():
            setattr(athlete, field, value)
    await session.flush()
    return athlete
