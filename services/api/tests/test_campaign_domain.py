from __future__ import annotations

import datetime as dt
from uuid import UUID

import pytest

from app.domain.campaigns import (
    CampaignEvent,
    CampaignStatus,
    CampaignValidationError,
    campaign_snapshot_hash,
    canonical_campaign_snapshot,
    transition_campaign,
    validate_campaign_draft,
)


def valid_campaign_input(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "unit_price_atomic": 25_000_000,
        "minimum_success_threshold_atomic": 800_000_000,
        "main_goal_atomic": 1_000_000_000,
        "stretch_goals_atomic": [1_250_000_000, 1_500_000_000],
        "start_at": dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
        "end_at": dt.datetime(2026, 10, 1, tzinfo=dt.UTC),
        "reward_tiers": [
            {"required_units": 1, "benefit": "Digital thank-you"},
            {"required_units": 5, "benefit": "Signed photo", "max_supply": 20},
        ],
    }
    value.update(overrides)
    return value


def test_campaign_requires_monotonic_goals() -> None:
    with pytest.raises(CampaignValidationError, match="main_goal_atomic"):
        validate_campaign_draft(valid_campaign_input(main_goal_atomic=700_000_000))


def test_campaign_rejects_non_increasing_stretch_goals() -> None:
    with pytest.raises(CampaignValidationError, match="strictly increasing"):
        validate_campaign_draft(
            valid_campaign_input(stretch_goals_atomic=[900_000_000, 900_000_000])
        )


def test_campaign_rejects_invalid_schedule() -> None:
    with pytest.raises(CampaignValidationError, match="end_at"):
        validate_campaign_draft(
            valid_campaign_input(
                start_at=dt.datetime(2026, 10, 1, tzinfo=dt.UTC),
                end_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
            )
        )


def test_snapshot_hash_is_stable_for_equivalent_inputs() -> None:
    first = canonical_campaign_snapshot(
        valid_campaign_input(), UUID("00000000-0000-0000-0000-000000000001"), b"nonce-16-bytes!!"
    )
    second = canonical_campaign_snapshot(
        valid_campaign_input(), UUID("00000000-0000-0000-0000-000000000001"), b"nonce-16-bytes!!"
    )
    assert campaign_snapshot_hash(first) == campaign_snapshot_hash(second)


def test_transition_matrix_rejects_illegal_events() -> None:
    assert (
        transition_campaign(CampaignStatus.DRAFT, CampaignEvent.PUBLISH_VERIFIED)
        == CampaignStatus.ACTIVE
    )
    assert (
        transition_campaign(CampaignStatus.DRAFT, CampaignEvent.CANCEL_REQUESTED)
        == CampaignStatus.CANCELLED
    )
    with pytest.raises(CampaignValidationError, match="cannot transition"):
        transition_campaign(CampaignStatus.ACTIVE, CampaignEvent.CANCEL_REQUESTED)
