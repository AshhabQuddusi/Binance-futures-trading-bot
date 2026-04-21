"""
Input validation for order parameters.
All functions raise ValueError with descriptive messages on bad input.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}


def validate_symbol(symbol: str) -> str:
    """Normalise and sanity-check a trading symbol (e.g. 'btcusdt' → 'BTCUSDT')."""
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol must be a non-empty string.")
    symbol = symbol.strip().upper()
    if len(symbol) < 3 or not symbol.isalnum():
        raise ValueError(
            f"Symbol '{symbol}' looks invalid. "
            "Expected something like 'BTCUSDT' (alphanumeric, no spaces)."
        )
    return symbol


def validate_side(side: str) -> str:
    """Validate and normalise order side."""
    if not side:
        raise ValueError("Side is required.")
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(
            f"Side '{side}' is not valid. Choose from: {', '.join(sorted(VALID_SIDES))}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """Validate and normalise order type."""
    if not order_type:
        raise ValueError("Order type is required.")
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Order type '{order_type}' is not valid. "
            f"Choose from: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: str) -> Decimal:
    """Parse and validate order quantity (must be a positive number)."""
    try:
        qty = Decimal(str(quantity))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be greater than zero (got {qty}).")
    return qty


def validate_price(price: Optional[str], order_type: str) -> Optional[Decimal]:
    """
    Validate the limit price.
    - LIMIT / STOP_MARKET orders require a positive price.
    - MARKET orders must NOT supply a price.
    """
    if order_type == "MARKET":
        if price is not None:
            raise ValueError("Price must not be provided for MARKET orders.")
        return None

    # LIMIT and STOP_MARKET need a price
    if price is None:
        raise ValueError(f"Price is required for {order_type} orders.")
    try:
        p = Decimal(str(price))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValueError(f"Price must be greater than zero (got {p}).")
    return p


def validate_stop_price(stop_price: Optional[str], order_type: str) -> Optional[Decimal]:
    """Validate stop price — only required for STOP_MARKET orders."""
    if order_type != "STOP_MARKET":
        return None
    if stop_price is None:
        raise ValueError("--stop-price is required for STOP_MARKET orders.")
    try:
        sp = Decimal(str(stop_price))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Stop price '{stop_price}' is not a valid number.")
    if sp <= 0:
        raise ValueError(f"Stop price must be greater than zero (got {sp}).")
    return sp
