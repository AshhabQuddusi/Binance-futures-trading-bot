"""
Low-level Binance Futures Testnet REST client.

Handles:
  - HMAC-SHA256 request signing
  - Timestamp / recvWindow management
  - HTTP session management with retries
  - Structured logging of every request and response
  - Raising BinanceAPIError for non-2xx responses
"""

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter, Retry

logger = logging.getLogger("trading_bot.client")

BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error payload or a non-2xx status."""

    def __init__(self, status_code: int, code: int, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"[HTTP {status_code}] Binance error {code}: {message}")


class BinanceFuturesClient:
    """Thin wrapper around the Binance USDT-M Futures Testnet REST API."""

    def __init__(self, api_key: str, api_secret: str):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must both be non-empty strings.")
        self._api_key = api_key
        self._api_secret = api_secret.encode()

        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session = requests.Session()
        self._session.mount("https://", adapter)
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> str:
        """Return the HMAC-SHA256 hex-digest signature for the given params dict."""
        query_string = urlencode(params)
        return hmac.new(self._api_secret, query_string.encode(), hashlib.sha256).hexdigest()

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request against the Binance Futures Testnet.

        Args:
            method:   "GET" | "POST" | "DELETE"
            endpoint: e.g. "/fapi/v1/order"
            params:   query / body parameters
            signed:   whether to append timestamp + signature

        Returns:
            Parsed JSON response dict.

        Raises:
            BinanceAPIError: on API-level errors (non-zero 'code' field or non-2xx status).
            requests.exceptions.RequestException: on network failures.
        """
        params = dict(params or {})

        if signed:
            params["timestamp"] = self._timestamp()
            params["recvWindow"] = RECV_WINDOW
            params["signature"] = self._sign(params)

        url = BASE_URL + endpoint

        logger.debug(
            "REQUEST  method=%s  url=%s  params=%s",
            method,
            url,
            {k: v for k, v in params.items() if k != "signature"},  # don't log sig
        )

        try:
            if method == "GET":
                response = self._session.get(url, params=params, timeout=10)
            elif method == "POST":
                response = self._session.post(url, data=params, timeout=10)
            elif method == "DELETE":
                response = self._session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.exceptions.RequestException as exc:
            logger.error("Network error while calling %s %s: %s", method, endpoint, exc)
            raise

        logger.debug(
            "RESPONSE  status=%s  body=%s",
            response.status_code,
            response.text[:500],  # cap at 500 chars to avoid log bloat
        )

        # Parse JSON body (Binance always returns JSON)
        try:
            data = response.json()
        except ValueError:
            logger.error("Non-JSON response (%s): %s", response.status_code, response.text)
            raise BinanceAPIError(response.status_code, -1, "Non-JSON response from server.")

        # API-level error: Binance returns {"code": <negative>, "msg": "..."}
        if isinstance(data, dict) and data.get("code", 0) < 0:
            logger.error(
                "API error  code=%s  msg=%s", data.get("code"), data.get("msg")
            )
            raise BinanceAPIError(
                response.status_code,
                data.get("code", -1),
                data.get("msg", "Unknown error"),
            )

        if not response.ok:
            raise BinanceAPIError(response.status_code, -1, response.text)

        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time as a UNIX timestamp in ms."""
        data = self._request("GET", "/fapi/v1/time")
        return data["serverTime"]

    def get_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange info (symbols, filters, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def place_order(self, **order_params) -> Dict[str, Any]:
        """
        Place a new futures order.

        Keyword args mirror the Binance /fapi/v1/order POST parameters:
          symbol, side, type, quantity, price, timeInForce, stopPrice, etc.
        """
        logger.info(
            "Placing order: symbol=%s  side=%s  type=%s  qty=%s  price=%s",
            order_params.get("symbol"),
            order_params.get("side"),
            order_params.get("type"),
            order_params.get("quantity"),
            order_params.get("price", "N/A"),
        )
        return self._request("POST", "/fapi/v1/order", params=order_params, signed=True)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Query an existing order by orderId."""
        return self._request(
            "GET",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        return self._request(
            "DELETE",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def get_account(self) -> Dict[str, Any]:
        """Fetch account information (balances, positions, etc.)."""
        return self._request("GET", "/fapi/v2/account", signed=True)
