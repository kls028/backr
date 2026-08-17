"""Response-schema contracts for profile routes.

`AthleteProfileOut` declared its ids as `str` while the ORM supplies `UUID`.
Pydantic v2 does not coerce between them, so every *successful* athlete
activation raised ResponseValidationError and surfaced as a 500 — after the row
had already been written and then rolled back. Typed ids and `from_attributes`
are both load-bearing, so both are pinned here.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.profiles import AthleteProfileOut, AthleteProfileUpdate


class _Row:
    """Stands in for the SQLAlchemy AthleteProfile row."""

    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.profile_id = uuid.uuid4()
        self.display_name = "Mara Lindqvist"
        self.sport = "Tennis"
        self.bio = None
        self.avatar_uri = None


def test_builds_from_an_orm_row_with_uuid_ids() -> None:
    row = _Row()
    out = AthleteProfileOut.model_validate(row)
    assert out.id == row.id
    assert out.profile_id == row.profile_id
    assert out.display_name == "Mara Lindqvist"


def test_ids_serialise_to_strings_for_the_browser() -> None:
    """The frontend types these as `string`, so the JSON shape must not change."""
    row = _Row()
    payload = AthleteProfileOut.model_validate(row).model_dump(mode="json")
    assert payload["id"] == str(row.id)
    assert isinstance(payload["id"], str)
    assert isinstance(payload["profile_id"], str)


def test_display_name_is_still_required_and_bounded() -> None:
    with pytest.raises(ValidationError):
        AthleteProfileUpdate(display_name="")
    with pytest.raises(ValidationError):
        AthleteProfileUpdate(display_name="x" * 81)


def test_unknown_fields_are_rejected_on_input() -> None:
    with pytest.raises(ValidationError):
        AthleteProfileUpdate(display_name="Mara", unexpected="value")
