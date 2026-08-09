import base64
import hashlib
import struct

from app.indexer.parser import decode_campaign_events, decode_program_data


def _event_bytes(name: str, body: bytes) -> bytes:
    return hashlib.sha256(f"event:{name}".encode()).digest()[:8] + body


def test_campaign_event_decoder_reads_anchor_events() -> None:
    payload = _event_bytes(
        "SubscriptionPurchased",
        bytes(32) + bytes([1]) * 32 + struct.pack("<QQQQ", 25, 2, 1, 1),
    )

    events = decode_campaign_events(
        decode_program_data([f"Program data: {base64.b64encode(payload).decode()}"])
    )

    assert len(events) == 1
    assert events[0].event_type == "subscription_purchased"
    assert events[0].amount_atomic == 25
    assert events[0].pending_units == 1


def test_campaign_settlement_event_decoder_reads_boolean_and_pending_units() -> None:
    payload = _event_bytes(
        "CampaignSettled",
        bytes(32) + bytes([1]) * 32 + bytes([1]) + struct.pack("<Q", 4),
    )

    events = decode_campaign_events(
        decode_program_data([f"Program data: {base64.b64encode(payload).decode()}"])
    )

    assert events[0].event_type == "campaign_settled"
    assert events[0].successful is True
    assert events[0].pending_units == 4
