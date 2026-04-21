"""
Order placement logic — sits between the CLI and the raw Binance client.

Responsibilities:
  - Build correct parameter dicts for each order type
  - Call the client
  - Format and return a clean result dict
  - Log meaningful summaries at INFO level
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient, BinanceAPIError

logger = logging.getLogger("trading_bot.orders")


def _fmt(value: Any, decimals: int = 8) -> str:
    """Format a numeric string or Decimal for display, stripping trailing zeros."""
    try:
        return f"{Decimal(str(value)):.{decimals}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _build_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the fields we care about from the raw Binance order response."""
    return {
        "orderId": raw.get("orderId"),
        "symbol": raw.get("symbol"),
        "side": raw.get("side"),
        "type": raw.get("type"),
        "status": raw.get("status"),
        "origQty": raw.get("origQty"),
        "executedQty": raw.get("executedQty"),
        "avgPrice": raw.get("avgPrice"),
        "price": raw.get("price"),
        "stopPrice": raw.get("stopPrice"),
        "timeInForce": raw.get("timeInForce"),
        "updateTime": raw.get("updateTime"),
        "raw": raw,  # keep full response for debugging
    }


# ---------------------------------------------------------------------------
# Market order
# ---------------------------------------------------------------------------

def place_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: Decimal,
) -> Dict[str, Any]:
    """
    Place a MARKET order.

    Returns:
        Normalised result dict.
    Raises:
        BinanceAPIError, requests.exceptions.RequestException
    """
    logger.info(
        "MARKET ORDER  symbol=%s  side=%s  qty=%s",
        symbol, side, quantity,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=str(quantity),
    )

    result = _build_result(raw)
    logger.info(
        "Order placed successfully  orderId=%s  status=%s  executedQty=%s  avgPrice=%s",
        result["orderId"],
        result["status"],
        result["executedQty"],
        result["avgPrice"],
    )
    return result


# ---------------------------------------------------------------------------
# Limit order
# ---------------------------------------------------------------------------

def place_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    time_in_force: str = "GTC",
) -> Dict[str, Any]:
    """
    Place a LIMIT order.

    Args:
        time_in_force: GTC (default), IOC, or FOK.

    Returns:
        Normalised result dict.
    Raises:
        BinanceAPIError, requests.exceptions.RequestException
    """
    logger.info(
        "LIMIT ORDER  symbol=%s  side=%s  qty=%s  price=%s  tif=%s",
        symbol, side, quantity, price, time_in_force,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="LIMIT",
        quantity=str(quantity),
        price=str(price),
        timeInForce=time_in_force,
    )

    result = _build_result(raw)
    logger.info(
        "Order placed successfully  orderId=%s  status=%s  price=%s",
        result["orderId"],
        result["status"],
        result["price"],
    )
    return result


# ---------------------------------------------------------------------------
# Stop-Market order (bonus order type)
# ---------------------------------------------------------------------------

def place_stop_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    stop_price: Decimal,
) -> Dict[str, Any]:
    """
    Place a STOP_MARKET order (triggered when the market reaches stop_price).

    Returns:
        Normalised result dict.
    Raises:
        BinanceAPIError, requests.exceptions.RequestException
    """
    logger.info(
        "STOP_MARKET ORDER  symbol=%s  side=%s  qty=%s  stopPrice=%s",
        symbol, side, quantity, stop_price,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="STOP_MARKET",
        quantity=str(quantity),
        stopPrice=str(stop_price),
    )

    result = _build_result(raw)
    logger.info(
        "Order placed successfully  orderId=%s  status=%s  stopPrice=%s",
        result["orderId"],
        result["status"],
        result["stopPrice"],
    )
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    time_in_force: str = "GTC",
) -> Dict[str, Any]:
    """
    Unified entry-point that routes to the correct order function.

    Args:
        client:        Configured BinanceFuturesClient.
        symbol:        e.g. "BTCUSDT"
        side:          "BUY" or "SELL"
        order_type:    "MARKET", "LIMIT", or "STOP_MARKET"
        quantity:      Order quantity as Decimal.
        price:         Required for LIMIT.
        stop_price:    Required for STOP_MARKET.
        time_in_force: For LIMIT orders (default GTC).

    Returns:
        Normalised order result dict.
    """
    if order_type == "MARKET":
        return place_market_order(client, symbol, side, quantity)
    elif order_type == "LIMIT":
        if price is None:
            raise ValueError("price is required for LIMIT orders.")
        return place_limit_order(client, symbol, side, quantity, price, time_in_force)
    elif order_type == "STOP_MARKET":
        if stop_price is None:
            raise ValueError("stop_price is required for STOP_MARKET orders.")
        return place_stop_market_order(client, symbol, side, quantity, stop_price)
    else:
        raise ValueError(f"Unsupported order type: {order_type}")
