#!/usr/bin/env python3
import argparse
from html import parser
import json
import logging
import os
import sys
from decimal import Decimal

from bot.client import BinanceFuturesClient, BinanceAPIError
from bot.logging_config import setup_logging
from bot.orders import place_order
from bot.validators import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_price,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def _color(text: str, code: str) -> str:
    """Wrap text in ANSI colour codes (skip if stdout is not a tty)."""
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"


def _print_summary(symbol, side, order_type, quantity, price, stop_price):
    """Print the order request summary before sending."""
    print()
    print(_color("=" * 52, BOLD))
    print(_color("  ORDER REQUEST SUMMARY", BOLD))
    print(_color("=" * 52, BOLD))
    print(f"  Symbol     : {_color(symbol, CYAN)}")
    print(f"  Side       : {_color(side, YELLOW)}")
    print(f"  Type       : {order_type}")
    print(f"  Quantity   : {quantity}")
    if price is not None:
        print(f"  Price      : {price}")
    if stop_price is not None:
        print(f"  Stop Price : {stop_price}")
    print(_color("=" * 52, BOLD))
    print()


def _print_result(result: dict):
    """Print the order response in a clean, readable format."""
    status = result.get("status", "UNKNOWN")
    color = GREEN if status in ("FILLED", "NEW", "PARTIALLY_FILLED") else YELLOW

    print(_color("=" * 52, BOLD))
    print(_color("  ORDER RESPONSE", BOLD))
    print(_color("=" * 52, BOLD))
    print(f"  Order ID     : {result.get('orderId')}")
    print(f"  Symbol       : {result.get('symbol')}")
    print(f"  Side         : {result.get('side')}")
    print(f"  Type         : {result.get('type')}")
    print(f"  Status       : {_color(status, color)}")
    print(f"  Orig Qty     : {result.get('origQty')}")
    print(f"  Executed Qty : {result.get('executedQty')}")

    avg = result.get("avgPrice")
    if avg and float(avg) > 0:
        print(f"  Avg Price    : {avg}")

    lim_price = result.get("price")
    if lim_price and float(lim_price) > 0:
        print(f"  Limit Price  : {lim_price}")

    stop = result.get("stopPrice")
    if stop and float(stop) > 0:
        print(f"  Stop Price   : {stop}")

    print(f"  Time In Force: {result.get('timeInForce')}")
    print(_color("=" * 52, BOLD))
    print()


# ── Argument parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Place orders on Binance Futures Testnet (USDT-M)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3200
  python cli.py --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.001 --stop-price 65000
        """,
    )

    # Credentials
    # Credentials
    creds = parser.add_argument_group("API credentials")

    creds.add_argument(
    "--api-key",
    default="JmZtpWRUZVM6b7PUKnp4txpz1BCvyO6RJKfVU2sYTXpgKmeNA18KldhPeD9FyNHp",
    help="Binance Futures Testnet API key",
)

    creds.add_argument(
    "--api-secret",
    default="YFz3XrD5dMwVm3CgrBfRuG5tvF20c1YawPjTQRCRha6IPCbVYGZhBwHpdMdlD6Qq",
    help="Binance Futures Testnet API secret",
)

    # Order parameters
    order = parser.add_argument_group("Order parameters")
    order.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")
    order.add_argument("--side", required=True, help="BUY or SELL")
    order.add_argument(
        "--type",
        dest="order_type",
        required=True,
        help="MARKET, LIMIT, or STOP_MARKET",
    )
    order.add_argument("--quantity", required=True, help="Order quantity")
    order.add_argument("--price", default=None, help="Limit price (required for LIMIT)")
    order.add_argument(
        "--stop-price",
        default=None,
        help="Stop price (required for STOP_MARKET)",
    )
    order.add_argument(
        "--tif",
        default="GTC",
        choices=["GTC", "IOC", "FOK"],
        help="Time-in-force for LIMIT orders (default: GTC)",
    )

    # Misc
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show DEBUG-level log output on the console",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print summary without sending the order",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output the order response as raw JSON (useful for scripting)",
    )

    return parser


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Setup logging first
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    logger = logging.getLogger("trading_bot.cli")

    # ── Validate inputs ──────────────────────────────────────────────────────
    errors = []

    try:
        symbol = validate_symbol(args.symbol)
    except ValueError as e:
        errors.append(str(e))
        symbol = None  # type: ignore

    try:
        side = validate_side(args.side)
    except ValueError as e:
        errors.append(str(e))
        side = None  # type: ignore

    try:
        order_type = validate_order_type(args.order_type)
    except ValueError as e:
        errors.append(str(e))
        order_type = None  # type: ignore

    try:
        quantity = validate_quantity(args.quantity)
    except ValueError as e:
        errors.append(str(e))
        quantity = None  # type: ignore

    # Price / stop-price validation only makes sense if order_type is known
    price = None
    stop_price = None
    if order_type:
        try:
            price = validate_price(args.price, order_type)
        except ValueError as e:
            errors.append(str(e))

        try:
            stop_price = validate_stop_price(args.stop_price, order_type)
        except ValueError as e:
            errors.append(str(e))

    if errors:
        print(_color("\n  ✗ Validation errors:", RED))
        for err in errors:
            print(f"    • {err}")
        print()
        sys.exit(1)

    # ── Credentials ──────────────────────────────────────────────────────────
    api_key = args.api_key
    api_secret = args.api_secret
    if not api_key or not api_secret:
        print(
            _color(
                "\n  ✗ API credentials missing.\n"
                "    Set --api-key / --api-secret or export "
                "BINANCE_API_KEY / BINANCE_API_SECRET.\n",
                RED,
            )
        )
        sys.exit(1)

    # ── Print summary ─────────────────────────────────────────────────────────
    _print_summary(symbol, side, order_type, quantity, price, stop_price)

    if args.dry_run:
        print(_color("  ✓ Dry-run mode: no order was sent.\n", YELLOW))
        sys.exit(0)

    # ── Place order ───────────────────────────────────────────────────────────
    try:
        client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
        result = place_order(
            client=client,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=args.tif,
        )
    except BinanceAPIError as exc:
        logger.error("API error: %s", exc)
        print(_color(f"\n  ✗ API Error: {exc}\n", RED))
        sys.exit(2)
    except Exception as exc:
        logger.exception("Unexpected error while placing order.")
        print(_color(f"\n  ✗ Unexpected error: {exc}\n", RED))
        sys.exit(3)

    # ── Print result ──────────────────────────────────────────────────────────
    if args.output_json:
        print(json.dumps(result.get("raw", result), indent=2))
    else:
        _print_result(result)
        print(_color("  ✓ Order placed successfully!\n", GREEN))


if __name__ == "__main__":
    main()
