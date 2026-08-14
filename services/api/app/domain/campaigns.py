"""Pure campaign validation, canonical snapshots, and lifecycle rules."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any
from uuid import UUID


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    FUNDED = "funded"
    SUCCESSFUL = "successful"
    UNSUCCESSFUL = "unsuccessful"
    CANCELLED = "cancelled"


class CampaignEvent(StrEnum):
    PUBLISH_VERIFIED = "publish_verified"
    CANCEL_REQUESTED = "cancel_requested"
    SETTLEMENT_FUNDED = "settlement_funded"
    SETTLEMENT_SUCCESSFUL = "settlement_successful"
    SETTLEMENT_UNSUCCESSFUL = "settlement_unsuccessful"


class CampaignValidationError(ValueError):
    """A user-correctable campaign validation failure."""

    def __init__(self, message: str, *, field_errors: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.field_errors = field_errors or {}


def _amount(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CampaignValidationError(f"{field} must be greater than zero")
    return value


def _timestamp(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise CampaignValidationError(f"{field} must include a timezone")
    return value.astimezone(dt.UTC)


def validate_campaign_draft(input: Mapping[str, Any]) -> None:
    """Validate all cross-field campaign rules before persistence or publication."""
    unit_price = _amount(input.get("unit_price_atomic"), "unit_price_atomic")
    minimum = _amount(
        input.get("minimum_success_threshold_atomic"), "minimum_success_threshold_atomic"
    )
    main_goal = input.get("main_goal_atomic")
    if main_goal is not None and main_goal != 0:
        main_goal = _amount(main_goal, "main_goal_atomic")
        if main_goal < minimum:
            raise CampaignValidationError(
                "main_goal_atomic must be at least the minimum_success_threshold_atomic",
                field_errors={"main_goal_atomic": "must be at least the minimum threshold"},
            )

    start_at = _timestamp(input.get("start_at"), "start_at")
    end_at = _timestamp(input.get("end_at"), "end_at")
    if end_at <= start_at:
        raise CampaignValidationError("end_at must be after start_at")
    if end_at - start_at < dt.timedelta(hours=1):
        raise CampaignValidationError("campaign duration must be at least one hour")

    stretch_goals = input.get("stretch_goals_atomic") or []
    if not isinstance(stretch_goals, list) or len(stretch_goals) > 8:
        raise CampaignValidationError("stretch_goals_atomic must contain at most 8 goals")
    previous = main_goal or minimum
    for goal in stretch_goals:
        current = _amount(goal, "stretch_goals_atomic")
        if current <= previous:
            raise CampaignValidationError("stretch goals must be strictly increasing")
        previous = current

    tiers = input.get("reward_tiers") or []
    if not isinstance(tiers, list) or len(tiers) > 32:
        raise CampaignValidationError("reward_tiers must contain at most 32 tiers")
    previous_units = 0
    for tier in tiers:
        if not isinstance(tier, Mapping):
            raise CampaignValidationError("reward tier must be an object")
        required_units = tier.get("required_units")
        if not isinstance(required_units, int) or required_units <= previous_units:
            raise CampaignValidationError("reward tier thresholds must be strictly increasing")
        benefit = tier.get("benefit")
        if not isinstance(benefit, str) or not benefit.strip():
            raise CampaignValidationError("reward tier benefit must not be empty")
        max_supply = tier.get("max_supply")
        max_per_supporter = tier.get("max_per_supporter")
        if max_supply is not None and (not isinstance(max_supply, int) or max_supply <= 0):
            raise CampaignValidationError("reward tier max_supply must be greater than zero")
        # An entitlement is unique per (campaign, supporter, tier), so a tier can
        # never be held more than once. Reject any other value rather than accept
        # a limit the platform will not honour.
        if max_per_supporter is not None and max_per_supporter != 1:
            raise CampaignValidationError("reward tier max_per_supporter must be 1 when set")
        group = tier.get("reward_group")
        if group is not None and (not isinstance(group, str) or not 1 <= len(group) <= 40):
            raise CampaignValidationError(
                "reward tier reward_group must be 1 to 40 characters when set"
            )
        previous_units = required_units

    # Keep the local assignment explicit so static analyzers see these fields are consumed.
    _ = unit_price, start_at, end_at


def _canonical(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def canonical_campaign_snapshot(input: Mapping[str, Any], campaign_id: UUID, nonce: bytes) -> bytes:
    """Create deterministic bytes for the publication hash."""
    if len(nonce) != 16:
        raise CampaignValidationError("campaign nonce must be exactly 16 bytes")
    payload = {"campaign_id": campaign_id, "nonce": nonce, "terms": input}
    return json.dumps(_canonical(payload), separators=(",", ":"), sort_keys=True).encode("utf-8")


def campaign_snapshot_hash(snapshot: bytes) -> bytes:
    return hashlib.sha256(snapshot).digest()


def public_campaign_status(start_at: dt.datetime, now: dt.datetime | None = None) -> CampaignStatus:
    """Map a verified on-chain publication to its time-based public status."""
    if start_at.tzinfo is None:
        raise CampaignValidationError("start_at must include a timezone")
    observed_at = now or dt.datetime.now(tz=dt.UTC)
    if observed_at.tzinfo is None:
        raise CampaignValidationError("now must include a timezone")
    return (
        CampaignStatus.ACTIVE
        if observed_at.astimezone(dt.UTC) >= start_at.astimezone(dt.UTC)
        else CampaignStatus.SCHEDULED
    )


def transition_campaign(current: CampaignStatus, event: CampaignEvent) -> CampaignStatus:
    transitions: dict[tuple[CampaignStatus, CampaignEvent], CampaignStatus] = {
        (CampaignStatus.DRAFT, CampaignEvent.PUBLISH_VERIFIED): CampaignStatus.SCHEDULED,
        (CampaignStatus.DRAFT, CampaignEvent.CANCEL_REQUESTED): CampaignStatus.CANCELLED,
        (CampaignStatus.SCHEDULED, CampaignEvent.CANCEL_REQUESTED): CampaignStatus.CANCELLED,
        (CampaignStatus.ACTIVE, CampaignEvent.SETTLEMENT_FUNDED): CampaignStatus.FUNDED,
        (CampaignStatus.FUNDED, CampaignEvent.SETTLEMENT_SUCCESSFUL): CampaignStatus.SUCCESSFUL,
        (CampaignStatus.ACTIVE, CampaignEvent.SETTLEMENT_SUCCESSFUL): CampaignStatus.SUCCESSFUL,
        (CampaignStatus.ACTIVE, CampaignEvent.SETTLEMENT_UNSUCCESSFUL): CampaignStatus.UNSUCCESSFUL,
    }
    try:
        return transitions[(current, event)]
    except KeyError as exc:
        raise CampaignValidationError(
            f"campaign cannot transition from {current.value} using {event.value}"
        ) from exc
