from __future__ import annotations

import pytest

from app.domain.money import MoneyValidationError, format_usdc_amount, parse_usdc_amount


def test_parse_usdc_amount_uses_six_decimals() -> None:
    assert parse_usdc_amount("25") == 25_000_000
    assert parse_usdc_amount("25.125") == 25_125_000


def test_parse_usdc_amount_rejects_over_precision() -> None:
    with pytest.raises(MoneyValidationError, match="at most 6 decimal places"):
        parse_usdc_amount("1.0000001")


def test_parse_usdc_amount_rejects_non_positive_values() -> None:
    with pytest.raises(MoneyValidationError, match="greater than zero"):
        parse_usdc_amount("0")
    with pytest.raises(MoneyValidationError, match="greater than zero"):
        parse_usdc_amount("-1")


def test_format_usdc_amount_round_trips_without_float() -> None:
    assert format_usdc_amount(25_125_000) == "25.125"
    assert format_usdc_amount(1) == "0.000001"
