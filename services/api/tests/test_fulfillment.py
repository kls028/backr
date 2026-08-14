import pytest

from app.domain.fulfillment import (
    EntitlementStatus,
    FulfillmentValidationError,
    OrderStatus,
    allowed_entitlement_targets,
    allowed_order_targets,
    parse_entitlement_status,
    parse_order_status,
    transition_entitlement,
    transition_order,
)


def test_entitlement_walks_the_happy_path() -> None:
    current = EntitlementStatus.UNLOCKED
    current = transition_entitlement(current, EntitlementStatus.IN_PROGRESS)
    current = transition_entitlement(current, EntitlementStatus.FULFILLED)

    assert current is EntitlementStatus.FULFILLED


def test_entitlement_terminal_states_allow_nothing() -> None:
    assert allowed_entitlement_targets(EntitlementStatus.FULFILLED) == frozenset()
    assert allowed_entitlement_targets(EntitlementStatus.CANCELLED) == frozenset()
    with pytest.raises(FulfillmentValidationError):
        transition_entitlement(EntitlementStatus.FULFILLED, EntitlementStatus.IN_PROGRESS)


def test_entitlement_cannot_skip_to_fulfilled() -> None:
    with pytest.raises(FulfillmentValidationError):
        transition_entitlement(EntitlementStatus.UNLOCKED, EntitlementStatus.FULFILLED)


def test_physical_order_walks_to_fulfilled_via_shipped() -> None:
    current = OrderStatus.RESERVED
    current = transition_order(current, OrderStatus.AWAITING_DETAILS, "physical")
    current = transition_order(current, OrderStatus.IN_PROGRESS, "physical")
    current = transition_order(current, OrderStatus.SHIPPED, "physical")
    current = transition_order(current, OrderStatus.FULFILLED, "physical")

    assert current is OrderStatus.FULFILLED


def test_session_order_walks_to_fulfilled_via_scheduled() -> None:
    current = transition_order(OrderStatus.IN_PROGRESS, OrderStatus.SCHEDULED, "session")

    assert transition_order(current, OrderStatus.FULFILLED, "session") is OrderStatus.FULFILLED


def test_shipping_and_scheduling_are_narrowed_by_fulfillment_type() -> None:
    physical = allowed_order_targets(OrderStatus.IN_PROGRESS, "physical")
    session = allowed_order_targets(OrderStatus.IN_PROGRESS, "session")
    digital = allowed_order_targets(OrderStatus.IN_PROGRESS, "digital")

    assert OrderStatus.SHIPPED in physical
    assert OrderStatus.SCHEDULED not in physical
    assert OrderStatus.SCHEDULED in session
    assert OrderStatus.SHIPPED not in session
    assert OrderStatus.SHIPPED not in digital
    assert OrderStatus.SCHEDULED not in digital
    assert OrderStatus.FULFILLED in digital


def test_a_digital_order_cannot_ship() -> None:
    with pytest.raises(FulfillmentValidationError):
        transition_order(OrderStatus.IN_PROGRESS, OrderStatus.SHIPPED, "digital")


def test_refund_is_reachable_from_every_open_state() -> None:
    for current in (
        OrderStatus.RESERVED,
        OrderStatus.AWAITING_DETAILS,
        OrderStatus.IN_PROGRESS,
        OrderStatus.SHIPPED,
        OrderStatus.SCHEDULED,
    ):
        fulfillment_type = "physical" if current is OrderStatus.SHIPPED else "session"
        assert (
            transition_order(current, OrderStatus.REFUNDED, fulfillment_type)
            is OrderStatus.REFUNDED
        )


def test_order_terminal_states_allow_nothing() -> None:
    for current in (OrderStatus.FULFILLED, OrderStatus.REFUNDED, OrderStatus.CANCELLED):
        assert allowed_order_targets(current, "digital") == frozenset()
    with pytest.raises(FulfillmentValidationError):
        transition_order(OrderStatus.REFUNDED, OrderStatus.IN_PROGRESS, "digital")


def test_an_order_cannot_move_backwards() -> None:
    with pytest.raises(FulfillmentValidationError):
        transition_order(OrderStatus.IN_PROGRESS, OrderStatus.RESERVED, "digital")


def test_unknown_statuses_and_types_are_rejected() -> None:
    with pytest.raises(FulfillmentValidationError):
        parse_order_status("posted")
    with pytest.raises(FulfillmentValidationError):
        parse_entitlement_status("granted")
    with pytest.raises(FulfillmentValidationError):
        allowed_order_targets(OrderStatus.RESERVED, "carrier-pigeon")


def test_status_parsing_round_trips() -> None:
    assert parse_order_status("awaiting_details") is OrderStatus.AWAITING_DETAILS
    assert parse_entitlement_status("unlocked") is EntitlementStatus.UNLOCKED
