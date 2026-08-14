"""Pure fulfillment state machines for reward entitlements and reward orders.

`domain.campaigns.transition_campaign` is keyed by `(state, event)` because
campaign events arrive from the chain and must be translated. Fulfillment is the
opposite shape: an athlete picks the next state directly, so these maps are keyed
by state and expose the legal *targets*. That also lets a route hand the browser
the exact option list for a row without mirroring the machine in TypeScript.
"""

from __future__ import annotations

from enum import StrEnum


class FulfillmentValidationError(ValueError):
    """Raised when a fulfillment transition is not permitted."""


class EntitlementStatus(StrEnum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    IN_PROGRESS = "in_progress"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class OrderStatus(StrEnum):
    RESERVED = "reserved"
    AWAITING_DETAILS = "awaiting_details"
    IN_PROGRESS = "in_progress"
    SHIPPED = "shipped"
    SCHEDULED = "scheduled"
    FULFILLED = "fulfilled"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


# The projector inserts entitlements directly as `unlocked` - a tier that has not
# been earned has no row at all. `LOCKED` is retained because the database check
# constraint permits it and a future manual grant may need it.
_ENTITLEMENT_TARGETS: dict[EntitlementStatus, frozenset[EntitlementStatus]] = {
    EntitlementStatus.LOCKED: frozenset({EntitlementStatus.UNLOCKED}),
    EntitlementStatus.UNLOCKED: frozenset(
        {EntitlementStatus.IN_PROGRESS, EntitlementStatus.CANCELLED}
    ),
    EntitlementStatus.IN_PROGRESS: frozenset(
        {EntitlementStatus.FULFILLED, EntitlementStatus.CANCELLED}
    ),
    EntitlementStatus.FULFILLED: frozenset(),
    EntitlementStatus.CANCELLED: frozenset(),
}

_ORDER_TARGETS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.RESERVED: frozenset(
        {
            OrderStatus.AWAITING_DETAILS,
            OrderStatus.IN_PROGRESS,
            OrderStatus.REFUNDED,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.AWAITING_DETAILS: frozenset(
        {OrderStatus.IN_PROGRESS, OrderStatus.REFUNDED, OrderStatus.CANCELLED}
    ),
    OrderStatus.IN_PROGRESS: frozenset(
        {
            OrderStatus.SHIPPED,
            OrderStatus.SCHEDULED,
            OrderStatus.FULFILLED,
            OrderStatus.REFUNDED,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.SHIPPED: frozenset({OrderStatus.FULFILLED, OrderStatus.REFUNDED}),
    OrderStatus.SCHEDULED: frozenset({OrderStatus.FULFILLED, OrderStatus.REFUNDED}),
    OrderStatus.FULFILLED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

FULFILLMENT_TYPES = ("digital", "physical", "session")

# Shipping only makes sense for goods, and scheduling only for a booked session.
_TYPE_RESTRICTED_TARGETS: dict[OrderStatus, str] = {
    OrderStatus.SHIPPED: "physical",
    OrderStatus.SCHEDULED: "session",
}

# Refunding an order returns the points and the reserved inventory unit, so a
# route must run the compensating writes rather than only flipping the status.
REFUNDING_STATUSES = frozenset({OrderStatus.REFUNDED})


def parse_entitlement_status(value: str) -> EntitlementStatus:
    try:
        return EntitlementStatus(value)
    except ValueError as exc:
        raise FulfillmentValidationError(f"unknown entitlement status {value!r}") from exc


def parse_order_status(value: str) -> OrderStatus:
    try:
        return OrderStatus(value)
    except ValueError as exc:
        raise FulfillmentValidationError(f"unknown reward order status {value!r}") from exc


def allowed_entitlement_targets(current: EntitlementStatus) -> frozenset[EntitlementStatus]:
    """Return the statuses an entitlement may move to from `current`."""
    return _ENTITLEMENT_TARGETS[current]


def allowed_order_targets(current: OrderStatus, fulfillment_type: str) -> frozenset[OrderStatus]:
    """Return the statuses an order may move to, narrowed by its fulfillment type."""
    if fulfillment_type not in FULFILLMENT_TYPES:
        raise FulfillmentValidationError(f"unknown fulfillment type {fulfillment_type!r}")
    return frozenset(
        target
        for target in _ORDER_TARGETS[current]
        if _TYPE_RESTRICTED_TARGETS.get(target, fulfillment_type) == fulfillment_type
    )


def transition_entitlement(
    current: EntitlementStatus, target: EntitlementStatus
) -> EntitlementStatus:
    if target not in allowed_entitlement_targets(current):
        raise FulfillmentValidationError(
            f"entitlement cannot move from {current.value} to {target.value}"
        )
    return target


def transition_order(
    current: OrderStatus, target: OrderStatus, fulfillment_type: str
) -> OrderStatus:
    if target not in allowed_order_targets(current, fulfillment_type):
        raise FulfillmentValidationError(
            f"reward order cannot move from {current.value} to {target.value}"
        )
    return target
