# Binance Futures Testnet Trading Bot

A clean, structured Python CLI for placing orders on the **Binance USDT-M Futures Testnet**.

---

## Features

| Feature | Details |
|---|---|
| Order types | MARKET, LIMIT, **STOP_MARKET** (bonus) |
| Sides | BUY and SELL |
| CLI | `argparse` with rich help text and coloured output |
| Validation | Strict input validation with descriptive error messages |
| Logging | Rotating file log (`logs/trading_bot.log`) + console output |
| Error handling | API errors, network failures, invalid inputs |
| Dry-run mode | Validate and preview without sending |
| JSON output | `--json` flag for scripting / piping |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Low-level Binance REST client (signing, retries)
│   ├── orders.py          # Order placement logic per order type
│   ├── validators.py      # Input validation (raises ValueError on bad data)
│   └── logging_config.py  # Rotating file + console logging setup
├── cli.py                 # CLI entry point (argparse)
├── logs/
│   └── trading_bot.log    # Auto-created on first run
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet Credentials

1. Go to [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with your GitHub account
3. Under **API Keys**, generate a new key pair
4. Copy the **API Key** and **Secret Key**

### 2. Install dependencies

```bash
# Clone or unzip the project
cd trading_bot

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### 3. Set credentials

**Option A – environment variables (recommended)**

```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
```

**Option B – pass directly on each command**

```bash
python cli.py --api-key YOUR_KEY --api-secret YOUR_SECRET ...
```

---

## Usage

### Basic syntax

```
python cli.py [--api-key KEY] [--api-secret SECRET]
              --symbol SYMBOL
              --side   BUY|SELL
              --type   MARKET|LIMIT|STOP_MARKET
              --quantity QTY
              [--price PRICE]          # required for LIMIT
              [--stop-price PRICE]     # required for STOP_MARKET
              [--tif GTC|IOC|FOK]      # default: GTC
              [-v]                     # verbose / DEBUG logging
              [--dry-run]              # validate only, no order sent
              [--json]                 # output raw JSON response
```

---

### Examples

#### Market BUY

```bash
python cli.py \
  --symbol BTCUSDT \
  --side   BUY \
  --type   MARKET \
  --quantity 0.001
```

Expected output:
```
====================================================
  ORDER REQUEST SUMMARY
====================================================
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001
====================================================

====================================================
  ORDER RESPONSE
====================================================
  Order ID     : 4081232
  Symbol       : BTCUSDT
  Side         : BUY
  Type         : MARKET
  Status       : FILLED
  Orig Qty     : 0.001
  Executed Qty : 0.001
  Avg Price    : 65432.10000
====================================================

  ✓ Order placed successfully!
```

---

#### Limit SELL

```bash
python cli.py \
  --symbol ETHUSDT \
  --side   SELL \
  --type   LIMIT \
  --quantity 0.01 \
  --price 3200
```

---

#### Stop-Market BUY (bonus order type)

Triggers a market order when the price reaches `--stop-price`.

```bash
python cli.py \
  --symbol BTCUSDT \
  --side   BUY \
  --type   STOP_MARKET \
  --quantity 0.001 \
  --stop-price 65000
```

---

#### Dry-run (no order sent)

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --dry-run
```

---

#### JSON output (for scripting)

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --json
```

---

### Viewing logs

```bash
tail -f logs/trading_bot.log
```

Log entries look like:

```
2025-07-14 10:22:01 | INFO     | trading_bot.orders | MARKET ORDER  symbol=BTCUSDT  side=BUY  qty=0.001
2025-07-14 10:22:01 | INFO     | trading_bot.orders | Order placed  orderId=4081232  status=FILLED  executedQty=0.001  avgPrice=65432.1
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Invalid symbol / side / type | Validation error printed; exit code 1 |
| Missing price for LIMIT | Validation error; exit code 1 |
| Missing credentials | Clear message; exit code 1 |
| Binance API error (e.g. -2019 Insufficient margin) | Error printed + logged; exit code 2 |
| Network failure (timeout, DNS) | Retried 3× then error reported; exit code 3 |

---

## Assumptions

- The bot targets **USDT-M Futures Testnet** only (`https://testnet.binancefuture.com`).
- `quantity` precision is passed as-is; Binance will reject values that violate the symbol's `LOT_SIZE` filter. Check `GET /fapi/v1/exchangeInfo` for per-symbol step sizes if you hit `-1111` errors.
- The STOP_MARKET order uses `positionSide=BOTH` (one-way mode), which is the testnet default.
- Credentials are read from env vars or CLI flags; they are **never** written to disk or logged.
- The log file rotates at 5 MB and keeps 3 backups.

---

## Dependencies

```
requests>=2.31.0   # HTTP client with retry support
```

Only stdlib + `requests` — no Binance SDK dependency, giving full control over the request/response cycle.


👨‍💻 Author
Ashhab Quddusi
LinkedIn: www.linkedin.com/in/ashhab-quddusi
GitHub: https://github.com/AshhabQuddusi?tab=repositories

⭐ Support
If you found this project helpful, consider giving it a star on GitHub!
