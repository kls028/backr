"""Exact USDC amount conversion at API boundaries."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

USDC_DECIMALS = 6
USDC_SCALE = 10**USDC_DECIMALS


class MoneyValidationError(ValueError):
    """Raised when a USDC amount cannot be represented exactly."""


def parse_usdc_amount(value: str) -> int:
    """Convert a positive decimal USDC string into six-decimal atomic units."""
    if not isinstance(value, str) or not value.strip():
        raise MoneyValidationError("amount must be a decimal string")

    normalized = value.strip()
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise MoneyValidationError("amount must be a valid decimal") from exc

    if not amount.is_finite():
        raise MoneyValidationError("amount must be finite")
    if amount <= 0:
        raise MoneyValidationError("amount must be greater than zero")
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -USDC_DECIMALS:
        raise MoneyValidationError("amount must have at most 6 decimal places")

    atomic = amount * USDC_SCALE
    if atomic != atomic.to_integral_value():
        raise MoneyValidationError("amount must have at most 6 decimal places")
    return int(atomic)


def format_usdc_amount(atomic: int) -> str:
    """Format atomic units without scientific notation or floating point."""
    if not isinstance(atomic, int) or atomic < 0:
        raise MoneyValidationError("atomic amount must be a non-negative integer")
    whole, fraction = divmod(atomic, USDC_SCALE)
    if fraction == 0:
        return str(whole)
    return f"{whole}.{fraction:0{USDC_DECIMALS}d}".rstrip("0")
